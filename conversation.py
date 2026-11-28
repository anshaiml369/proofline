"""PagarSaathi conversation: one question per turn, mandatory read-back, Python does the maths.

START → ASK_DAYS → ASK_RATE → ASK_ADVANCE → ASK_PAYMENTS → CONFIRM → CALCULATE → READ_RESULT
      → ASK_SEND → SHOW_PREVIEW → DONE

Input is TEXT: the worker dictates with Wispr Flow (double-tap Fn on Mac, the Wispr Flow keyboard
on iPhone) and the words land in the text box. This module has no I/O. Each agent line has
`agent_text` (Roman Hinglish, shown on screen) and `speak_text` (Devanagari with digits, which
browser Hindi voices read naturally).
"""
import re
import unicodedata
import uuid

from hinglish_numbers import amount_groups, parse_amounts, parse_yes_no, says_none, says_nothing, to_words, tokens
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
        "example": ("Hafte ke hisaab se sochiye: jis hafte ka paisa baaki hai, usme kitne din kaam par gaye?",
                    "हफ़्ते के हिसाब से सोचिए: जिस हफ़्ते का पैसा बाकी है, उसमें कितने दिन काम पर गए?"),
    },
    ASK_RATE: {
        "extract_field": "rate",
        "question_hi": ("Roz ki mazdoori kitni tay hui thi?", "रोज़ की मज़दूरी कितनी तय हुई थी?"),
        "simpler": ("Ek din ke kitne rupaye tay hue the? Jaise saat sau rupaye.",
                    "एक दिन के कितने रुपये तय हुए थे? जैसे सात सौ रुपये।"),
        "example": ("Thekedar ne ek din ka kitna bola tha? Sirf rupaye boliye.",
                    "ठेकेदार ने एक दिन का कितना बोला था? सिर्फ़ रुपये बोलिए।"),
    },
    ASK_ADVANCE: {
        "extract_field": "advance",
        "question_hi": ("Koi advance mila tha pehle?", "कोई एडवांस मिला था पहले?"),
        "simpler": ("Kaam se pehle kitne paise mile the? Nahi mile to boliye nahi.",
                    "काम से पहले कितने पैसे मिले थे? नहीं मिले तो बोलिए नहीं।"),
        "example": ("Kaam shuru hone se pehle ya beech mein, mazdoori mein se katne wale kitne paise liye the?",
                    "काम शुरू होने से पहले या बीच में, मज़दूरी में से कटने वाले कितने पैसे लिए थे?"),
    },
    ASK_PAYMENTS: {
        "extract_field": "payments",
        "question_hi": ("Ab tak kitne paise mile?", "अब तक कितने पैसे मिले?"),
        "simpler": ("Advance ke alawa ab tak kitne rupaye mile? Kuch nahi mila to boliye nahi.",
                    "एडवांस के अलावा अब तक कितने रुपये मिले? कुछ नहीं मिला तो बोलिए नहीं।"),
        "example": ("Is kaam ke liye haath mein kitne rupaye aa chuke hain? Kuch nahi aaya to boliye kuch nahi.",
                    "इस काम के लिए हाथ में कितने रुपये आ चुके हैं? कुछ नहीं आया तो बोलिए कुछ नहीं।"),
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
            "case_id": None, "needs_assistance": [], "turns": [], "last_agent_text": "",
            # the frame the dialogue policy reads, beyond the four numbers
            "context_notes": [], "unresolved": [], "turn_count": 0, "misses": {}}


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
    if case["received"]:
        shown = f"Kul kamaai {to_words(case['expected'])}. Mila {to_words(case['received'])}."
        spoken = f"कुल कमाई {case['expected']} रुपये। मिला {case['received']} रुपये।"
    else:
        shown = f"Kul kamaai {to_words(case['expected'])}. Abhi tak kuch nahi mila."
        spoken = f"कुल कमाई {case['expected']} रुपये। अभी तक कुछ नहीं मिला।"
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
        stored = _merge_tagged(session, text)           # "6 din, 700 roz" in the first message counts
        ctx = rules_context(None, text)                 # "pichhle hafte bimar tha": say something human
        for note in rules_notes(text):
            _note(session, note)
        line = _ask(session, _next_missing(session))
        return _reply(session, _join(ctx["line"], line) if ctx and ctx["line"] else line,
                      **({"facts": dict(session["facts"])} if stored else {}))

    if state in (ASK_DAYS, ASK_RATE, ASK_ADVANCE, ASK_PAYMENTS):
        field = STATES[state]["extract_field"]
        ctx = rules_context(field, text)
        if ctx:
            _note(session, ctx["note"])
        value = None if ctx and ctx["block"] else _accept_number(field, extract(field, session["last_agent_text"], text))
        if value is None:
            if ctx and ctx["block"]:                          # "3 saal" / "ek hafta" is not a day count: ask
                return _reply(session, ctx["line"], reasked=True, context=True)
            if ctx and ctx["line"]:                           # hospital, loan...: respond, then ask again
                return _reply(session, _join(ctx["line"], STATES[state]["question_hi"]), context=True)
            session["failures"] += 1
            if session["failures"] == 1:                      # re-ask once, simpler
                return _reply(session, _reask(session, state), reasked=True)
            # second miss: flag for help and move on where we safely can
            if field not in session["needs_assistance"]:
                session["needs_assistance"].append(field)
            if field in ("advance", "payments"):
                session["facts"][field] = 0
                return _reply(session, _ask(session, _next_missing(session), prefix=ASSIST_ZERO),
                              parsed={"field": field, "value": 0, "assumed": True})
            # days and rate cannot be guessed: keep asking, a different way each time
            return _reply(session, _reask(session, state), reasked=True)
        session["facts"][field] = value
        session["turns"][-1]["value"] = value
        if field in session["needs_assistance"]:
            session["needs_assistance"].remove(field)
        _merge_tagged(session, text, skip=field)         # other facts said in the same breath
        nxt = _ask(session, _next_missing(session))
        return _reply(session, _join(ctx["line"], nxt) if ctx and ctx["line"] else nxt,
                      parsed={"field": field, "value": value}, facts=dict(session["facts"]))

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


