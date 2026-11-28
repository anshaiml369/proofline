"""PagarSaathi: a Hinglish voice agent that works out a daily-wage worker's unpaid wages."""
import json
import os
import tempfile
import threading
import time

import httpx
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAI

import conversation
import database
import sarvam_tts
from hinglish_numbers import parse_amounts, says_none

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TTS_DIR = os.path.join(BASE_DIR, "static", "tts")      # generated, git-ignored
DEMO_DIR = os.path.join(BASE_DIR, "static", "demo")    # pre-recorded, committed (scripted mode)
PROMPT = open(os.path.join(BASE_DIR, "prompts", "turn.txt"), encoding="utf-8").read()

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v4")
STT_KEYTERMS = json.dumps(["din", "rupaye", "sau", "hazaar", "advance", "thekedar", "mazdoori", "haan", "nahi"])
OPENROUTER_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
PLACEHOLDER_KEYS = {"", "your_key_here"}
AUDIO_EXT = {"webm": "audio/webm", "ogg": "audio/ogg", "mp4": "audio/mp4", "m4a": "audio/mp4",
             "wav": "audio/wav", "mp3": "audio/mpeg"}
HEARD_NOTHING = "Sun nahi paya, phir se boliye."
SESSION_TTL_S = 2 * 60 * 60

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
database.init_db()
os.makedirs(TTS_DIR, exist_ok=True)

# Conversations in progress live in memory (one gunicorn worker); finished cases go to SQLite.
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()


def env_key(name):
    value = (os.getenv(name) or "").strip()
    return None if value in PLACEHOLDER_KEYS else value


def missing_keys():
    """What does not work without keys. Typed mode and scripted mode need none."""
    missing = []
    if not env_key("SARVAM_API_KEY"):
        missing.append("SARVAM_API_KEY (voice input and spoken replies)"
                       if not env_key("OPENAI_API_KEY") else "SARVAM_API_KEY (spoken replies)")
    if not (env_key("OPENROUTER_API_KEY") or env_key("OPENAI_API_KEY")):
        missing.append("OPENROUTER_API_KEY (AI understanding; simple rules used instead)")
    return missing


# ---------- speech-to-text: Sarvam Saaras v4 codemix, Whisper fallback ----------

def transcribe_sarvam(path, api_key):
    ext = path.rsplit(".", 1)[-1]
    with open(path, "rb") as f:
        resp = httpx.post(
            SARVAM_STT_URL,
            headers={"api-subscription-key": api_key},
            data={"model": SARVAM_STT_MODEL, "mode": "codemix", "language_code": "hi-IN", "keyterms": STT_KEYTERMS},
            files={"file": (os.path.basename(path), f, AUDIO_EXT.get(ext, "application/octet-stream"))},
            timeout=20,
        )
    resp.raise_for_status()
    return resp.json().get("transcript", "")


def transcribe(path):
    sarvam_key = env_key("SARVAM_API_KEY")
    if sarvam_key:
        try:
            return transcribe_sarvam(path, sarvam_key)
        except Exception as e:
            app.logger.warning("Sarvam STT failed (%s)", type(e).__name__)
    openai_key = env_key("OPENAI_API_KEY")
    if openai_key:
        with open(path, "rb") as f:
            return OpenAI(api_key=openai_key).audio.transcriptions.create(
                model="whisper-1", file=f, prompt="Hinglish: chhe din, saat sau rupaye, paanch sau advance, haan, nahi."
            ).text
    raise RuntimeError("no speech-to-text engine available")


# ---------- understanding: OpenRouter reads ONE number or yes/no; never calculates ----------

def llm_extract(field, question, transcript):
    if openrouter := env_key("OPENROUTER_API_KEY"):
        client, model = OpenAI(api_key=openrouter, base_url=OPENROUTER_URL), OPENROUTER_MODEL
    elif openai_key := env_key("OPENAI_API_KEY"):
        client, model = OpenAI(api_key=openai_key), "gpt-4o-mini"
    else:
        return conversation.local_extract(field, question, transcript)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": PROMPT},
                      {"role": "user", "content": f"Field asked: {field}\nAgent asked: {question}\nWorker said: {transcript}"}],
            temperature=0, max_tokens=120, response_format={"type": "json_object"}, timeout=15,
        )
        answer = json.loads(resp.choices[0].message.content)
        if not isinstance(answer, dict) or answer.get("field") != field:
            return {"field": field, "value": None, "confidence": "low"}
        # Guard: ₹0 only when the worker actually said "nothing" (a bare "haan" is not zero).
        if field in ("advance", "payments") and answer.get("value") == 0 and not answer.get("parts"):
            if not (says_none(transcript) or 0 in parse_amounts(transcript)):
                return {"field": field, "value": None, "confidence": "low"}
        return answer
    except Exception as e:
        app.logger.warning("LLM extraction failed (%s), using local rules", type(e).__name__)
        return conversation.local_extract(field, question, transcript)


