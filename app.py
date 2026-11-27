import hashlib
import hmac
import json
import secrets
import os
import re
import tempfile
import time
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse

import httpx
import qrcode
import qrcode.image.svg
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from openai import OpenAI

import db
from dispute_engine import score_dispute
from mock_disputes import MOCK_DISPUTES

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "static", "audio")
PHOTO_DIR = os.path.join(BASE_DIR, "photos")  # outside static/: not publicly served
PHOTO_EXT = {"jpg", "jpeg", "png", "webp", "heic"}
PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "extraction.txt")
ALLOWED_EXT = {"webm", "ogg", "mp4", "m4a", "wav", "mp3"}
PLACEHOLDER_KEYS = {"", "your_key_here"}
SARVAM_URL = "https://api.sarvam.ai/speech-to-text"
OPENROUTER_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openai/gpt-4o"
AUDIO_MIME = {
    "webm": "audio/webm", "ogg": "audio/ogg", "mp4": "audio/mp4",
    "m4a": "audio/mp4", "wav": "audio/wav", "mp3": "audio/mpeg",
}
# Without this, Whisper hears Hinglish "teen floor" (3rd) as "18th floor".
WHISPER_HINT = (
    "Hinglish delivery note in Roman script. Ek, do, teen, chaar, paanch floor. "
    "Gate locked, watchman ne liya, reception pe chhoda, photo liya, customer ko diya."
)

IST = timezone(timedelta(hours=5, minutes=30))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.secret_key = os.getenv("FLASK_SECRET_KEY") or ""
if not app.secret_key:
    app.secret_key = secrets.token_hex(32)
    print(" * FLASK_SECRET_KEY not set: using a temporary key, so logins reset on every restart.")
db.init_db()
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(PHOTO_DIR, exist_ok=True)


def env_key(name):
    value = (os.getenv(name) or "").strip()
    return None if value in PLACEHOLDER_KEYS else value


def openai_client():
    key = env_key("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set on the server")
    return OpenAI(api_key=key)


def transcribe_wispr(path, api_key):
    # Endpoint is a placeholder: confirm URL and response shape against Wispr's API docs.
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        audio_data = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + audio_data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        "https://api.wispr.ai/v1/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read()).get("text", "")


def transcribe_sarvam(path, api_key, language_code="unknown"):  # default: auto-detect (evidence path)
    ext = path.rsplit(".", 1)[-1]
    with open(path, "rb") as f:
        resp = httpx.post(
            SARVAM_URL,
            headers={"api-subscription-key": api_key},
            data={"model": "saaras:v3", "mode": "codemix", "language_code": language_code},
            files={"file": (os.path.basename(path), f, AUDIO_MIME.get(ext, "application/octet-stream"))},
            timeout=20,
        )
    resp.raise_for_status()
    return resp.json()["transcript"]


def transcribe_audio(path):
    """STT: Wispr if keyed, then Sarvam codemix if keyed, else Whisper. Returns (transcript, engine)."""
    wispr_key = env_key("WISPR_API_KEY")
    if wispr_key:
        try:
            return transcribe_wispr(path, wispr_key), "wispr"
        except Exception as e:
            app.logger.warning("Wispr failed (%s), trying next engine", e)
    sarvam_key = env_key("SARVAM_API_KEY")
    if sarvam_key:
        try:
            return transcribe_sarvam(path, sarvam_key), "sarvam"
        except Exception as e:
            app.logger.warning("Sarvam failed (%s), falling back to Whisper", e)
    with open(path, "rb") as f:
        text = openai_client().audio.transcriptions.create(
            model="whisper-1", file=f, prompt=WHISPER_HINT
        ).text
    return text, "whisper"


def chat_json(client, model, system_prompt, transcript):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        temperature=0,
        max_tokens=800,
        response_format={"type": "json_object"},
        timeout=30,
    )
    return response.choices[0].message.content.strip()