# ---------- LLM dialogue policy: the LLM decides the next move, Python guards it ----------

ORDER = (("days", ASK_DAYS), ("rate", ASK_RATE), ("advance", ASK_ADVANCE), ("payments", ASK_PAYMENTS))
ASK_STATE = dict(ORDER)
WHAT_WRONG = ("Kya galat hai? Din, roz ki mazdoori, advance ya mila hua paisa: sahi number boliye.",
              "क्या गलत है? दिन, रोज़ की मज़दूरी, एडवांस या मिला हुआ पैसा: सही नंबर बोलिए।")
SORRY = ("Maaf kijiye, theek se samajh nahi aaya. ", "माफ़ कीजिए, ठीक से समझ नहीं आया। ")
STALL_LIMIT = 3        # one ask + two rephrases of the same number with nothing new -> Python moves on
TURN_CAP = 12          # worker turns; after this the agent stops collecting and points to help
HELPLINE = ("Abhi poora hisaab nahi ban paaya. Jo aapne bataya woh screen par hai. Kisi saathi, union ya "
            "India Labourline 1800 1800 999 se madad lijiye.",
            "अभी पूरा हिसाब नहीं बन पाया। जो आपने बताया वह स्क्रीन पर है। किसी साथी, यूनियन या "
            "इंडिया लेबरलाइन 1800 1800 999 से मदद लीजिए।")
_NO_ADVANCE = re.compile(r"\b(advance|एडवांस)\s+(nahi|nahin|nai|no|नहीं|नही)\b|\bno\s+advance\b|"
                         r"\b(koi|kuch)\s+advance\s+(nahi|nahin|नहीं)\b", re.I)


def _next_missing(session):
    for field, state in ORDER:
        if field not in session["facts"]:
            return state
    return CONFIRM


def _with(prefix, line):
    return _join(prefix, line) if prefix else line


