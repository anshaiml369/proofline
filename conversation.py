"""PagarSaathi conversation: one question per turn, mandatory read-back, Python does the maths.

START → ASK_DAYS → ASK_RATE → ASK_ADVANCE → ASK_PAYMENTS → CONFIRM → CALCULATE → READ_RESULT
      → ASK_SEND → SHOW_PREVIEW → DONE

Input is TEXT: the worker dictates with Wispr Flow (double-tap Fn on Mac, the Wispr Flow keyboard
on iPhone) and the words land in the text box. This module has no I/O. Each agent line has
`agent_text` (Roman Hinglish, shown on screen) and `speak_text` (Devanagari with digits, which
browser Hindi voices read naturally).
"""
import uuid

from hinglish_numbers import parse_amounts, parse_yes_no, says_none, to_words
from wage_math import calculate_wages, payment_request

START, ASK_DAYS, ASK_RATE, ASK_ADVANCE, ASK_PAYMENTS = "START", "ASK_DAYS", "ASK_RATE", "ASK_ADVANCE", "ASK_PAYMENTS"
CONFIRM, CALCULATE, READ_RESULT, ASK_SEND = "CONFIRM", "CALCULATE", "READ_RESULT", "ASK_SEND"
SHOW_PREVIEW, DONE = "SHOW_PREVIEW", "DONE"

# (shown, spoken)
GREETING = ("Namaste, main PagarSaathi hoon. Bataiye, paise ko lekar kya pareshani hai?",
            "नमस्ते, मैं पगार साथी हूँ। बताइए, पैसों को लेकर क्या परेशानी है?")

# state -> extract_field, question_hi (shown, spoken), simpler re-ask (shown, spoken)
STATES = {
    ASK_DAYS: {
        "extract_field": "days",
        "question_hi": ("Aapne kitne din kaam kiya?", "आपने कितने दिन काम किया?"),
        "simpler": ("Kitne din kaam kiya? Sirf number boliye, jaise chhe din.",
                    "कितने दिन काम किया? सिर्फ़ नंबर बोलिए, जैसे छह दिन।"),
    },
    ASK_RATE: {
        "extract_field": "rate",
        "question_hi": ("Roz ki mazdoori kitni tay hui thi?", "रोज़ की मज़दूरी कितनी तय हुई थी?"),
        "simpler": ("Ek din ke kitne rupaye tay hue the? Jaise saat sau rupaye.",
                    "एक दिन के कितने रुपये तय हुए थे? जैसे सात सौ रुपये।"),
    },
    ASK_ADVANCE: {
        "extract_field": "advance",
        "question_hi": ("Koi advance mila tha pehle?", "कोई एडवांस मिला था पहले?"),
        "simpler": ("Kaam se pehle kitne paise mile the? Nahi mile to boliye nahi.",
                    "काम से पहले कितने पैसे मिले थे? नहीं मिले तो बोलिए नहीं।"),
    },
    ASK_PAYMENTS: {
        "extract_field": "payments",
        "question_hi": ("Ab tak kitne paise mile?", "अब तक कितने पैसे मिले?"),
        "simpler": ("Advance ke alawa ab tak kitne rupaye mile? Kuch nahi mila to boliye nahi.",
                    "एडवांस के अलावा अब तक कितने रुपये मिले? कुछ नहीं मिला तो बोलिए नहीं।"),
    },
    CONFIRM: {
        "extract_field": "confirm",
        "simpler": ("Kya yeh sab sahi hai? Haan ya nahi boliye.", "क्या यह सब सही है? हाँ या नहीं बोलिए।"),
    },
    ASK_SEND: {
        "extract_field": "send",
        "simpler": ("Thekedar ko message bhejna hai? Haan ya nahi boliye.", "ठेकेदार को मैसेज भेजना है? हाँ या नहीं बोलिए।"),
    },
}
NEXT = {START: ASK_DAYS, ASK_DAYS: ASK_RATE, ASK_RATE: ASK_ADVANCE, ASK_ADVANCE: ASK_PAYMENTS, ASK_PAYMENTS: CONFIRM}

# Plausible ranges. Anything outside is treated as a mistake and re-asked.
LIMITS = {"days": (1, 366), "rate": (50, 20_000), "advance": (0, 10_000_000), "payments": (0, 10_000_000)}

RESTART = ("Theek hai, phir se shuru karte hain. Aapne kitne din kaam kiya?",
           "ठीक है, फिर से शुरू करते हैं। आपने कितने दिन काम किया?")