def extract_structured(transcript):
    """Extraction: OpenRouter if keyed, else direct OpenAI. Adds extraction_engine to the result."""
    with open(PROMPT_PATH, "r") as f:
        system_prompt = f.read()

    raw, engine = None, None
    openrouter_key = env_key("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            client = OpenAI(base_url=OPENROUTER_URL, api_key=openrouter_key)
            raw = chat_json(client, OPENROUTER_MODEL, system_prompt, transcript)
            engine = "openrouter"
        except Exception as e:
            app.logger.warning("OpenRouter failed (%s), falling back to OpenAI", e)
    if raw is None:
        raw = chat_json(openai_client(), "gpt-4o-mini", system_prompt, transcript)
        engine = "openai"

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"error": "parse_failed", "raw": raw}
    result["extraction_engine"] = engine
    return result


VOICE_ENUMS = {
    "delivery_status": ({"delivered", "failed", "partial", "not_mentioned"}, "not_mentioned"),
    "handover_location": ({"door", "reception", "security", "neighbor", "other", "not_mentioned"}, "other"),
    "obstacle": ({"none", "gate_locked", "customer_unavailable", "address_issue", "refused", "other", "not_mentioned"}, "other"),
    "confidence": ({"high", "medium", "low"}, "low"),
}


def parse_bool(value):
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def clean_id(value):
    value = (value or "").strip()[:64]
    return value or "not_provided"


def build_evidence_card(extracted, order_id, rider_id, otp_confirmed, gps_matched):
    """Fixed rules: platform fields come from the request; voice fields are clamped to allowed values."""
    card = {
        "order_id": order_id,
        "rider_id": rider_id,
        "otp_confirmed": otp_confirmed,
        "gps_matched": gps_matched,
    }
    for field, (allowed, fallback) in VOICE_ENUMS.items():
        value = str(extracted.get(field, "not_mentioned")).strip().lower()
        card[field] = value if value in allowed else fallback
    for field in ("customer_instruction", "spoken_context"):
        value = str(extracted.get(field) or "not_mentioned").strip()[:500]
        card[field] = value or "not_mentioned"
    return card


def parse_gps(lat, lng):
    try:
        lat_f, lng_f = float(lat), float(lng)
    except (TypeError, ValueError):
        return "unavailable"
    if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
        return "unavailable"
    return f"{lat_f:.6f},{lng_f:.6f}"


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "Audio file too large (max 10 MB)"}), 413


@app.route("/")
def index():
    return redirect(url_for("rider", **request.args))


@app.route("/rider")
def rider():
    order_id = (request.args.get("order_id") or "ORD123").strip()[:64]
    rider_id = (request.args.get("rider_id") or "RID456").strip()[:64]
    if not db.get_confirmation(order_id):
        # Fresh one-time code per page load; an existing confirmation (and its code) is left alone.
        db.set_nonce(order_id, secrets.token_urlsafe(12))
    nonce = db.get_nonce(order_id) or ""
    confirm_url = request.host_url.rstrip("/") + url_for("confirm", order_id=order_id, rider_id=rider_id, n=nonce)
    qr_svg = qrcode.make(
        confirm_url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10
    ).to_string(encoding="unicode")
    return render_template("rider.html", qr_svg=qr_svg, confirm_url=confirm_url, qr_nonce=nonce)


def nonce_ok(order_id, nonce):
    expected = db.get_nonce(order_id)
    return bool(expected and nonce) and hmac.compare_digest(expected, nonce)


@app.route("/confirm", methods=["GET", "POST"])
def confirm():
    """Customer-side page opened from the QR. One tap with the QR's one-time code confirms receipt."""
    order_id = clean_id(request.values.get("order_id"))
    nonce = request.values.get("n") or ""
    if not nonce_ok(order_id, nonce):
        return render_template("confirm.html", order_id=order_id, expired=True)
    if request.method == "POST":
        db.add_confirmation(order_id, str(uuid.uuid4()))  # first tap wins
        return render_template("confirm.html", order_id=order_id, done=True)
    return render_template("confirm.html", order_id=order_id, nonce=nonce, done=False)