def _norm(s):
    return " ".join("".join(ch for ch in s.lower() if ch.isalnum() or ch.isspace()).split())


def _note(session, note):
    if note and note.lower() not in (n.lower() for n in session["context_notes"]):
        session["context_notes"] = (session["context_notes"] + [note])[-6:]


def _recently_said(session, text):
    """Numbers in the worker's latest message and the one before it ("2000 ka loan" ... "haan,
    woh kaat liya" makes 2000 the advance)."""
    earlier = [t["worker"] for t in session["turns"][-2:-1] if t.get("worker")]
    return set(parse_amounts(text)).union(*(parse_amounts(w) for w in earlier))


def accept_extracted(session, text, decision):
    """Validate the numbers the policy heard. A number counts only if the worker actually said
    it (in this message or the one before), is in a plausible range, and (for ₹0) the worker said "nothing".
    Python adds multiple amounts. Returns (stored {slot: value}, rejected [slot])."""
    heard = _recently_said(session, text)
    stored, rejected = {}, []
    moving_on = decision["action"] in ("ask_slot", "conclude")
    for item in decision["extracted"]:
        slot, value = item["slot"], item["value"]
        if item["confidence"] != "high" and not moving_on:
            session["unresolved"] = sorted(set(session["unresolved"]) | {slot})   # e.g. two different rates
            continue
        # "shayad 600" and the policy moves on: keep it; the mandatory read-back will check it
        parts = value if isinstance(value, list) else [value]
        ok = all(p in heard or (p == 0 and says_nothing(text)) for p in parts)
        total = sum(parts)                       # Python adds, never the model
        lo, hi = LIMITS[slot]
        if total == 0 and slot in ("days", "rate"):
            ok = False
        if not ok or not lo <= total <= hi:
            rejected.append(slot)
            continue
        if session["facts"].get(slot) != total:  # new or changed only
            session["facts"][slot] = stored[slot] = total
        if slot in session["needs_assistance"]:
            session["needs_assistance"].remove(slot)
        session["unresolved"] = [u for u in session["unresolved"] if u != slot]
    return stored, rejected


def guard_line(session, text, decision):
    """The policy's line, if it is safe to say: not empty, not a word-for-word repeat of the last
    question, and no amount the worker did not say (so never a total or an amount owed)."""
    shown, spoken = decision["agent_text"], decision["agent_text_hi"]
    if not shown or _norm(shown) in {_norm(a) for a in _last_agent_lines(session)}:
        return None
    allowed = _recently_said(session, text) | set(session["facts"].values())
    digits = {int(d) for d in re.findall(r"\d+", (shown + " " + spoken).replace(",", ""))}
    # number words: only amounts of 100+ count ("saath" is also "together", not just 60)
    words = {n for n in parse_amounts(shown) + parse_amounts(spoken) if n >= 100}
    if any(n > 31 and n not in allowed for n in digits | words):
        return None
    return (shown, spoken)


def _last_agent_lines(session, n=2):
    """The agent's last n lines before this turn (the repetition detector compares against them)."""
    lines = [t["agent"] for t in session["turns"][-n:] if t.get("agent")]
    return lines or [session["last_agent_text"]]


def _question_of(line):
    parts = [p for p in re.split(r"(?<=[.!?।])\s+", line.strip()) if p]
    return _norm(parts[-1]) if parts else ""


def _statements(line):
    """The line without its question sentences: an acknowledgement to put before the read-back."""
    if not line:
        return None
    keep = [[p for p in re.split(r"(?<=[.!?।])\s+", x.strip()) if p and "?" not in p
             and not any(w in p.lower() for w in _PROMPT_WORDS)] for x in line]
    shown, spoken = " ".join(keep[0]), " ".join(keep[1])
    return (shown + " ", (spoken or shown) + " ") if shown and len(shown) <= 200 else None