# ---------- agent voice ----------

def agent_audio_url(text, scripted):
    # Fixed lines were pre-recorded and checked by sending them back through Saaras: reuse them.
    name = sarvam_tts.audio_name(text)
    if os.path.exists(os.path.join(DEMO_DIR, name)):
        return f"/static/demo/{name}"
    if scripted:  # pre-recorded only: scripted mode makes no network calls
        return None
    name = sarvam_tts.synthesize(text, env_key("SARVAM_API_KEY"), TTS_DIR, app.logger)
    return f"/static/tts/{name}" if name else None


def get_session(session_id):
    now = time.time()
    with SESSIONS_LOCK:
        for sid in [s for s, v in SESSIONS.items() if now - v["touched"] > SESSION_TTL_S]:
            del SESSIONS[sid]
        session = SESSIONS.get(session_id or "")
        if session:
            session["touched"] = now
        return session


def respond(session, reply, scripted, heard=None):
    if reply.pop("save", False) and session["case"]:
        session["case_id"] = database.save_case(session["id"], session["case"])
    return jsonify({
        "session_id": session["id"],
        "agent_text": reply["agent_text"],
        "agent_audio_url": agent_audio_url(reply["agent_text"], scripted),
        "state": reply["state"],
        "done": reply["done"],
        "case": reply["case"],
        "case_id": session["case_id"],
        "heard": heard,
        "parsed": reply.get("parsed"),
        "reasked": reply.get("reasked", False),
        "fallback_text": reply.get("fallback_text", False),
    })


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "Recording too large (max 10 MB)"}), 413


@app.route("/")
def index():
    voice_ok = bool(env_key("SARVAM_API_KEY") or env_key("OPENAI_API_KEY"))
    return render_template("index.html", keys_missing=missing_keys(), voice_ok=voice_ok)


@app.route("/health")
def health():
    return jsonify({"ok": True, "keys_missing": missing_keys()})


@app.route("/turn", methods=["POST"])
def turn():
    """{session_id, audio | text, mode} -> {agent_text, agent_audio_url, state, done, case}.
    No session_id starts a new conversation and returns the agent's opening line."""
    mode = request.form.get("mode", "voice")
    scripted = mode == "scripted"
    session = get_session(request.form.get("session_id"))
    if session is None:
        session = conversation.new_session()
        session["touched"] = time.time()
        with SESSIONS_LOCK:
            SESSIONS[session["id"]] = session
        return respond(session, conversation.opening(session), scripted)

    if request.form.get("event") == "sent":           # worker tapped "Send to contractor"
        reply = conversation.mark_sent(session)
        if reply is None:
            return jsonify({"error": "Nothing to send yet."}), 409
        return respond(session, reply, scripted)

    audio = request.files.get("audio")
    if audio and audio.filename:
        if not (env_key("SARVAM_API_KEY") or env_key("OPENAI_API_KEY")):
            return jsonify({"error": "API key not set: SARVAM_API_KEY. Voice input is off; use typed mode (?mode=text).",
                            "key_missing": True}), 503
        ext = (audio.filename.rsplit(".", 1)[-1] or "webm").lower()
        ext = ext if ext in AUDIO_EXT else "webm"
        fd, path = tempfile.mkstemp(suffix="." + ext)
        os.close(fd)
        try:
            audio.save(path)
            transcript = transcribe(path).strip()
        except Exception as e:
            app.logger.warning("STT failed (%s)", type(e).__name__)
            transcript = ""
        finally:
            os.remove(path)
        if not transcript:
            return jsonify({"session_id": session["id"], "error": HEARD_NOTHING, "stt_failed": True,
                            "state": session["state"]}), 200
    else:
        transcript = (request.form.get("text") or "").strip()[:300]
        if not transcript:
            return jsonify({"session_id": session["id"], "error": "Kuch likhiye ya boliye.",
                            "state": session["state"]}), 400

    extract = conversation.local_extract if scripted else llm_extract
    reply = conversation.step(session, transcript, extract)
    return respond(session, reply, scripted, heard=transcript)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5050)))
