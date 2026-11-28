"""PagarSaathi conversation: one question per turn, mandatory read-back, Python does the maths.

START → ASK_DAYS → ASK_RATE → ASK_ADVANCE → ASK_PAYMENTS → CONFIRM → CALCULATE → READ_RESULT
      → ASK_SEND → SHOW_PREVIEW → SEND_BUTTON → DONE

This module has no I/O. `step(session, transcript, extract)` takes the worker's words and an
`extract(field, question, transcript)` function (the LLM, or the local parser) and returns the
agent's next line. The extractor only reads a number or a yes/no; it never calculates.
"""
import uuid

from legacy.v1_hinglish_numbers import parse_amounts, parse_yes_no, says_none, to_words
from wage_math import calculate_wages, payment_request

START, ASK_DAYS, ASK_RATE, ASK_ADVANCE, ASK_PAYMENTS = "START", "ASK_DAYS", "ASK_RATE", "ASK_ADVANCE", "ASK_PAYMENTS"
CONFIRM, CALCULATE, READ_RESULT, ASK_SEND = "CONFIRM", "CALCULATE", "READ_RESULT", "ASK_SEND"
SHOW_PREVIEW, SEND_BUTTON, DONE = "SHOW_PREVIEW", "SEND_BUTTON", "DONE"

GREETING = "Namaste, main PagarSaathi hoon. Bataiye, paise ko lekar kya pareshani hai?"

# state -> (field, question, simpler re-ask)
QUESTIONS = {
    ASK_DAYS: ("days", "Aapne kitne din kaam kiya?",
               "Kitne din kaam kiya? Sirf number boliye, jaise chhe din."),
    ASK_RATE: ("rate", "Roz ki mazdoori kitni tay hui thi?",
               "Ek din ke kitne rupaye tay hue the? Jaise saat sau rupaye."),
    ASK_ADVANCE: ("advance", "Koi advance mila tha pehle?",
                  "Kaam se pehle kitne paise mile the? Nahi mile to boliye nahi."),
    ASK_PAYMENTS: ("payments", "Ab tak kitne paise mile?",
                   "Advance ke alawa ab tak kitne rupaye mile? Kuch nahi mila to boliye nahi."),
}
NEXT = {START: ASK_DAYS, ASK_DAYS: ASK_RATE, ASK_RATE: ASK_ADVANCE, ASK_ADVANCE: ASK_PAYMENTS, ASK_PAYMENTS: CONFIRM}

# Plausible ranges. Anything outside is treated as a mishearing and re-asked.
LIMITS = {"days": (1, 366), "rate": (50, 20_000), "advance": (0, 10_000_000), "payments": (0, 10_000_000)}

CONFIRM_REASK = "Kya yeh sab sahi hai? Haan ya nahi boliye."
SEND_REASK = "Thekedar ko message bhejna hai? Haan ya nahi boliye."
TYPE_FALLBACK = "Mujhe theek se samajh nahi aaya. Neeche likh kar bataiye."
RESTART = "Theek hai, phir se shuru karte hain. Aapne kitne din kaam kiya?"
NOTHING_DUE = "Hisaab ke hisaab se koi paisa baaki nahi hai."
PREVIEW_LINE = "Yeh raha message. Dekh lijiye, phir hara button dabaiye."
NO_SEND = "Theek hai, message nahi bhejte. Aapka hisaab screen par hai."
DONE_LINE = "Hisaab ho gaya. Dhanyavaad."
SENT_LINE = "WhatsApp khul gaya hai. Message bhej dijiye. Dhanyavaad."


def new_session():
    return {"id": uuid.uuid4().hex, "state": START, "facts": {}, "failures": 0,
            "case": None, "case_id": None, "text_mode": False, "turns": []}


def opening(session):
    """The agent speaks first."""
    return _reply(session, GREETING)


def _reply(session, text, **extra):
    out = {"agent_text": text, "state": session["state"], "done": session["state"] == DONE,
           "case": session["case"], "fallback_text": False}
    out.update(extra)
    session["last_agent_text"] = text
    return out


def readback(facts):
    adv = f"{to_words(facts['advance'])} advance" if facts["advance"] else "koi advance nahi"
    paid = f"{to_words(facts['payments'])} paid" if facts["payments"] else "abhi tak kuch nahi mila"
    return (f"Confirm karta hoon: {to_words(facts['days'])} din, {to_words(facts['rate'])} roz, "
            f"{adv}, {paid}. Sahi hai?")


def result_line(case):
    head = f"Kul kamaai {to_words(case['expected'])}. Mila {to_words(case['received'])}."
    if case["outstanding"] <= 0:
        return f"{head} {NOTHING_DUE}"
    return f"{head} Baaki {to_words(case['outstanding'])} rupaye. Thekedar ko payment request bhejun?"