def backstop(session, text, decision):
    """Facts the policy missed but the worker clearly stated with a fact word ("rate 700",
    "advance nahi"). Only for numbers still missing that the policy did not mention at all."""
    if decision["action"] not in ("ask_slot", "conclude"):
        return {}                                # the policy is clarifying: trust it, do not guess
    mentioned = {item["slot"] for item in decision["extracted"]}
    stored = {}
    for field, value in tagged_facts(text).items():
        lo, hi = LIMITS[field]
        if field not in mentioned and field not in session["facts"] and lo <= value <= hi:
            session["facts"][field] = stored[field] = value
    if "advance" not in mentioned and "advance" not in session["facts"] and _NO_ADVANCE.search(text):
        session["facts"]["advance"] = stored["advance"] = 0
    return stored


def _reask(session, state):
    """A re-ask that changes with each miss and is never the same words as the last line."""
    options = [STATES[state]["simpler"], STATES[state].get("example"), _join(ASSIST_NUMBER, STATES[state]["simpler"]),
               STATES[state].get("question_hi")]
    options = [o for o in options if o and _norm(o[0]) != _norm(session["last_agent_text"])]
    return options[max(session["failures"] - 1, 0) % len(options)]


_PROMPT_WORDS = ("bataiye", "batayein", "bataye", "boliye", "batao", "bolo")


def _ends_with_question(line):
    """The line already asks something: a "?" or a closing "bataiye" / "boliye"."""
    last = re.split(r"(?<=[.!?।])\s+", line[0].strip())[-1].lower()
    return "?" in line[0] or any(w in last for w in _PROMPT_WORDS)


