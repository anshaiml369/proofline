"""Optional conversational brain for PagarSaathi.

With OPENAI_API_KEY (or OPENROUTER_API_KEY) set, an LLM reads each Wispr Flow message, pulls out
any facts the worker stated, and writes a short natural reply to what they actually said. The LLM
never calculates: Python validates the facts, adds multiple amounts, runs the read-back and does
the maths (wage_math.py). With no key, or if the call fails or is slow, the app uses its built-in
rules instead (conversation.local_extract).
"""
import json
import os
import re

import httpx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT = open(os.path.join(BASE_DIR, "prompts", "agent.txt"), encoding="utf-8").read()
PLACEHOLDER_KEYS = {"", "your_key_here"}
FIELDS = ("days", "rate", "advance", "payments")
TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "8"))


def _key(name):
    value = (os.getenv(name) or "").strip()
    return None if value in PLACEHOLDER_KEYS else value


def providers():
    """(url, key, model) for each configured provider, in order of preference."""
    out = []
    if _key("OPENAI_API_KEY"):
        out.append(("https://api.openai.com/v1/chat/completions", _key("OPENAI_API_KEY"),
                    os.getenv("OPENAI_MODEL", "gpt-4.1-mini")))
    if _key("OPENROUTER_API_KEY"):
        out.append(("https://openrouter.ai/api/v1/chat/completions", _key("OPENROUTER_API_KEY"),
                    os.getenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini")))
    return out


def enabled():
    return bool(providers())


def _int_or_none(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return v if isinstance(v, int) and v >= 0 else None


def _no_questions(text):
    """`say` must not ask anything (the app asks its own question next): drop question sentences."""
    kept = [p for p in re.split(r"(?<=[.!?।])\s+", text) if p and not p.rstrip().endswith(("?", "？"))]
    return " ".join(kept).strip()


def normalise(raw):
    """Keep only well-formed values from the model's JSON. Returns None if it is unusable."""
    if not isinstance(raw, dict):
        return None
    facts_in = raw.get("facts") if isinstance(raw.get("facts"), dict) else {}
    parts_in = raw.get("parts") if isinstance(raw.get("parts"), dict) else {}
    facts = {f: _int_or_none(facts_in.get(f)) for f in FIELDS}
    parts = {}
    for f in ("advance", "payments"):
        p = parts_in.get(f)
        if isinstance(p, list) and len(p) > 1 and all(_int_or_none(x) is not None for x in p):
            parts[f] = [_int_or_none(x) for x in p]
    say = _no_questions(str(raw.get("say") or "").strip()[:300])
    say_hi = _no_questions(str(raw.get("say_hi") or "").strip()[:300]) or say
    ask = str(raw.get("ask") or "").strip()[:200]
    ask_hi = str(raw.get("ask_hi") or "").strip()[:200] or ask
    intent = raw.get("intent") if raw.get("intent") in ("yes", "no", "other") else "other"
    return {"facts": facts, "parts": parts, "intent": intent, "say": say, "say_hi": say_hi,
            "ask": ask, "ask_hi": ask_hi}


def build_user_message(session, question, text):
    known = {f: session["facts"].get(f) for f in FIELDS}
    history = session["turns"][-6:]
    lines = [f"Agent: {t['agent']}\nWorker: {t['worker']}" for t in history if t.get("worker")]
    return (f"Current step: {session['state']}\n"
            f"Facts so far (null = not known yet): {json.dumps(known)}\n"
            f"Recent conversation:\n" + ("\n".join(lines) or "(none)") + "\n"
            f"The app just asked: {question}\n"
            f"Worker's new message: {text}")


def understand(session, question, text, log=None):
    """Ask the LLM about one worker message. Returns the normalised dict, or None to fall back."""
    messages = [{"role": "system", "content": PROMPT},
                {"role": "user", "content": build_user_message(session, question, text)}]
    for url, key, model in providers():
        try:
            resp = httpx.post(url, headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT_S,
                              json={"model": model, "temperature": 0.3, "max_tokens": 300,
                                    "response_format": {"type": "json_object"}, "messages": messages})
            resp.raise_for_status()
            out = normalise(json.loads(resp.json()["choices"][0]["message"]["content"]))
            if out:
                return out
        except Exception as e:  # noqa: BLE001 - any failure means "use the next provider / rules"
            if log:
                log.warning("LLM call failed (%s: %s)", type(e).__name__, url.split("/")[2])
    return None