def _accept_number(field, answer):
    """Validate the extractor's answer for a numeric field. Returns an int or None.

    Several amounts ("do hazaar aur ek hazaar") come back as `parts`; Python adds them here,
    never the LLM.
    """
    if answer.get("confidence") != "high":
        return None
    parts = answer.get("parts")
    if parts:
        if not all(isinstance(p, int) and not isinstance(p, bool) and p >= 0 for p in parts):
            return None
        value = sum(parts)
    else:
        value = answer.get("value")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    lo, hi = LIMITS[field]
    return value if lo <= value <= hi else None


def _accept_bool(answer):
    value = answer.get("value")
    return value if isinstance(value, bool) and answer.get("confidence") == "high" else None


def _failed(session, simpler):
    """First miss: re-ask the same question in simpler words. Second miss: ask for typed input."""
    session["failures"] += 1
    if session["failures"] >= 2:
        session["text_mode"] = True
        return _reply(session, f"{TYPE_FALLBACK} {simpler}", fallback_text=True, reasked=True)
    return _reply(session, simpler, reasked=True)


def _advance_to(session, state):
    session["state"] = state
    session["failures"] = 0


def step(session, transcript, extract):
    """One worker turn. `extract(field, question, transcript)` -> {"field", "value", "confidence"[, "parts"]}."""
    state = session["state"]
    transcript = (transcript or "").strip()
    question = session.get("last_agent_text", "")
    session["turns"].append({"agent": question, "worker": transcript, "state": state})

    if state == START:
        _advance_to(session, ASK_DAYS)
        return _reply(session, QUESTIONS[ASK_DAYS][1])

    if state in QUESTIONS:
        field, _, simpler = QUESTIONS[state]
        answer = extract(field, question, transcript)
        value = _accept_number(field, answer)
        if value is None:
            return _failed(session, simpler)
        session["facts"][field] = value
        session["turns"][-1]["value"] = value
        _advance_to(session, NEXT[state])
        if session["state"] == CONFIRM:
            return _reply(session, readback(session["facts"]), parsed={"field": field, "value": value})
        return _reply(session, QUESTIONS[session["state"]][1], parsed={"field": field, "value": value})

    if state == CONFIRM:
        ok = _accept_bool(extract("confirm", question, transcript))
        if ok is None:
            return _failed(session, CONFIRM_REASK)
        if not ok:
            session["facts"] = {}
            _advance_to(session, ASK_DAYS)
            return _reply(session, RESTART)
        # CALCULATE → READ_RESULT happen inside this turn: Python does the maths, the agent reads it.
        _advance_to(session, CALCULATE)
        f = session["facts"]
        session["case"] = calculate_wages(f["days"], f["rate"], f["advance"], f["payments"])
        _advance_to(session, READ_RESULT)
        line = result_line(session["case"])
        if session["case"]["outstanding"] <= 0:
            _advance_to(session, DONE)
            return _reply(session, line, save=True)
        _advance_to(session, ASK_SEND)
        return _reply(session, line, save=True)

    if state == ASK_SEND:
        ok = _accept_bool(extract("send", question, transcript))
        if ok is None:
            return _failed(session, SEND_REASK)
        if not ok:
            _advance_to(session, DONE)
            return _reply(session, NO_SEND)
        # SHOW_PREVIEW: the message is on screen first; the browser reveals the button after it (SEND_BUTTON).
        _advance_to(session, SHOW_PREVIEW)
        session["case"]["payment_request"] = payment_request(session["case"])
        _advance_to(session, SEND_BUTTON)
        return _reply(session, PREVIEW_LINE, save=True)

    if state == SEND_BUTTON:   # waiting for the button tap (mark_sent); words alone don't send
        return _reply(session, PREVIEW_LINE)

    return _reply(session, DONE_LINE)


def mark_sent(session):
    """The worker tapped "Send to contractor" (SEND_BUTTON → DONE)."""
    if session["state"] != SEND_BUTTON:
        return None
    _advance_to(session, DONE)
    return _reply(session, SENT_LINE)


def local_extract(field, question, transcript):
    """Rule-based reader used when no LLM key is set, when the LLM call fails, and in scripted mode."""
    if field in ("confirm", "send"):
        value = parse_yes_no(transcript)
        return {"field": field, "value": value, "confidence": "high" if value is not None else "low"}
    amounts = parse_amounts(transcript)
    if field in ("advance", "payments") and not amounts and says_none(transcript):
        return {"field": field, "value": 0, "confidence": "high"}
    if len(amounts) == 1:
        return {"field": field, "value": amounts[0], "confidence": "high"}
    if len(amounts) > 1 and field in ("advance", "payments"):
        return {"field": field, "value": None, "parts": amounts, "confidence": "high"}
    return {"field": field, "value": None, "confidence": "low"}