def step_policy(session, text, decision):
    """One worker turn driven by the LLM dialogue policy. The policy chooses what to say and
    which number to go after; Python keeps the frame, accepts only numbers the worker said,
    breaks loops, forces the read-back before any maths, and does the maths."""
    state = session["state"]
    text = (text or "").strip()
    session["turns"].append({"agent": session["last_agent_text"], "worker": text, "state": state,
                             "action": decision["action"]})
    session["turn_count"] += 1
    if decision["context_delta"]:
        _note(session, decision["context_delta"])
    stored, rejected = accept_extracted(session, text, decision)
    if state != CONFIRM:
        stored.update(backstop(session, text, decision))
    session["turns"][-1]["facts"] = stored
    line = None if rejected else guard_line(session, text, decision)
    if line is None:
        session["turns"][-1]["guarded"] = "rejected number" if rejected else "unsafe or repeated line"
    extra = {"facts": dict(session["facts"]), "action": decision["action"]}
    if stored:
        extra["parsed"] = {"field": list(stored)[-1], "value": list(stored.values())[-1]}

    if state in (START, ASK_DAYS, ASK_RATE, ASK_ADVANCE, ASK_PAYMENTS):
        progressed = bool(stored or decision["context_delta"])
        session["failures"] = 0 if progressed else session["failures"] + 1
        asked = STATES[state]["extract_field"] if state in STATES else None
        if asked and asked not in session["facts"] and not decision["context_delta"]:
            session["misses"][asked] = session["misses"].get(asked, 0) + 1
        nxt = _next_missing(session)
        if nxt == CONFIRM:                      # all four known: the read-back is Python's, always
            return _reply(session, _with(_statements(line), _ask(session, CONFIRM)), **extra)
        if session["turn_count"] >= TURN_CAP:   # hard cap: stop collecting, point to help
            _advance_to(session, DONE)
            session["unresolved"] = sorted(set(session["unresolved"]) | {f for f, _ in ORDER if f not in session["facts"]})
            return _reply(session, HELPLINE, **extra, capped=True)
        prefix = None
        if asked and asked not in session["facts"] and session["misses"].get(asked, 0) >= STALL_LIMIT:
            # asked once and rephrased twice with nothing new: flag it and move on
            if asked not in session["needs_assistance"]:
                session["needs_assistance"].append(asked)
            session["unresolved"] = sorted(set(session["unresolved"]) | {asked})
            if asked in ("advance", "payments"):
                session["facts"][asked] = 0      # shown as "maana" (assumed); the read-back checks it
                session["failures"] = 0
                if _next_missing(session) == CONFIRM:
                    return _reply(session, _ask(session, CONFIRM, prefix=ASSIST_ZERO), action="python_assist",
                                  parsed={"field": asked, "value": 0, "assumed": True}, facts=dict(session["facts"]))
                extra.update(facts=dict(session["facts"]), action="python_assist",
                             parsed={"field": asked, "value": 0, "assumed": True})
                prefix = ASSIST_ZERO
            else:
                prefix = ASSIST_NUMBER           # days or rate cannot be guessed: other numbers first
            line = None
        open_ = [st for f, st in ORDER if f not in session["facts"] and session["misses"].get(f, 0) < STALL_LIMIT]
        nxt = open_[0] if open_ else _next_missing(session)
        target = decision["target_slot"]
        if prefix is None and target in ASK_STATE and ASK_STATE[target] in open_:
            nxt = ASK_STATE[target]             # the policy may choose which open number to go after
        field = STATES[nxt]["extract_field"]
        if prefix:
            moved = nxt != state
            _advance_to(session, nxt)
            q = STATES[nxt]["question_hi"] if moved else _reask(session, nxt)
            return _reply(session, _join(prefix, q), reasked=not moved, moved_on=asked, **extra)
        session["state"] = nxt
        ctx = rules_context(field, text) if line is None and not rejected else None
        if ctx and ctx["line"]:                 # policy line unusable, but the rules know this one
            return _reply(session, ctx["line"] if ctx["block"] else _join(ctx["line"], STATES[nxt]["question_hi"]),
                          guarded=True, **extra)
        if line and not progressed and _question_of(line[0]) in {_question_of(a) for a in _last_agent_lines(session)}:
            line = None                         # same question again with nothing new: rephrase instead
            session["turns"][-1]["guarded"] = "repeated question"
        if line is None:                        # unsafe or repeated line: Python's own question
            prefix = SORRY if rejected else None
            q = STATES[nxt]["question_hi"] if not session["failures"] else _reask(session, nxt)
            return _reply(session, _with(prefix, q), reasked=bool(session["failures"]), guarded=True, **extra)
        if not _ends_with_question(line):       # every collecting turn moves the hisaab forward
            line = _join(_space(line), STATES[nxt]["question_hi"])
        return _reply(session, line, reasked=bool(session["failures"]), **extra)

    if state == CONFIRM:
        if stored:                               # a correction: read everything back again
            _advance_to(session, CONFIRM)
            return _reply(session, readback(session["facts"]), corrected=stored, **extra)
        rules_yes = parse_yes_no(text)
        if decision["intent"] == "yes" and rules_yes is not False:
            return step(_undo_turn(session), text, lambda *a: {"value": True, "confidence": "high"})
        if decision["intent"] == "no":
            session["failures"] += 1
            if session["failures"] >= 2:
                session["facts"] = {}
                session["needs_assistance"] = []
                _advance_to(session, ASK_DAYS)
                return _reply(session, RESTART, restarted=True, facts={})
            return _reply(session, WHAT_WRONG, **extra)   # never guess which number is wrong
        session["failures"] += 1
        reask = STATES[CONFIRM]["simpler"]
        return _reply(session, _join(_space(line), reask) if line and not _ends_with_question(line)
                      else line or reask, reasked=True, **extra)

    if state == ASK_SEND:
        if decision["intent"] in ("yes", "no"):
            ok = decision["intent"] == "yes"
            return step(_undo_turn(session), text, lambda *a: {"value": ok, "confidence": "high"})
        reask = STATES[ASK_SEND]["simpler"]
        return _reply(session, _join(_space(line), reask) if line and not _ends_with_question(line)
                      else line or reask, reasked=True, **extra)

    if state == SHOW_PREVIEW:
        return _reply(session, PREVIEW)
    return _reply(session, DONE_LINE)


def _space(line):
    return (line[0].rstrip() + " ", line[1].rstrip() + " ") if line else None


def _undo_turn(session):
    """step() records the turn itself; drop the one step_policy() just added."""
    session["turns"].pop()
    session["turn_count"] -= 1
    return session