@app.route("/confirmation-status")
def confirmation_status():
    order_id = clean_id(request.args.get("order_id"))
    conf = db.get_confirmation(order_id)
    # The session id goes only to the page holding the QR's one-time code, not to anyone who knows the order id.
    session_id = conf["session_id"] if conf and nonce_ok(order_id, request.args.get("n") or "") else None
    return jsonify({"confirmed": bool(conf), "session_id": session_id})


@app.route("/confirmation-reset", methods=["POST"])
def confirmation_reset():
    """Testing aid for the rider page's 'Reset confirmation' link."""
    order_id = clean_id(request.form.get("order_id"))
    db.reset_confirmation(order_id)
    return jsonify({"confirmed": False})


def mask_phone(raw):
    digits = "".join(c for c in (raw or "") if c.isdigit())
    return "*" * (len(digits) - 4) + digits[-4:] if len(digits) >= 10 else None


def ist_time(moment):
    return moment.astimezone(IST).strftime("%d %b, %H:%M")


def parse_utc(iso):
    try:
        return datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def ist_label(iso):
    moment = parse_utc(iso)
    return ist_time(moment) if moment else "—"


# ---- login ----

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def safe_next(target):
    """Only same-site paths like /history (blocks redirects to other sites)."""
    target = target or ""
    parts = urlparse(target)
    if target.startswith("/") and not target.startswith("//") and not parts.scheme and not parts.netloc:
        return target
    return url_for("dashboard")


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.values.get("next") or ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user_id = db.verify_user(email, request.form.get("password") or "")
        if user_id:
            session.clear()
            session["user_id"] = user_id
            session["email"] = email
            return redirect(safe_next(next_url))
        return render_template("login.html", error="Email or password is incorrect.", email=email, next=next_url), 401
    return render_template("login.html", next=next_url)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        error = None
        if "@" not in email or "." not in email.split("@")[-1] or len(email) > 254:
            error = "Enter a valid email address."
        elif len(password) < 8:
            error = "Use at least 8 characters for the password."
        else:
            user_id = db.create_user(email, password)
            if not user_id:
                error = "An account with this email already exists."
            else:
                session.clear()
                session["user_id"] = user_id
                session["email"] = email
                return redirect(url_for("dashboard"))
        return render_template("signup.html", error=error, email=email), 400
    return render_template("signup.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---- platform views ----

def db_rows():
    rows = []
    for d in db.list_deliveries():
        stored = d["card_json"] or {}
        rows.append({
            "id": d["id"],
            "card": stored.get("card", {}),
            "score": stored.get("score", {}),
            "transcript": stored.get("transcript", ""),
            "customer_claim": stored.get("customer_claim", ""),
            "time": ist_label(d["received_at"]),
            "received_at": d["received_at"],
            "audio_hash": d["audio_hash"] or "",
            "live": True,
            "export": {k: v for k, v in d.items() if k != "card_json"} | {"evidence": stored},
        })
    return rows


def db_tiles(rows):
    n = len(rows)
    strengths = [r["score"].get("evidence_strength", 0) for r in rows]
    inconclusive = sum(1 for r in rows if r["score"].get("recommendation") == "inconclusive")
    return {
        "deliveries": f"{n:,}",
        "cards": f"{n:,}",
        "cards_pct": "100%" if n else "0%",
        "inconclusive": f"{round(100 * inconclusive / n)}%" if n else "0%",
        "avg_strength": round(sum(strengths) / n) if n else 0,
    }


MOCK_TILES = {"deliveries": "1,247", "cards": "1,089", "cards_pct": "87%", "inconclusive": "12%", "avg_strength": 84}


@app.route("/dashboard")
@login_required
def dashboard():
    now = datetime.now(timezone.utc)
    live = db_rows()
    mock = [
        {**d, "score": score_dispute(d["card"], d["customer_claim"]), "live": False,
         "time": ist_time(now - timedelta(minutes=d["minutes_ago"]))}
        for d in MOCK_DISPUTES
    ]
    tiles = db_tiles(live) if live else MOCK_TILES
    return render_template(
        "dashboard.html", rows=[*live, *mock], live_count=len(live),
        tiles=tiles, tiles_from_db=bool(live), email=session.get("email"),
    )


@app.route("/history")
@login_required
def history():
    return render_template("history.html", rows=db_rows(), email=session.get("email"))


@app.route("/transcribe", methods=["POST"])
def transcribe():
    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "no audio file"}), 400
    path = os.path.join(AUDIO_DIR, f"{uuid.uuid4().hex}.webm")
    try:
        audio.save(path)
        transcript, stt_engine = transcribe_audio(path)
        return jsonify({"transcript": transcript, "stt_engine": stt_engine})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/extract", methods=["POST"])
