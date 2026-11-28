"""PagarSaathi: a Hinglish wage-reconciliation agent. Voice input is Wispr Flow.

The worker dictates with Wispr Flow (an OS-level dictation layer), so the app receives TEXT.
No API key is needed for the core flow. Optional extras, only if keys are set:
- OPENAI_API_KEY or OPENROUTER_API_KEY: an LLM dialogue policy decides each next move (ask, follow up,
  clarify, respond to context) from the frame and transcript (agent_llm.py). It never calculates.
- SARVAM_API_KEY: Sarvam Bulbul, a natural Hindi voice for the agent
"""
import logging
import os
import threading
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

import agent_llm
import conversation
import database
import sarvam_tts

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TTS_DIR = os.path.join(BASE_DIR, "static", "tts")      # generated, git-ignored
DEMO_DIR = os.path.join(BASE_DIR, "static", "demo")    # pre-recorded agent lines (free fallback voice)
PLACEHOLDER_KEYS = {"", "your_key_here"}
SESSION_TTL_S = 2 * 60 * 60
RATE_LIMIT, RATE_WINDOW_S = 120, 10 * 60   # turns per visitor per 10 minutes

app = Flask(__name__)
app.logger.setLevel(logging.INFO)   # per-turn timing lines show in Railway logs
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


# ---------- optional: Sarvam voice (natural Hindi); the browser voice is the free fallback ----------

def agent_audio(agent_text, speak_text, scripted):
    """(url, source) for the agent's voice. source: "recorded" (static/demo clip), "sarvam"
    (live Bulbul), or None, which means the browser speaks the line itself."""
    name = sarvam_tts.audio_name(agent_text)
    if os.path.exists(os.path.join(DEMO_DIR, name)):       # pre-recorded, free
        return f"/static/demo/{name}", "recorded"
    if scripted or not env_key("SARVAM_API_KEY"):
        return None, None
    started = time.time()
    name = sarvam_tts.synthesize(speak_text, env_key("SARVAM_API_KEY"), TTS_DIR, app.logger)
    app.logger.info("tts sarvam %s in %.2fs", "ok" if name else "FAILED", time.time() - started)
    return (f"/static/tts/{name}", "sarvam") if name else (None, None)


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


def respond(session, reply, scripted, heard=None, text_source="rules"):
    """text_source: "llm" when the LLM read the message and wrote the reply, "rules" for the
    built-in state machine. Shown in the UI as a provenance badge."""
    if reply.pop("save", False) and session["case"]:
        session["case_id"] = database.save_case(session["id"], session["case"])
    audio_url, audio_source = agent_audio(reply["agent_text"], reply["speak_text"], scripted)
    return jsonify({
        "session_id": session["id"],
        "agent_text": reply["agent_text"],
        "speak_text": reply["speak_text"],
        "agent_audio_url": audio_url,
        "audio_source": audio_source,
        "text_source": text_source,
        "input_source": None if heard is None else ("scripted" if scripted else "typed"),
        "state": reply["state"],
        "done": reply["done"],
        "case_data": reply["case"],
        "case_id": session["case_id"],
        "heard": heard,
        "parsed": reply.get("parsed"),
        "reasked": reply.get("reasked", False),
        "needs_assistance": reply.get("needs_assistance", False),
        "facts": dict(session["facts"]),
        "context_notes": list(session.get("context_notes", [])),
        "policy_source": "llm" if text_source == "llm" else "fallback",
        "action": reply.get("action"),
    })


# Hinglish errors, never a raw traceback or an English error page.
ERRORS = {404: "Yeh page nahi mila.", 405: "Yeh tareeka yahan nahi chalta.",
          413: "Jawab bahut lamba hai. Chhota karke boliye.", 500: "Kuch gadbad ho gayi. Phir se koshish kijiye."}


@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(413)
@app.errorhandler(500)
def error_page(e):
    code = getattr(e, "code", 500) or 500
    message = ERRORS.get(code, ERRORS[500])
    if request.path.startswith(("/turn", "/health")) or request.is_json:
        return jsonify({"error": message}), code
    html = (f'<!doctype html><html lang="hi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>PagarSaathi</title><body style="font:18px system-ui;background:#1e1b4b;color:#f1f5f9;display:grid;place-items:center;'
            f'min-height:100vh;margin:0;text-align:center;padding:16px"><div><p style="font-size:24px;font-weight:700">{message}</p>'
            f'<p><a style="color:#a5b4fc" href="/">PagarSaathi par wapas jaiye</a></p></div></body></html>')
    return html, code


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    llm, voice = agent_llm.enabled(), bool(env_key("SARVAM_API_KEY"))
    return jsonify({"status": "ok",
                    "key_set": llm or voice,
                    "llm": llm,
                    "llm_provider": agent_llm.provider_name(),
                    "voice": voice,
                    "stt": False,        # by design: Wispr Flow does speech-to-text on the device
                    "mode": "live" if (llm or voice) else "keyless",
                    "missing": [k for k, ok in (("OPENAI_API_KEY or OPENROUTER_API_KEY", llm),
                                                ("SARVAM_API_KEY", voice)) if not ok]})


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

    reply, source, started = None, "rules", time.time()
    if not scripted and agent_llm.enabled():
        decision = agent_llm.decide(session, text, app.logger)
        if decision:
            reply, source = conversation.step_policy(session, text, decision), "llm"
    if reply is None:   # no key, scripted demo, or the LLM failed: built-in rules
        reply = conversation.step(session, text, conversation.local_extract)
    guarded = session["turns"][-1].get("guarded", "-") if session["turns"] else "-"
    app.logger.info("turn %s state=%s text=%s action=%s guarded=%s in %.2fs", session["id"][:8], reply["state"],
                    source, reply.get("action", "-"), guarded, time.time() - started)
    return respond(session, reply, scripted, heard=text, text_source=source)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5050)))
