"""PagarSaathi: a Hinglish wage-reconciliation agent. Voice input is Wispr Flow.

The worker dictates with Wispr Flow (an OS-level dictation layer), so the app receives TEXT.
No API key is needed for the core flow. Optional extras, only if keys are set:
- OPENROUTER_API_KEY: an LLM reads the answer instead of the built-in rules (it never calculates)
- SARVAM_API_KEY: Sarvam Bulbul voice for the agent when the browser has no Hindi voice
"""
import json
import os
import threading
import time

import httpx
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

import conversation
import database
import sarvam_tts
from hinglish_numbers import parse_amounts, says_none

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TTS_DIR = os.path.join(BASE_DIR, "static", "tts")      # generated, git-ignored
DEMO_DIR = os.path.join(BASE_DIR, "static", "demo")    # pre-recorded agent lines (free fallback voice)
PROMPT = open(os.path.join(BASE_DIR, "prompts", "turn.txt"), encoding="utf-8").read()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
PLACEHOLDER_KEYS = {"", "your_key_here"}
SESSION_TTL_S = 2 * 60 * 60
RATE_LIMIT, RATE_WINDOW_S = 120, 10 * 60   # turns per visitor per 10 minutes

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)  # real client IP behind Railway's proxy
database.init_db()
os.makedirs(TTS_DIR, exist_ok=True)

# Conversations in progress live in memory (one gunicorn worker); finished cases go to SQLite.
SESSIONS, SESSIONS_LOCK = {}, threading.Lock()
RATE_HITS, RATE_LOCK = {}, threading.Lock()


def env_key(name):
    value = (os.getenv(name) or "").strip()
    return None if value in PLACEHOLDER_KEYS else value


# ---------- optional: OpenRouter reads ONE number or yes/no; never calculates ----------

def llm_extract(field, question, text):
    key = env_key("OPENROUTER_API_KEY")
    if not key:
        return conversation.local_extract(field, question, text)
    try:
        resp = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": OPENROUTER_MODEL, "temperature": 0, "max_tokens": 120,
                  "response_format": {"type": "json_object"},
                  "messages": [{"role": "system", "content": PROMPT},
                               {"role": "user", "content": f"Field asked: {field}\nAgent asked: {question}\nWorker said: {text}"}]},
            timeout=15,
        )
        resp.raise_for_status()
        answer = json.loads(resp.json()["choices"][0]["message"]["content"])
        if not isinstance(answer, dict) or answer.get("field") != field:
            return conversation.local_extract(field, question, text)
        # ₹0 only when the worker actually said "nothing" (a bare "haan" is not zero)
        if field in ("advance", "payments") and answer.get("value") == 0 and not answer.get("parts"):
            if not (says_none(text) or 0 in parse_amounts(text)):
                return {"field": field, "value": None, "confidence": "low"}
        return answer
    except Exception as e:
        app.logger.warning("OpenRouter failed (%s), using built-in rules", type(e).__name__)
        return conversation.local_extract(field, question, text)


# ---------- optional: Sarvam voice, used by the browser only when it has no Hindi voice ----------

def agent_audio_url(agent_text, speak_text, scripted):
    name = sarvam_tts.audio_name(agent_text)
    if os.path.exists(os.path.join(DEMO_DIR, name)):       # pre-recorded, free
        return f"/static/demo/{name}"
    if scripted or not env_key("SARVAM_API_KEY"):
        return None
    name = sarvam_tts.synthesize(speak_text, env_key("SARVAM_API_KEY"), TTS_DIR, app.logger)
    return f"/static/tts/{name}" if name else None


def rate_limited():
    now, ip = time.time(), request.remote_addr or "?"
    with RATE_LOCK:
        if len(RATE_HITS) > 5000:
            RATE_HITS.clear()
        hits = [t for t in RATE_HITS.get(ip, []) if now - t < RATE_WINDOW_S]
        limited = len(hits) >= RATE_LIMIT
        if not limited:
            hits.append(now)
        RATE_HITS[ip] = hits
        return limited


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
        "speak_text": reply["speak_text"],
        "agent_audio_url": agent_audio_url(reply["agent_text"], reply["speak_text"], scripted),
        "state": reply["state"],
        "done": reply["done"],
        "case_data": reply["case"],
        "case_id": session["case_id"],
        "heard": heard,
        "parsed": reply.get("parsed"),
        "reasked": reply.get("reasked", False),
        "needs_assistance": reply.get("needs_assistance", False),
    })


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "key_set": bool(env_key("SARVAM_API_KEY") or env_key("OPENROUTER_API_KEY"))})


@app.route("/turn", methods=["POST"])
def turn():
    """{session_id, text} -> {agent_text, state, done, case_data}. `text` is what the worker
    dictated with Wispr Flow. No session_id starts a new conversation (the agent speaks first)."""
    data = request.get_json(silent=True) or request.form
    scripted = data.get("mode", "") == "scripted"
    if not scripted and rate_limited():
        return jsonify({"error": "Bahut zyada koshish ho gayi. Thodi der baad phir try kijiye."}), 429

    session = get_session(data.get("session_id"))
    if session is None:
        session = conversation.new_session()
        session["touched"] = time.time()
        with SESSIONS_LOCK:
            SESSIONS[session["id"]] = session
        return respond(session, conversation.opening(session), scripted)

    if data.get("event") == "sent":                     # worker tapped "Send to contractor"
        reply = conversation.mark_sent(session)
        if reply is None:
            return jsonify({"error": "Abhi bhejne ke liye kuch nahi hai."}), 409
        return respond(session, reply, scripted)

    text = str(data.get("text") or "").strip()[:500]
    if not text:
        return jsonify({"session_id": session["id"], "state": session["state"],
                        "error": "Jawab khaali hai. Wispr Flow se boliye ya likhiye."}), 400

    extract = conversation.local_extract if scripted else llm_extract
    reply = conversation.step(session, text, extract)
    return respond(session, reply, scripted, heard=text)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5050)))