def extract():
    data = request.get_json(silent=True)
    if not data or "transcript" not in data:
        return jsonify({"error": "no transcript"}), 400
    try:
        return jsonify(extract_structured(data["transcript"]))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def save_photo(photo):
    """Optional delivery photo. Saved as-is; no vision model runs on it. Returns photo_id or None."""
    if not photo or not photo.filename or not (photo.mimetype or "").startswith("image/"):
        return None
    ext = photo.filename.rsplit(".", 1)[-1].lower()
    photo_id = str(uuid.uuid4())
    photo.save(os.path.join(PHOTO_DIR, f"{photo_id}.{ext if ext in PHOTO_EXT else 'jpg'}"))
    return photo_id


def create_evidence(audio, form, order_id, rider_id, otp_confirmed, gps_matched, photo=None, card_extras=None):
    """Shared by /process (demo page) and /evidence (platform API). Returns (payload, status)."""
    try:
        photo_id = save_photo(photo)
        ext = (audio.filename or "").rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXT:
            ext = "webm"
        filename = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join(AUDIO_DIR, filename)
        audio.save(path)

        # Trust layer is fixed on receipt, before any AI touches the audio.
        server_timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
        gps_string = parse_gps(form.get("gps_lat"), form.get("gps_lng"))
        sealed_fields = f"{server_timestamp}|{gps_string}|{order_id}|{rider_id}|{otp_confirmed}|{gps_matched}"
        with open(path, "rb") as f:
            audio_bytes = f.read()
        record_hash = hashlib.sha256(audio_bytes + sealed_fields.encode()).hexdigest()
        audio_hash = hashlib.sha256(audio_bytes).hexdigest()  # raw audio only
        record = {
            "timestamp": server_timestamp,
            "gps": gps_string,
            "hash": record_hash,
            "hash_short": record_hash[:12],
            "sealed_fields": sealed_fields,
            "audio_url": f"/static/audio/{filename}",
        }

        transcript, stt_engine = transcribe_audio(path)
        extracted = extract_structured(transcript)
    except Exception as e:
        return {"error": str(e)}, 500

    engines = {"stt_engine": stt_engine, "extraction_engine": extracted.pop("extraction_engine", None)}
    if "error" in extracted:
        return {**extracted, **engines, "record": record, "transcript": transcript}, 502

    card = build_evidence_card(extracted, order_id, rider_id, otp_confirmed, gps_matched)
    card["photo_captured"] = bool(photo_id)
    card["photo_id"] = photo_id
    card["audio_hash"] = audio_hash
    card["received_at"] = server_timestamp  # server clock, independent of the phone
    card["recorded_at_client"] = (form.get("recorded_at_client") or "").strip()[:40] or None  # phone clock, display only
    card.update(card_extras or {})  # added before scoring so the reasoning can name the check used
    customer_claim = (form.get("customer_claim") or "").strip()[:200]
    dispute_score = score_dispute(card, customer_claim)
    evidence_id = db.insert_delivery({
        "order_id": order_id,
        "rider_id": rider_id,
        "customer_phone_masked": card.get("customer_phone"),
        "otp_confirmed": int(bool(card.get("otp_confirmed"))),
        "gps_matched": int(bool(card.get("gps_matched"))),
        "photo_captured": int(bool(card.get("photo_captured"))),
        "photo_id": card.get("photo_id"),
        "spoken_context": card.get("spoken_context"),
        "handover_location": card.get("handover_location"),
        "obstacle": card.get("obstacle"),
        "customer_instruction": card.get("customer_instruction"),
        "confidence": card.get("confidence"),
        "evidence_strength": dispute_score.get("evidence_strength"),
        "recommendation": dispute_score.get("recommendation"),
        "stt_engine": engines["stt_engine"],
        "extraction_engine": engines["extraction_engine"],
        "audio_hash": audio_hash,
        "recording_session_id": card.get("recording_session_id"),
        "received_at": server_timestamp,
        "customer_confirmed": None if "customer_confirmed" not in card else int(bool(card["customer_confirmed"])),
        "session_verified": None if "session_verified" not in card else int(bool(card["session_verified"])),
        "recorded_at_client": card.get("recorded_at_client"),
        "client_id": (form.get("client_id") or "").strip()[:64] or None,
        "card_json": json.dumps({
            "card": card, "score": dispute_score, "transcript": transcript,
            "customer_claim": customer_claim, "record": record, **engines,
        }, ensure_ascii=False),
    })
    return {
        "evidence_id": evidence_id,
        "evidence_card": card,
        "dispute_score": dispute_score,
        "customer_claim": customer_claim,
        "record": record,
        "transcript": transcript,
        **engines,
    }, 200