def mark_sent(session):
    """The worker tapped "Send to contractor" (SHOW_PREVIEW → DONE)."""
    if session["state"] != SHOW_PREVIEW:
        return None
    _advance_to(session, DONE)
    return _reply(session, SENT)


# Words that say which fact an amount belongs to: "6 din", "700 roz", "500 advance", "3000 mile".
_TAGS = {
    "days": {"din", "dino", "dinon", "day", "days", "दिन", "दिनों"},
    "rate": {"roz", "roj", "rozana", "daily", "rate", "dihadi", "dihaadi", "mazdoori", "per", "रोज़", "रोज",
             "रोजाना", "रोज़ाना", "दिहाड़ी", "मज़दूरी", "मजदूरी"},
    "advance": {"advance", "advanced", "peshgi", "एडवांस", "पेशगी"},
    "payments": {"mile", "mila", "mili", "milaa", "paid", "received", "diye", "diya", "payment", "मिले", "मिला",
                 "मिली", "दिए", "दिया"},
}
_TAGS = {f: {unicodedata.normalize("NFC", w) for w in ws} for f, ws in _TAGS.items()}


def _tag(before, after):
    """Which fact an amount belongs to, from the nearest words after it, then before it."""
    for w in tuple(after) + tuple(before):
        for field, words in _TAGS.items():
            if w in words:
                return field
    return None


def tagged_facts(text):
    """{field: value} for amounts clearly tied to a fact word. Two different values for the same
    fact cancel out (unclear), and Python never adds them here."""
    found = {}
    for value, before, after in amount_groups(text):
        if after and after[0] in _PERIOD_KEYS:
            continue                      # "teen saal", "do hafte": a duration, not days or money
        field = _tag(before, after)
        if field:
            found.setdefault(field, set()).add(value)
    return {f: vals.pop() for f, vals in found.items() if len(vals) == 1}


def _merge_tagged(session, text, skip=None):
    stored = {}
    for field, value in tagged_facts(text).items():
        lo, hi = LIMITS[field]
        if field != skip and field not in session["facts"] and lo <= value <= hi:
            session["facts"][field] = stored[field] = value
    return stored


# Things a worker says outside the four numbers. The rules path responds to them like a person
# would (the LLM policy does this far better when a key is set), and keeps a note.
_W = lambda *ws: {unicodedata.normalize("NFC", w) for w in ws}  # noqa: E731
CONTEXT_RULES = (
    # keys, note kept for the hisaab, ack said before the usual question, and for the days question
    # only: a clarifying question asked INSTEAD of storing the number ("4 din hospital" is not 4
    # days of work; "3 saal" / "ek hafta" is not a day count).
    {"keys": _W("hospital", "aspatal", "aspataal", "bimar", "beemar", "bimaar", "bukhar", "sick", "ill", "chot",
                "injury", "injured", "अस्पताल", "बीमार", "बुखार", "चोट"),
     "note": "Was ill / in hospital for some days",
     "ack": ("Yeh sunkar dukh hua. Sirf jin dino kaam kiya, wahi ginenge. ",
             "यह सुनकर दुख हुआ। सिर्फ़ जिन दिनों काम किया, वही गिनेंगे। "),
     "days": ("Yeh sunkar dukh hua, ab aap theek rahiye. Hospital ya bimaari ke din chhod kar, kitne din kaam kiya?",
              "यह सुनकर दुख हुआ, अब आप ठीक रहिए। अस्पताल या बीमारी के दिन छोड़ कर, कितने दिन काम किया?")},
    {"keys": _W("loan", "udhaar", "udhar", "karz", "karza", "qarz", "karj", "borrowed", "उधार", "कर्ज़", "कर्ज", "लोन"),
     "note": "Took a loan",
     "ack": ("Samajh gaya. Jo loan aapki mazdoori se kaata gaya, use advance mein ginenge. ",
             "समझ गया। जो लोन आपकी मज़दूरी से काटा गया, उसे एडवांस में गिनेंगे। ")},
    {"keys": _W("saal", "year", "years", "baras", "साल", "बरस"),
     "note": "Has worked there for years",
     "days": ("Lamba saath hai. Jis time ka paisa baaki hai, jaise pichhla hafta ya mahina, usme kitne din kaam kiya?",
              "लंबा साथ है। जिस टाइम का पैसा बाकी है, जैसे पिछला हफ़्ता या महीना, उसमें कितने दिन काम किया?")},
    {"keys": _W("mahina", "mahine", "mahino", "month", "months", "महीना", "महीने"),
     "days": ("Theek hai. Us mahine mein asal mein kitne din kaam kiya? Chhutti ke din chhod kar boliye.",
              "ठीक है। उस महीने में असल में कितने दिन काम किया? छुट्टी के दिन छोड़ कर बोलिए।")},
    {"keys": _W("hafta", "hafte", "hafton", "week", "weeks", "हफ़्ता", "हफ्ता", "हफ़्ते", "हफ्ते"),
     "days": ("Hafte mein kitne din kaam kiya, chhe ya saat? Ya jitne din gaye, utne boliye.",
              "हफ़्ते में कितने दिन काम किया, छह या सात? या जितने दिन गए, उतने बोलिए।")},
)
_PERIOD_KEYS = {"saal", "year", "years", "baras", "साल", "बरस", "mahina", "mahine", "mahino", "month", "months",
                "महीना", "महीने", "hafta", "hafte", "hafton", "week", "weeks", "हफ़्ता", "हफ्ता", "हफ़्ते", "हफ्ते"}


