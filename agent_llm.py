"""Optional LLM dialogue policy for PagarSaathi.

With OPENAI_API_KEY (or OPENROUTER_API_KEY) set, an LLM decides each next move of the conversation:
it reads the frame (known numbers, notes the worker volunteered, what is still open, the last
question), the whole transcript and the latest Wispr Flow message, and returns an action, the line
to say, any numbers the worker stated and any new context. The LLM never calculates and never
skips the read-back: conversation.step_policy() validates every number against the worker's own
words, adds multiple amounts, guards the line it says, and Python does the maths (wage_math.py).
With no key, or if the call fails or is slow, the app uses its built-in rules instead.
"""
import concurrent.futures
import json
import os
import time

import httpx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT = open(os.path.join(BASE_DIR, "prompts", "policy.txt"), encoding="utf-8").read()
PLACEHOLDER_KEYS = {"", "your_key_here"}
SLOTS = ("days", "rate", "advance", "payments")
ACTIONS = ("ask_slot", "follow_up", "clarify", "acknowledge_context", "handle_off_topic", "rephrase", "conclude")
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


def provider_name():
    """Which provider is tried first: "openai", "openrouter", or None."""
    first = providers()[:1]
    return ("openai" if "openai.com" in first[0][0] else "openrouter") if first else None


def _int_or_none(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, str) and v.strip().isdigit():
        v = int(v.strip())
    return v if isinstance(v, int) and v >= 0 else None


def _value(v):
    """An int, or a list of 2+ ints (several amounts Python will add), else None."""
    if isinstance(v, list):
        parts = [_int_or_none(x) for x in v]
        if not parts or any(p is None for p in parts):
            return None
        return parts if len(parts) > 1 else parts[0]
    return _int_or_none(v)


def _text(v, limit):
    return str(v).strip()[:limit] if isinstance(v, str) else ""


def normalise(raw):
    """Keep only well-formed fields of the model's decision. Returns None if it is unusable."""
    if not isinstance(raw, dict):
        return None
    items = raw.get("extracted")
    items = [items] if isinstance(items, dict) else items if isinstance(items, list) else []
    extracted = []
    for it in items:
        if isinstance(it, dict) and it.get("slot") in SLOTS:
            value = _value(it.get("value"))
            if value is not None:
                extracted.append({"slot": it["slot"], "value": value,
                                  "confidence": "high" if it.get("confidence") == "high" else "low"})
    agent_text = _text(raw.get("agent_text"), 300)
    context = _text(raw.get("context_delta"), 120)
    return {
        "action": raw.get("action") if raw.get("action") in ACTIONS else "ask_slot",
        "target_slot": raw.get("target_slot") if raw.get("target_slot") in SLOTS else None,
        "agent_text": agent_text,
        "agent_text_hi": _text(raw.get("agent_text_hi"), 300) or agent_text,
        "extracted": extracted,
        "context_delta": None if context.lower() in ("", "null", "none") else context,
        "intent": raw.get("intent") if raw.get("intent") in ("yes", "no", "other") else "other",
    }


def frame(session):
    """What the policy sees about the conversation so far."""
    known = {s: session["facts"].get(s) for s in SLOTS}
    return {"step": session["state"], "known": known,
            "missing": [s for s in SLOTS if known[s] is None],
            "context_notes": session.get("context_notes", []),
            "unresolved": session.get("unresolved", []),
            "last_question": session.get("last_agent_text", ""),
            "turn_count": session.get("turn_count", 0),
            "language": session.get("language", "hi")}


def build_user_message(session, text):
    lines = []
    for t in session["turns"][-20:]:
        lines.append(f"Agent: {t['agent']}")
        if t.get("worker"):
            lines.append(f"Worker: {t['worker']}")
    return (f"FRAME: {json.dumps(frame(session), ensure_ascii=False)}\n"
            "CONVERSATION:\n" + ("\n".join(lines) or "(none yet)") + "\n"
            f"Agent (last question): {session.get('last_agent_text', '')}\n"
            f"Worker (latest message): {text}")


_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _call(url, key, model, messages):
    resp = httpx.post(url, headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT_S,
                      json={"model": model, "temperature": 0.4, "max_tokens": 400,
                            "response_format": {"type": "json_object"}, "messages": messages})
    resp.raise_for_status()
    return normalise(json.loads(resp.json()["choices"][0]["message"]["content"]))


def decide(session, text, log=None):
    """Ask the policy for the next move. Returns the normalised decision, or None to fall back.
    TIMEOUT_S is a hard wall-clock limit for the whole turn, across providers (httpx's own timeout
    is per network step, so a slow server could otherwise hold the worker for much longer)."""
    messages = [{"role": "system", "content": PROMPT},
                {"role": "user", "content": build_user_message(session, text)}]
    deadline = time.monotonic() + TIMEOUT_S
    for url, key, model in providers():
        left = deadline - time.monotonic()
        if left <= 0.5:
            break
        try:
            out = _POOL.submit(_call, url, key, model, messages).result(timeout=left)
            if out and out["agent_text"]:
                return out
        except Exception as e:  # noqa: BLE001 - any failure means "use the next provider / rules"
            status = getattr(getattr(e, "response", None), "status_code", None)
            # error class, HTTP status and host only: never the key or the response body
            session["llm_error"] = f"{type(e).__name__}{f' {status}' if status else ''} @ {url.split('/')[2]}"
            if log:
                log.warning("LLM call failed (%s)", session["llm_error"])
    return None
