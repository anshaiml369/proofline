import hashlib
import json
import os
import urllib.request
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAI

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "static", "audio")
PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "extraction.txt")
ALLOWED_EXT = {"webm", "ogg", "mp4", "m4a", "wav", "mp3"}
PLACEHOLDER_KEYS = {"", "your_key_here"}
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


def transcribe_audio(path):
    """STT: Wispr Flow if a key is configured, else OpenAI Whisper."""
    wispr_key = env_key("WISPR_API_KEY")
    if wispr_key:
        try:
            return transcribe_wispr(path, wispr_key)
        except Exception as e:
            app.logger.warning("Wispr failed (%s), falling back to Whisper", e)
    with open(path, "rb") as f:
        return openai_client().audio.transcriptions.create(
            model="whisper-1", file=f, prompt=WHISPER_HINT
        ).text


def extract_structured(transcript):
    with open(PROMPT_PATH, "r") as f:
        prompt = f.read().replace("{transcript}", transcript)

    response = openai_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "parse_failed", "raw": raw}


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
        return jsonify({"transcript": transcribe_audio(path)})
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

        # Trust layer is fixed on receipt, before any AI touches the audio.
        server_timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
        gps_string = parse_gps(request.form.get("gps_lat"), request.form.get("gps_lng"))
        with open(path, "rb") as f:
            audio_bytes = f.read()
        record_hash = hashlib.sha256(
            audio_bytes + server_timestamp.encode() + gps_string.encode()
        ).hexdigest()
        trust = {
            "timestamp": server_timestamp,
            "gps": gps_string,
            "hash": record_hash,
            "hash_short": record_hash[:12],
            "audio_url": f"/static/audio/{filename}",
        }

        transcript = transcribe_audio(path)
        result = extract_structured(transcript)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    result.update(trust)
    result["transcript"] = transcript
    return jsonify(result), (500 if "error" in result else 200)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5050)))