@app.route("/process", methods=["POST"])
def process():
    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "no audio file"}), 400
    form = request.form
    order_id = clean_id(form.get("order_id"))
    # Recording session: a wrong or forged session id is rejected before any audio is processed.
    # No session id is allowed and recorded as "not verified" (scores as unconfirmed).
    session_id = (form.get("session_id") or "").strip()[:64]
    expected = (db.get_confirmation(order_id) or {}).get("session_id") or ""
    session_verified = bool(session_id) and hmac.compare_digest(session_id, expected)
    if session_id and not session_verified:
        return jsonify({"error": "Recording session invalid or expired."}), 400
    customer_confirmed = session_verified  # the session is the proof of the customer's tap
    payload, status = create_evidence(
        audio, form, order_id, clean_id(form.get("rider_id")),
        customer_confirmed,  # QR confirmation is the OTP signal for scoring
        parse_bool(form.get("gps_matched")),
        photo=request.files.get("photo"),
        card_extras={
            "customer_confirmed": customer_confirmed,
            "customer_phone": mask_phone(form.get("customer_phone")),
            "session_verified": session_verified,
            "recording_session_id": session_id or None,
        },
    )
    # A confirmation lasts for the order (re-records included) until reset or restart.
    return jsonify(payload), status


def strict_bool(value):
    value = (value or "").strip().lower()
    return {"true": True, "1": True, "false": False, "0": False}.get(value)


@app.route("/evidence", methods=["POST"])
def evidence():
    form = request.form
    audio = request.files.get("audio")
    order_id = (form.get("order_id") or "").strip()[:64]
    rider_id = (form.get("rider_id") or "").strip()[:64]
    otp_confirmed = strict_bool(form.get("otp_confirmed"))
    gps_matched = strict_bool(form.get("gps_matched"))

    problems = []
    if not audio or not audio.filename:
        problems.append("audio")
    if not order_id:
        problems.append("order_id")
    if not rider_id:
        problems.append("rider_id")
    if otp_confirmed is None:
        problems.append("otp_confirmed (must be true or false)")
    if gps_matched is None:
        problems.append("gps_matched (must be true or false)")
    if problems:
        return jsonify({"error": "invalid_request", "fields": problems}), 400

    payload, status = create_evidence(audio, form, order_id, rider_id, otp_confirmed, gps_matched,
                                      photo=request.files.get("photo"))
    return jsonify(payload), status


