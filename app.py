import hashlib
import json
import os
import urllib.request
import uuid
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAI

from dispute_engine import score_dispute

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "static", "audio")
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

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
os.makedirs(AUDIO_DIR, exist_ok=True)


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


def transcribe_sarvam(path, api_key):
    ext = path.rsplit(".", 1)[-1]
    with open(path, "rb") as f:
        resp = httpx.post(
            SARVAM_URL,
            headers={"api-subscription-key": api_key},
            data={"model": "saaras:v3", "mode": "codemix", "language_code": "unknown"},
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
    return render_template("index.html")


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


@app.route("/process", methods=["POST"])
def process():
    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "no audio file"}), 400

    try:
        ext = (audio.filename or "").rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXT:
            ext = "webm"
        filename = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join(AUDIO_DIR, filename)
        audio.save(path)

        form = request.form
        order_id = clean_id(form.get("order_id"))
        rider_id = clean_id(form.get("rider_id"))
        otp_confirmed = parse_bool(form.get("otp_confirmed"))
        gps_matched = parse_bool(form.get("gps_matched"))

        # Trust layer is fixed on receipt, before any AI touches the audio.
        server_timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
        gps_string = parse_gps(form.get("gps_lat"), form.get("gps_lng"))
        sealed_fields = f"{server_timestamp}|{gps_string}|{order_id}|{rider_id}|{otp_confirmed}|{gps_matched}"
        with open(path, "rb") as f:
            audio_bytes = f.read()
        record_hash = hashlib.sha256(audio_bytes + sealed_fields.encode()).hexdigest()
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
        return jsonify({"error": str(e)}), 500

    engines = {"stt_engine": stt_engine, "extraction_engine": extracted.pop("extraction_engine", None)}
    if "error" in extracted:
        return jsonify({**extracted, **engines, "record": record, "transcript": transcript}), 500

    card = build_evidence_card(extracted, order_id, rider_id, otp_confirmed, gps_matched)
    customer_claim = (form.get("customer_claim") or "").strip()[:200]
    return jsonify({
        "evidence_card": card,
        "dispute_score": score_dispute(card, customer_claim),
        "customer_claim": customer_claim,
        "record": record,
        "transcript": transcript,
        **engines,
    })


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5050)))