PREVIEW = ("Yeh raha message. Dekh lijiye, phir hara button dabaiye.",
           "यह रहा मैसेज। देख लीजिए, फिर हरा बटन दबाइए।")
NO_SEND = ("Theek hai, message nahi bhejte. Aapka hisaab screen par hai.",
           "ठीक है, मैसेज नहीं भेजते। आपका हिसाब स्क्रीन पर है।")
SENT = ("WhatsApp khul gaya hai. Message bhej dijiye. Dhanyavaad.",
        "व्हाट्सऐप खुल गया है। मैसेज भेज दीजिए। धन्यवाद।")
DONE_LINE = ("Hisaab ho gaya. Dhanyavaad.", "हिसाब हो गया। धन्यवाद।")
ASSIST_NUMBER = ("Koi baat nahi. Kisi saathi ki madad le lijiye. ",
                 "कोई बात नहीं। किसी साथी की मदद ले लीजिए। ")
ASSIST_ZERO = ("Koi baat nahi, abhi ke liye zero maan lete hain. Confirm karte waqt badal sakte hain. ",
               "कोई बात नहीं, अभी के लिए ज़ीरो मान लेते हैं। कन्फ़र्म करते वक़्त बदल सकते हैं। ")


def new_session():
    return {"id": uuid.uuid4().hex, "state": START, "facts": {}, "failures": 0, "case": None,
            "case_id": None, "needs_assistance": [], "turns": [], "last_agent_text": ""}


def _reply(session, line, **extra):
    shown, spoken = line
    out = {"agent_text": shown, "speak_text": spoken, "state": session["state"],
           "done": session["state"] == DONE, "case": session["case"],
           "needs_assistance": bool(session["needs_assistance"])}
    out.update(extra)
    session["last_agent_text"] = shown
    return out


def _join(a, b):
    return (a[0] + b[0], a[1] + b[1])


def opening(session):
    """The agent speaks first."""
    return _reply(session, GREETING)


def readback(f):
    adv = (f"{to_words(f['advance'])} advance", f"{f['advance']} रुपये एडवांस") if f["advance"] else \
          ("koi advance nahi", "कोई एडवांस नहीं")
    paid = (f"{to_words(f['payments'])} paid", f"{f['payments']} रुपये मिले") if f["payments"] else \
           ("abhi tak kuch nahi mila", "अब तक कुछ नहीं मिला")
    return (f"Confirm karta hoon: {to_words(f['days'])} din, {to_words(f['rate'])} roz, {adv[0]}, {paid[0]}. Sahi hai?",
            f"कन्फ़र्म करता हूँ: {f['days']} दिन, {f['rate']} रुपये रोज़, {adv[1]}, {paid[1]}। सही है?")


def result_line(case):
    shown = f"Kul kamaai {to_words(case['expected'])}. Mila {to_words(case['received'])}."
    spoken = f"कुल कमाई {case['expected']} रुपये। मिला {case['received']} रुपये।"
    if case["outstanding"] <= 0:
        return (f"{shown} Hisaab ke hisaab se koi paisa baaki nahi hai.",
                f"{spoken} हिसाब के हिसाब से कोई पैसा बाकी नहीं है।")
    return (f"{shown} Baaki {to_words(case['outstanding'])} rupaye. Thekedar ko payment request bhejun?",
            f"{spoken} बाकी {case['outstanding']} रुपये। ठेकेदार को पेमेंट रिक्वेस्ट भेजूँ?")


def _accept_number(field, answer):
    """Validate the reader's answer for a numeric field. Several amounts come back as `parts`;
    Python adds them here."""
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


def _advance_to(session, state):
    session["state"] = state
    session["failures"] = 0


def _ask(session, state, prefix=None):
    """Move to `state` and ask its question (or the read-back for CONFIRM)."""
    _advance_to(session, state)
    line = readback(session["facts"]) if state == CONFIRM else STATES[state]["question_hi"]
    return _join(prefix, line) if prefix else line