# ---- Speech help (rider page): stateless, nothing stored or logged ----

HELP_PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "help.txt")
HELP_FALLBACK = "Please tap the record button and speak one line about the delivery."
HELP_LIMIT, HELP_WINDOW_S = 10, 60
HELP_HITS = {}  # client ip -> recent request times (in memory, rate limit only)
SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")


def help_rate_limited():
    ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "?").split(",")[0].strip()
    now = time.monotonic()
    hits = [t for t in HELP_HITS.get(ip, []) if now - t < HELP_WINDOW_S]
    limited = len(hits) >= HELP_LIMIT
    if not limited:
        hits.append(now)
    HELP_HITS[ip] = hits
    if len(HELP_HITS) > 5000:  # keep the table small
        HELP_HITS.clear()
    return limited


def help_chat(question):
    with open(HELP_PROMPT_PATH, "r") as f:
        system_prompt = f.read()
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    openrouter_key = env_key("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            client = OpenAI(base_url=OPENROUTER_URL, api_key=openrouter_key)
            r = client.chat.completions.create(
                model=OPENROUTER_MODEL, messages=messages, temperature=0, max_tokens=120, timeout=20
            )
            return r.choices[0].message.content or ""
        except Exception as e:
            app.logger.warning("Help: OpenRouter failed (%s), falling back to OpenAI", type(e).__name__)
    r = openai_client().chat.completions.create(
        model="gpt-4o-mini", messages=messages, temperature=0, max_tokens=120, timeout=20
    )
    return r.choices[0].message.content or ""


def tidy_help_answer(text):
    text = (text or "").strip().strip("'\"").strip()
    if not text or text.lower().startswith(HELP_FALLBACK.rstrip(".").lower()):
        return HELP_FALLBACK
    answer = " ".join(SENTENCE_END.split(text)[:2])
    return answer[:400].rstrip()


@app.route("/help", methods=["POST"])
def help_answer():
    question = str((request.get_json(silent=True) or {}).get("question") or "").strip()[:300]
    if not question:
        return jsonify({"error": "Ask a question first."}), 400
    if help_rate_limited():
        return jsonify({"error": "Too many questions. Please wait a minute."}), 429
    try:
        answer = tidy_help_answer(help_chat(question))
    except Exception as e:
        app.logger.warning("Help answer failed (%s)", type(e).__name__)  # no question text in logs
        return jsonify({"error": "Help is unavailable right now."}), 502
    return jsonify({"answer": answer})


@app.route("/help/stt", methods=["POST"])
def help_stt():
    audio = request.files.get("audio")
    if not audio or not audio.filename:
        return jsonify({"error": "no audio file"}), 400
    if help_rate_limited():
        return jsonify({"error": "Too many questions. Please wait a minute."}), 429
    ext = audio.filename.rsplit(".", 1)[-1].lower()
    ext = ext if ext in ALLOWED_EXT else "webm"
    fd, path = tempfile.mkstemp(suffix="." + ext)  # outside static/, deleted below
    os.close(fd)
    try:
        audio.save(path)
        sarvam_key = env_key("SARVAM_API_KEY")
        transcript = None
        if sarvam_key:
            try:
                transcript = transcribe_sarvam(path, sarvam_key, language_code="hi-IN")
            except Exception as e:
                app.logger.warning("Help STT: Sarvam failed (%s), using fallback engine", type(e).__name__)
        if transcript is None:
            transcript, _ = transcribe_audio(path)
        return jsonify({"transcript": (transcript or "").strip()[:300]})
    except Exception as e:
        app.logger.warning("Help STT failed (%s)", type(e).__name__)
        return jsonify({"error": "Could not hear that. Please type your question."}), 502
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5050)))