def rules_context(field, text):
    """{note, block, line} when the worker said something outside the plain number, else None."""
    words = set(tokens(text))
    for rule in CONTEXT_RULES:
        if not words & rule["keys"]:
            continue
        period = bool(rule["keys"] & _PERIOD_KEYS)
        if field == "days" and "days" in rule:
            work_named = words & {"kaam", "work", "worked", "काम"}
            if words & _TAGS["days"] and (period or ("ack" in rule and work_named)):
                if "ack" in rule:            # "hospital tha, 5 din kaam kiya": the days are named
                    return {"note": rule.get("note"), "block": False, "line": rule["ack"]}
                continue                     # "hafte mein 6 din": the days are named, fine
            return {"note": rule.get("note"), "block": True, "line": rule["days"]}
        if "ack" in rule:
            return {"note": rule.get("note"), "block": False, "line": rule["ack"]}
        if rule.get("note"):
            return {"note": rule["note"], "block": False, "line": None}
    return None


def rules_notes(text):
    """Every context note the rules recognise in the text."""
    words = set(tokens(text))
    return [r["note"] for r in CONTEXT_RULES if r.get("note") and words & r["keys"]]


def local_extract(field, question, text):
    """Rule-based reader for Wispr Flow text. Needs no API key. Handles digits ("700", "₹3,000"),
    Roman Hinglish ("saat sau", "teen hazaar") and Devanagari ("छह दिन"). When an answer holds
    several amounts, the one tagged for this question wins ("6 din, 700 roz" -> days 6)."""
    if field in ("confirm", "send"):
        value = parse_yes_no(text)
        return {"field": field, "value": value, "confidence": "high" if value is not None else "low"}
    groups = amount_groups(text)
    amounts = [g[0] for g in groups]
    if field in ("advance", "payments") and not amounts and says_none(text):
        return {"field": field, "value": 0, "confidence": "high"}
    if len(amounts) == 1:
        return {"field": field, "value": amounts[0], "confidence": "high"}
    tags = [_tag(b, a) for _, b, a in groups]
    other_fact = any(t not in (None, field) for t in tags)
    if len(amounts) > 1 and field in ("advance", "payments") and not other_fact:
        # "do hazaar aur ek hazaar (mile)": several payments; Python adds the parts
        return {"field": field, "value": None, "parts": amounts, "confidence": "high"}
    mine = {v for (v, _, _), t in zip(groups, tags) if t == field}
    if len(mine) == 1:
        return {"field": field, "value": mine.pop(), "confidence": "high"}
    return {"field": field, "value": None, "confidence": "low"}