def step(session, text, extract):
    """One worker turn. `extract(field, question, text)` -> {"field", "value", "confidence"[, "parts"]}."""
    state = session["state"]
    text = (text or "").strip()
    session["turns"].append({"agent": session["last_agent_text"], "worker": text, "state": state})

    if state == START:
        return _reply(session, _ask(session, ASK_DAYS))

    if state in (ASK_DAYS, ASK_RATE, ASK_ADVANCE, ASK_PAYMENTS):
        field = STATES[state]["extract_field"]
        value = _accept_number(field, extract(field, session["last_agent_text"], text))
        if value is None:
            session["failures"] += 1
            if session["failures"] == 1:                      # re-ask once, simpler
                return _reply(session, STATES[state]["simpler"], reasked=True)
            # second miss: flag for help and move on where we safely can
            if field not in session["needs_assistance"]:
                session["needs_assistance"].append(field)
            if field in ("advance", "payments"):
                session["facts"][field] = 0
                return _reply(session, _ask(session, NEXT[state], prefix=ASSIST_ZERO),
                              parsed={"field": field, "value": 0, "assumed": True})
            # days and rate cannot be guessed: keep asking, with a hint
            return _reply(session, _join(ASSIST_NUMBER, STATES[state]["simpler"]), reasked=True)
        session["facts"][field] = value
        session["turns"][-1]["value"] = value
        if field in session["needs_assistance"]:
            session["needs_assistance"].remove(field)
        return _reply(session, _ask(session, NEXT[state]), parsed={"field": field, "value": value})

    if state == CONFIRM:
        ok = _accept_bool(extract("confirm", session["last_agent_text"], text))
        if ok is None:
            session["failures"] += 1
            return _reply(session, STATES[CONFIRM]["simpler"], reasked=True)
        if not ok:
            session["facts"] = {}
            session["needs_assistance"] = []
            _advance_to(session, ASK_DAYS)
            return _reply(session, RESTART, restarted=True)
        # CALCULATE → READ_RESULT inside this turn: Python does the maths, the agent reads it out.
        _advance_to(session, CALCULATE)
        f = session["facts"]
        session["case"] = calculate_wages(f["days"], f["rate"], f["advance"], f["payments"])
        _advance_to(session, READ_RESULT)
        line = result_line(session["case"])
        _advance_to(session, DONE if session["case"]["outstanding"] <= 0 else ASK_SEND)
        return _reply(session, line, save=True)

    if state == ASK_SEND:
        ok = _accept_bool(extract("send", session["last_agent_text"], text))
        if ok is None:
            session["failures"] += 1
            return _reply(session, STATES[ASK_SEND]["simpler"], reasked=True)
        if not ok:
            _advance_to(session, DONE)
            return _reply(session, NO_SEND)
        session["case"]["payment_request"] = payment_request(session["case"])
        _advance_to(session, SHOW_PREVIEW)   # preview first, then the Send button
        return _reply(session, PREVIEW, save=True)

    if state == SHOW_PREVIEW:              # waiting for the button tap; words alone don't send
        return _reply(session, PREVIEW)

    return _reply(session, DONE_LINE)


# ---------- LLM path: the agent replies to what the worker actually said ----------

ORDER = (("days", ASK_DAYS), ("rate", ASK_RATE), ("advance", ASK_ADVANCE), ("payments", ASK_PAYMENTS))
WHAT_WRONG = ("Kya galat hai? Din, roz ki mazdoori, advance ya mila hua paisa: sahi number boliye.",
              "क्या गलत है? दिन, रोज़ की मज़दूरी, एडवांस या मिला हुआ पैसा: सही नंबर बोलिए।")


def merge_facts(session, text, understood):
    """Validate and store the facts the LLM heard. Python adds multiple amounts. Returns
    {field: value} for what was stored this turn."""
    stored = {}
    for field, _ in ORDER:
        parts = understood["parts"].get(field)
        value = sum(parts) if parts else understood["facts"].get(field)
        if value is None:
            continue
        # ₹0 only when the worker actually said "nothing" (a bare "haan" is not zero)
        if value == 0 and field in ("advance", "payments") and not (says_none(text) or 0 in parse_amounts(text)):
            continue
        lo, hi = LIMITS[field]
        if lo <= value <= hi and session["facts"].get(field) != value:   # new or changed only
            session["facts"][field] = value
            stored[field] = value
            if field in session["needs_assistance"]:
                session["needs_assistance"].remove(field)
    return stored


def _next_missing(session):
    for field, state in ORDER:
        if field not in session["facts"]:
            return state
    return CONFIRM


def _say(understood):
    """The LLM's short reply, as a (shown, spoken) prefix."""
    if not understood["say"]:
        return None
    return (understood["say"].rstrip() + " ", understood["say_hi"].rstrip() + " ")


def _with(prefix, line):
    return _join(prefix, line) if prefix else line


def step_llm(session, text, understood):
    """One worker turn when the LLM understood the message. Same states and rules as step():
    the read-back is still mandatory and Python still does the maths."""
    state = session["state"]
    text = (text or "").strip()
    session["turns"].append({"agent": session["last_agent_text"], "worker": text, "state": state})
    prefix = _say(understood)

    if state in (START, ASK_DAYS, ASK_RATE, ASK_ADVANCE, ASK_PAYMENTS):
        stored = merge_facts(session, text, understood)
        session["turns"][-1]["facts"] = stored
        extra = {"facts": dict(session["facts"])}
        if stored:
            extra["parsed"] = {"field": list(stored)[-1], "value": list(stored.values())[-1]}
        if state == START and not stored and understood["ask"]:
            _advance_to(session, ASK_DAYS)
            return _reply(session, _with(prefix, (understood["ask"], understood["ask_hi"])), **extra)
        if state == START or stored:
            return _reply(session, _with(prefix, _ask(session, _next_missing(session))), **extra)
        session["failures"] += 1
        field = STATES[state]["extract_field"]
        if session["failures"] == 1:
            question = (understood["ask"], understood["ask_hi"]) if understood["ask"] else STATES[state]["question_hi"]
            return _reply(session, _with(prefix, question), reasked=True, **extra)
        if field not in session["needs_assistance"]:
            session["needs_assistance"].append(field)
        if field in ("advance", "payments") and session["failures"] >= 3:
            session["facts"][field] = 0
            return _reply(session, _ask(session, _next_missing(session), prefix=ASSIST_ZERO),
                          parsed={"field": field, "value": 0, "assumed": True}, facts=dict(session["facts"]))
        return _reply(session, _with(prefix, STATES[state]["simpler"]), reasked=True, **extra)

    if state == CONFIRM:
        stored = merge_facts(session, text, understood)
        if stored:                                   # a correction: read everything back again
            _advance_to(session, CONFIRM)
            return _reply(session, _with(prefix, readback(session["facts"])),
                          facts=dict(session["facts"]), corrected=stored)
        if understood["intent"] == "yes":
            return step(_undo_turn(session), text, lambda *a: {"value": True, "confidence": "high"})
        if understood["intent"] == "no":
            session["failures"] += 1
            if session["failures"] >= 2:
                session["facts"] = {}
                session["needs_assistance"] = []
                _advance_to(session, ASK_DAYS)
                return _reply(session, RESTART, restarted=True, facts={})
            return _reply(session, WHAT_WRONG)
        return _reply(session, _with(prefix, STATES[CONFIRM]["simpler"]), reasked=True)

    if state == ASK_SEND:
        if understood["intent"] in ("yes", "no"):
            ok = understood["intent"] == "yes"
            return step(_undo_turn(session), text, lambda *a: {"value": ok, "confidence": "high"})
        return _reply(session, _with(prefix, STATES[ASK_SEND]["simpler"]), reasked=True)

    if state == SHOW_PREVIEW:
        return _reply(session, _with(prefix, PREVIEW))
    return _reply(session, _with(prefix, DONE_LINE))


def _undo_turn(session):
    """step() records the turn itself; drop the one step_llm() just added."""
    session["turns"].pop()
    return session


def mark_sent(session):
    """The worker tapped "Send to contractor" (SHOW_PREVIEW → DONE)."""
    if session["state"] != SHOW_PREVIEW:
        return None
    _advance_to(session, DONE)
    return _reply(session, SENT)


def local_extract(field, question, text):
    """Rule-based reader for Wispr Flow text. Needs no API key. Handles digits ("700", "₹3,000"),
    Roman Hinglish ("saat sau", "teen hazaar") and Devanagari ("छह दिन")."""
    if field in ("confirm", "send"):
        value = parse_yes_no(text)
        return {"field": field, "value": value, "confidence": "high" if value is not None else "low"}
    amounts = parse_amounts(text)
    if field in ("advance", "payments") and not amounts and says_none(text):
        return {"field": field, "value": 0, "confidence": "high"}
    if len(amounts) == 1:
        return {"field": field, "value": amounts[0], "confidence": "high"}
    if len(amounts) > 1 and field in ("advance", "payments"):
        return {"field": field, "value": None, "parts": amounts, "confidence": "high"}
    return {"field": field, "value": None, "confidence": "low"}
