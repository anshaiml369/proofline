"""Frozen snapshot (tag v3-before-derivation, b379e75) for evaluate.py. Do not edit."""
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
from datetime import datetime, timezone

import audit
from legacy.v3_i18n import localise, readback_mr, result_mr

from legacy.v3_hinglish_numbers import amount_groups, parse_amounts, parse_yes_no, says_none, says_nothing, to_words, tokens
from wage_math import calculate_wages, payment_request

START, ASK_DAYS, ASK_RATE, ASK_ADVANCE, ASK_PAYMENTS = "START", "ASK_DAYS", "ASK_RATE", "ASK_ADVANCE", "ASK_PAYMENTS"
CONFIRM, CALCULATE, READ_RESULT, ASK_SEND = "CONFIRM", "CALCULATE", "READ_RESULT", "ASK_SEND"
SHOW_PREVIEW, DONE = "SHOW_PREVIEW", "DONE"
ASK_EXTRAS, FOLLOWUP, CONFIRM_DELETE = "ASK_EXTRAS", "FOLLOWUP", "CONFIRM_DELETE"

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
        "simpler": ("Message bhejun, shikayat ka draft banaun, ya sirf case save karun? Ek boliye.",
                    "मैसेज भेजूँ, शिकायत का ड्राफ़्ट बनाऊँ, या सिर्फ़ केस सेव करूँ? एक बोलिए।"),
    },
}
NEXT = {START: ASK_DAYS, ASK_DAYS: ASK_RATE, ASK_RATE: ASK_ADVANCE, ASK_ADVANCE: ASK_PAYMENTS, ASK_PAYMENTS: CONFIRM}

# Plausible ranges. Anything outside is treated as a mistake and re-asked.
LIMITS = {"days": (1, 366), "rate": (50, 20_000), "advance": (0, 10_000_000), "payments": (0, 10_000_000)}

RESTART = ("Theek hai, phir se shuru karte hain. Aapne kitne din kaam kiya?",
           "ठीक है, फिर से शुरू करते हैं। आपने कितने दिन काम किया?")
PREVIEW = ("Yeh raha message. Dekh lijiye, phir WhatsApp par bhejein wala button dabaiye.",
           "यह रहा मैसेज। देख लीजिए, फिर व्हाट्सऐप पर भेजें वाला बटन दबाइए।")
NO_SEND = ("Theek hai, message nahi bhejte. Aapka hisaab screen par hai.",
           "ठीक है, मैसेज नहीं भेजते। आपका हिसाब स्क्रीन पर है।")
SENT = ("WhatsApp khul gaya hai. Message bhej dijiye. Dhanyavaad.",
        "व्हाट्सऐप खुल गया है। मैसेज भेज दीजिए। धन्यवाद।")
DONE_LINE = ("Hisaab ho gaya. Dhanyavaad.", "हिसाब हो गया। धन्यवाद।")
CHOICES = ("Ab kya karun: message bhejun, escalate karun, ya sirf case save karun?",
           "अब क्या करूँ: मैसेज भेजूँ, एस्केलेट करूँ, या सिर्फ़ केस सेव करूँ?")
SAVED = ("Case save ho gaya. Hash card par hai. Baad mein message ya shikayat bhi kar sakte hain.",
         "केस सेव हो गया। हैश कार्ड पर है। बाद में मैसेज या शिकायत भी कर सकते हैं।")
ESCALATED = ("Shikayat ka draft screen par hai. Copy karke SAMADHAN portal par ya labour office mein dijiye.",
             "शिकायत का ड्राफ़्ट स्क्रीन पर है। कॉपी करके समाधान पोर्टल पर या लेबर ऑफ़िस में दीजिए।")
EXTRAS_Q = ("Theek hai. Kitne ghante overtime kiya, ek ghante ka kitna, aur kitni katauti hui?",
            "ठीक है। कितने घंटे ओवरटाइम किया, एक घंटे का कितना, और कितनी कटौती हुई?")
EXTRAS_SIMPLER = ("Jaise: das ghante overtime, sau rupaye ghanta, do sau katauti. Kuch nahi tha to boliye nahi.",
                  "जैसे: दस घंटे ओवरटाइम, सौ रुपये घंटा, दो सौ कटौती। कुछ नहीं था तो बोलिए नहीं।")
FOLLOWUP_Q = ("Namaste, PagarSaathi phir se. Pichhle case ke baare mein: thekedar ya manager ne kya kaha?",
              "नमस्ते, पगार साथी फिर से। पिछले केस के बारे में: ठेकेदार या मैनेजर ने क्या कहा?")
DELETE_ASK = ("Pakka case delete karun? Yeh wapas nahi aayega. Haan ya nahi boliye.",
              "पक्का केस डिलीट करूँ? यह वापस नहीं आएगा। हाँ या नहीं बोलिए।")
DELETED = ("Case delete ho gaya. Uska koi record ab nahi hai.", "केस डिलीट हो गया। उसका कोई रिकॉर्ड अब नहीं है।")
NOT_DELETED = ("Theek hai, case delete nahi kiya. ", "ठीक है, केस डिलीट नहीं किया। ")
NO_CASE = ("Abhi koi save kiya hua case nahi hai. ", "अभी कोई सेव किया हुआ केस नहीं है। ")
ASSIST_NUMBER = ("Koi baat nahi. Kisi saathi ki madad le lijiye. ",
                 "कोई बात नहीं। किसी साथी की मदद ले लीजिए। ")
ASSIST_ZERO = ("Koi baat nahi, abhi ke liye zero maan lete hain. Confirm karte waqt badal sakte hain. ",
               "कोई बात नहीं, अभी के लिए ज़ीरो मान लेते हैं। कन्फ़र्म करते वक़्त बदल सकते हैं। ")


def new_session():
    return {"id": uuid.uuid4().hex, "state": START, "facts": {}, "failures": 0, "case": None,
            "case_id": None, "needs_assistance": [], "turns": [], "last_agent_text": "",
            # the frame the dialogue policy reads, beyond the four numbers
            "context_notes": [], "unresolved": [], "turn_count": 0, "misses": {},
            "language": "hi", "node_path": [START], "pending_conflict": None, "extras": {},
            "extras_offered": False}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_turn(session, text, state, **kw):
    """Every worker turn, with a timestamp (it goes into the hashed case record)."""
    session["turns"].append({"at": _now(), "agent": session["last_agent_text"], "worker": text, "state": state, **kw})


def _reply(session, line, **extra):
    line, lang = localise(session, line, extra.pop("line_lang", None))
    shown, spoken = line
    if session["node_path"][-1] != session["state"]:
        session["node_path"].append(session["state"])
    out = {"agent_text": shown, "speak_text": spoken, "state": session["state"],
           "done": session["state"] == DONE, "case": session["case"],
           "needs_assistance": bool(session["needs_assistance"])}
    out.update(extra)
    out["line_lang"] = lang
    session["last_agent_text"] = shown
    return out


def _join(a, b):
    return (a[0] + b[0], a[1] + b[1])


def opening(session):
    """The agent speaks first."""
    return _reply(session, GREETING)


def readback(f, lang="hi", offer_extras=False, extras=None):
    if lang == "mr":
        return readback_mr(f, offer_extras, extras)
    adv = (f"{to_words(f['advance'])} advance", f"{f['advance']} रुपये एडवांस") if f["advance"] else \
          ("koi advance nahi", "कोई एडवांस नहीं")
    paid = (f"{to_words(f['payments'])} paid", f"{f['payments']} रुपये मिले") if f["payments"] else \
           ("abhi tak kuch nahi mila", "अब तक कुछ नहीं मिला")
    ex_s, ex_h = "", ""
    if extras and extras.get("overtime_hours"):
        ex_s += f", {to_words(extras['overtime_hours'])} ghante overtime {to_words(extras['overtime_rate'])} ke rate se"
        ex_h += f", {extras['overtime_hours']} घंटे ओवरटाइम {extras['overtime_rate']} रुपये घंटा"
    if extras and extras.get("deductions"):
        ex_s += f", {to_words(extras['deductions'])} katauti"
        ex_h += f", {extras['deductions']} रुपये कटौती"
    line = (f"Confirm karta hoon: {to_words(f['days'])} din, {to_words(f['rate'])} roz, {adv[0]}, {paid[0]}{ex_s}. Sahi hai?",
            f"कन्फ़र्म करता हूँ: {f['days']} दिन, {f['rate']} रुपये रोज़, {adv[1]}, {paid[1]}{ex_h}। सही है?")
    if offer_extras:
        line = _join(line, (" Overtime ya katauti thi to woh bhi bataiye.", " ओवरटाइम या कटौती थी तो वह भी बताइए।"))
    return line


def result_line(case, lang="hi"):
    """Reads every line of the card aloud, then offers the three choices (or ends when ₹0 is owed)."""
    if lang == "mr":
        return result_mr(case)
    shown = [f"Kul kamaai {to_words(case['expected'])}."]
    spoken = [f"कुल कमाई {case['expected']} रुपये।"]
    if case["received"]:
        shown.append(f"Advance {to_words(case['advance'])}, ab tak mila {to_words(case['payments'])}, "
                     f"kul mila {to_words(case['received'])}.")
        spoken.append(f"एडवांस {case['advance']} रुपये, अब तक मिला {case['payments']} रुपये, कुल मिला {case['received']} रुपये।")
    else:
        shown.append("Abhi tak kuch nahi mila.")
        spoken.append("अभी तक कुछ नहीं मिला।")
    if case["outstanding"] <= 0:
        shown.append("Hisaab ke hisaab se koi paisa baaki nahi hai. Case save ho gaya.")
        spoken.append("हिसाब के हिसाब से कोई पैसा बाकी नहीं है। केस सेव हो गया।")
    else:
        shown.append(f"Baaki {to_words(case['outstanding'])} rupaye. {CHOICES[0]}")
        spoken.append(f"बाकी {case['outstanding']} रुपये। {CHOICES[1]}")
    return (" ".join(shown), " ".join(spoken))


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
    if state == CONFIRM:
        line = readback(session["facts"], session.get("language", "hi"),
                        offer_extras=not session.get("extras_offered"), extras=session.get("extras"))
        session["extras_offered"] = True
    else:
        line = STATES[state]["question_hi"]
    return _join(prefix, line) if prefix else line


def step(session, text, extract):
    """One worker turn. `extract(field, question, text)` -> {"field", "value", "confidence"[, "parts"]}."""
    state = session["state"]
    text = (text or "").strip()
    record_turn(session, text, state)

    if state == FOLLOWUP:                               # reply to "thekedar ne kya kaha?"
        return followup_reply(session, text)

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
        tagged = tagged_facts(text)
        fixes = {f: v for f, v in tagged.items() if f != field and f in session["facts"]
                 and session["facts"][f] != v and LIMITS[f][0] <= v <= LIMITS[f][1]}
        if fixes and field not in tagged:              # "sorry, advance 500 tha": a correction, not this answer
            session["facts"].update(fixes)
            session["turns"][-1]["corrected"] = dict(fixes)
            f, v = next(iter(fixes.items()))
            said = (f"Theek hai, {SLOT_HI[f][0]} {to_words(v)} kar diya. ", f"ठीक है, {v} {SLOT_HI[f][1]} कर दिया। ")
            return _reply(session, _join(said, STATES[state]["question_hi"]), corrected=fixes,
                          facts=dict(session["facts"]))
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
        if mentions_extras(text):                     # "haan, aur overtime bhi tha"
            return extras_step(session, text, first=True)
        ok = _accept_bool(extract("confirm", session["last_agent_text"], text))
        if ok is None:
            session["failures"] += 1
            return _reply(session, STATES[CONFIRM]["simpler"], reasked=True)
        if not ok:
            session["facts"] = {}
            session["extras"] = {}
            session["needs_assistance"] = []
            _advance_to(session, ASK_DAYS)
            return _reply(session, RESTART, restarted=True)
        return calculate(session)

    if state == ASK_EXTRAS:
        return extras_step(session, text)

    if state == ASK_SEND:
        choice = parse_choice(text)
        if choice is None:
            yes = _accept_bool(extract("send", session["last_agent_text"], text))
            choice = None if yes is None else ("send" if yes else "save")
        if choice is None:
            session["failures"] += 1
            return _reply(session, STATES[ASK_SEND]["simpler"], reasked=True)
        return choose(session, choice)

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


BETA_FIXED_HINDI = ("bn", "ta", "te")   # the LLM speaks these; Python's fixed lines stay Hindi


def _mix(session, llm, py):
    """The policy's line followed by one of Python's fixed lines, in one voice. Returns (line, lang)."""
    lang = session.get("language", "hi")
    if not llm:
        return py, None
    if lang in BETA_FIXED_HINDI:          # beta: never one reply in two voices; the fixed line wins
        return py, None
    if lang == "mr":
        return _join(llm, localise(session, py)[0]), "mr"
    return _join(llm, py), None


_SCRIPT = {"mr": ("\u0900", "\u097F"), "bn": ("\u0980", "\u09FF"), "ta": ("\u0B80", "\u0BFF"),
           "te": ("\u0C00", "\u0C7F")}


def _script_ok(session, line):
    """In Marathi, Bengali, Tamil and Telugu the policy's line must be in that script; a Roman
    Hinglish line would be read by the wrong voice."""
    rng = _SCRIPT.get(session.get("language", "hi"))
    if not rng or not line:
        return True
    letters = [ch for ch in line[0] if ch.isalpha()]
    return bool(letters) and sum(rng[0] <= ch <= rng[1] for ch in letters) / len(letters) > 0.6


def _llm_lang(session):
    lang = session.get("language", "hi")
    return lang if lang in ("mr",) + BETA_FIXED_HINDI else None


_CORRECTION = {"nahi", "nahin", "galat", "sorry", "actually", "matlab", "asal", "sahi", "दरअसल", "गलत", "नहीं",
               "maaf", "wait", "ruko", "balki", "बल्कि", "correction", "change"}
_OLD = {"pehla", "pehle", "pehlawala", "purana", "first", "old", "पहला", "पहले", "पुराना"}
_NEW = {"doosra", "dusra", "naya", "abhi", "second", "new", "latest", "दूसरा", "नया", "अभी"}
SLOT_HI = {"days": ("din", "दिन"), "rate": ("roz", "रुपये रोज़"), "advance": ("advance", "रुपये एडवांस"),
           "payments": ("mile", "रुपये मिले")}


def conflict_question(slot, old, new):
    w = SLOT_HI[slot]
    return (f"Aapne pehle {to_words(old)} {w[0]} kaha, ab {to_words(new)} {w[0]}: kaunsa sahi hai?",
            f"आपने पहले {old} {w[1]} कहा, अब {new} {w[1]}: कौन-सा सही है?")


def resolve_conflict(session, text):
    """The worker's answer to "kaunsa sahi hai?". Both values stay in the turn log."""
    c = session["pending_conflict"]
    session["pending_conflict"] = None
    words, said = set(tokens(text)), set(parse_amounts(text))
    if c["old"] in said and c["new"] not in said or words & _OLD:
        pick, how = c["old"], "worker chose the earlier value"
    elif c["new"] in said or words & _NEW or parse_yes_no(text) is True:
        pick, how = c["new"], "worker chose the later value"
    else:
        pick, how = c["new"], "unclear answer: the latest value is kept; the read-back checks it"
    session["facts"][c["slot"]] = pick
    session["turns"][-1]["conflict"] = {**c, "chosen": pick, "how": how}
    return c["slot"], pick


def step_policy(session, text, decision):
    """One worker turn driven by the LLM dialogue policy. The policy chooses what to say and
    which number to go after; Python keeps the frame, accepts only numbers the worker said,
    breaks loops, forces the read-back before any maths, and does the maths."""
    state = session["state"]
    text = (text or "").strip()
    if state in (FOLLOWUP, ASK_EXTRAS) or (state == CONFIRM and mentions_extras(text)):
        return step(session, text, local_extract)        # Python-only steps, same in both paths
    record_turn(session, text, state, action=decision["action"])
    session["turn_count"] += 1
    resolved = resolve_conflict(session, text) if session.get("pending_conflict") else None
    before = dict(session["facts"])
    if decision["context_delta"]:
        _note(session, decision["context_delta"])
    stored, rejected = accept_extracted(session, text, decision)
    if resolved:                       # the answer to "kaunsa sahi hai?" decides, not a re-extraction
        session["facts"][resolved[0]] = resolved[1]
        stored[resolved[0]] = resolved[1]
    if state != CONFIRM:
        stored.update(backstop(session, text, decision))
    session["turns"][-1]["facts"] = stored
    line = None if rejected else guard_line(session, text, decision)
    if line is not None and not _script_ok(session, line):
        line = None
        session["turns"][-1]["guarded"] = "wrong language"
    elif line is None:
        session["turns"][-1]["guarded"] = "rejected number" if rejected else "unsafe or repeated line"
    extra = {"facts": dict(session["facts"]), "action": decision["action"]}
    if stored:
        extra["parsed"] = {"field": list(stored)[-1], "value": list(stored.values())[-1]}

    if state in (START, ASK_DAYS, ASK_RATE, ASK_ADVANCE, ASK_PAYMENTS):
        changed = [k for k in stored if k in before and before[k] != stored[k] and not resolved]
        if changed and not set(tokens(text)) & _CORRECTION:
            slot = changed[0]               # a different value with no "nahi"/"galat": ask, don't guess
            session["pending_conflict"] = {"slot": slot, "old": before[slot], "new": stored[slot]}
            session["turns"][-1]["conflict_asked"] = dict(session["pending_conflict"])
            return _reply(session, conflict_question(slot, before[slot], stored[slot]), action="python_conflict",
                          conflict=dict(session["pending_conflict"]), facts=dict(session["facts"]))
        progressed = bool(stored or decision["context_delta"])
        session["failures"] = 0 if progressed else session["failures"] + 1
        asked = STATES[state]["extract_field"] if state in STATES else None
        if asked and asked not in session["facts"] and not decision["context_delta"]:
            session["misses"][asked] = session["misses"].get(asked, 0) + 1
        nxt = _next_missing(session)
        if nxt == CONFIRM:                      # all four known: the read-back is Python's, always
            joined, lang = _mix(session, _statements(line), _ask(session, CONFIRM))
            return _reply(session, joined, line_lang=lang, **extra)
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
        lang = _llm_lang(session)
        if not _ends_with_question(line):       # every collecting turn moves the hisaab forward
            line, lang = _mix(session, _space(line), STATES[nxt]["question_hi"])
        return _reply(session, line, line_lang=lang, reasked=bool(session["failures"]), **extra)

    if state == CONFIRM:
        if stored:                               # a correction: read everything back again
            _advance_to(session, CONFIRM)
            return _reply(session, readback(session["facts"], session.get("language", "hi"),
                                            extras=session.get("extras")), corrected=stored, **extra)
        rules_yes = parse_yes_no(text)
        if (decision["intent"] == "yes" and rules_yes is not False) or (rules_yes is True and decision["intent"] == "other"):
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
        return _policy_reask(session, line, STATES[CONFIRM]["simpler"], extra)

    if state == ASK_SEND:
        if parse_choice(text) or decision["intent"] in ("yes", "no"):   # Python reads the choice words first
            ok = decision["intent"] != "no"
            return step(_undo_turn(session), text, lambda *a: {"value": ok, "confidence": "high"})
        return _policy_reask(session, line, STATES[ASK_SEND]["simpler"], extra)

    if state == SHOW_PREVIEW:
        return _reply(session, PREVIEW)
    return _reply(session, DONE_LINE)


def _policy_reask(session, line, reask, extra):
    if line and _ends_with_question(line):
        return _reply(session, line, line_lang=_llm_lang(session), reasked=True, **extra)
    joined, lang = _mix(session, _space(line), reask)
    return _reply(session, joined, line_lang=lang, reasked=True, **extra)


def _space(line):
    return (line[0].rstrip() + " ", line[1].rstrip() + " ") if line else None


def _undo_turn(session):
    """step() records the turn itself; drop the one step_policy() just added."""
    session["turns"].pop()
    session["turn_count"] -= 1
    return session


def calculate(session):
    """CALCULATE → READ_RESULT inside one turn: Python does the maths, the agent reads every line."""
    _advance_to(session, CALCULATE)
    f, x = session["facts"], session.get("extras", {})
    session["case"] = calculate_wages(f["days"], f["rate"], f["advance"], f["payments"],
                                      x.get("overtime_hours", 0), x.get("overtime_rate", 0), x.get("deductions", 0))
    _advance_to(session, READ_RESULT)
    line = result_line(session["case"], session.get("language", "hi"))
    _advance_to(session, DONE if session["case"]["outstanding"] <= 0 else ASK_SEND)
    return _reply(session, line, save=True)


_CHOICE_WORDS = {
    "escalate": {"escalate", "escalation", "shikayat", "complaint", "commissioner", "samadhan", "takrar", "शिकायत",
                 "तक्रार", "एस्केलेट"},
    "save": {"save", "sev", "rakh", "rakho", "rakhiye", "rakhna", "bas", "सेव", "रख", "रखो"},
    "send": {"message", "msg", "bhej", "bhejo", "bhejun", "bhejiye", "bhejna", "whatsapp", "send", "मैसेज", "भेजो",
             "भेजूँ", "भेजिए", "पाठवा", "पाठव"},
}


def parse_choice(text):
    """"message bhejun" -> send, "escalate karo" -> escalate, "sirf save karo" -> save, else None."""
    words = set(tokens(text))
    for choice in ("escalate", "save", "send"):       # escalate/save win over a stray "message"
        if words & _CHOICE_WORDS[choice]:
            return choice
    return None


def choose(session, choice):
    session["choice"] = choice
    if choice == "send":
        msg = payment_request(session["case"])
        if session.get("case_hash"):          # set by the app when the case was sealed
            msg += f"\nCase ID (sha256): {session['case_hash'][:12]}"
        session["case"]["payment_request"] = msg
        _advance_to(session, SHOW_PREVIEW)   # preview first, then the Send button
        return _reply(session, PREVIEW, save=True, choice=choice)
    _advance_to(session, DONE)
    return _reply(session, ESCALATED if choice == "escalate" else SAVED, save=True, choice=choice,
                  escalate=choice == "escalate")


# ---------- optional overtime and deductions (offered in the read-back; never asked separately) ----------

_EXTRA_WORDS = {"overtime", "ot", "ओवरटाइम", "katauti", "katoti", "deduction", "deductions", "jurmana", "fine",
                "कटौती", "जुर्माना", "kapat", "कपात"}
_HOUR_WORDS = {"ghante", "ghanta", "ghanton", "hours", "hour", "hrs", "घंटे", "घंटा", "तास"}
_CUT_WORDS = {"katauti", "katoti", "deduction", "deductions", "jurmana", "fine", "kata", "kaata", "kaat", "kat",
              "कटौती", "जुर्माना", "कपात", "कटे", "काटा"}
_MONEY_WORDS = {"rupaye", "rupay", "rupees", "rs", "₹", "रुपये", "रुपए", "per", "prati", "har"}


def mentions_extras(text):
    return bool(set(tokens(text)) & _EXTRA_WORDS)


def parse_extras(text):
    """{overtime_hours, overtime_rate, deductions} found in the text. "10 ghante overtime, 100 rupaye
    ghanta, 200 katauti" -> {10, 100, 200}. Reading numbers only; Python does the maths later."""
    out = {}
    for value, before, after in amount_groups(text):
        nxt = [w for w in after[:3]]
        if nxt and nxt[0] in _HOUR_WORDS:
            out.setdefault("overtime_hours", value)
        elif nxt and nxt[0] in _MONEY_WORDS and set(nxt[1:3]) & _HOUR_WORDS:
            out.setdefault("overtime_rate", value)
        elif set(nxt[:2]) & _CUT_WORDS or (before and before[-1] in _CUT_WORDS):
            out.setdefault("deductions", value)
        elif before and set(before[-2:]) & _HOUR_WORDS and "overtime_hours" in out:
            out.setdefault("overtime_rate", value)        # "10 ghante, ghante ka 100"
    return out


def extras_step(session, text, first=False):
    """Collect the optional extras, then read everything back again (the read-back stays mandatory)."""
    if first:
        _advance_to(session, ASK_EXTRAS)
    found = parse_extras(text)
    x = session.setdefault("extras", {})
    x.update({k: v for k, v in found.items() if 0 <= v <= 100_000})
    if not found and (says_none(text) or parse_yes_no(text) is False):
        session["extras"] = {}
        return _reply(session, _ask(session, CONFIRM), extras={})
    complete = ("overtime_hours" in x) == ("overtime_rate" in x) and (x.get("overtime_hours") or x.get("deductions"))
    if complete:
        x.setdefault("overtime_hours", 0)
        x.setdefault("overtime_rate", 0)
        x.setdefault("deductions", 0)
        return _reply(session, _ask(session, CONFIRM), extras=dict(x))
    session["failures"] += 1
    if session["failures"] >= 3:                       # give up on the extras, keep the four-number case
        session["extras"] = {}
        session["unresolved"] = sorted(set(session["unresolved"]) | {"extras"})
        return _reply(session, _join(ASSIST_NUMBER, _ask(session, CONFIRM)), extras={})
    if "overtime_hours" in x and "overtime_rate" not in x:
        q = ("Overtime ke ek ghante ka kitna milna tha?", "ओवरटाइम के एक घंटे का कितना मिलना था?")
    else:
        q = EXTRAS_Q if first or session["failures"] == 1 else EXTRAS_SIMPLER
    return _reply(session, q, reasked=not first, extras=dict(x))


# ---------- follow-up on a case sent more than a day ago ----------

def followup_opening(session, prior):
    """Open with a question about the earlier case instead of the greeting."""
    session["state"] = FOLLOWUP
    session["followup_of"] = prior["session_id"]
    session["node_path"] = [FOLLOWUP]
    return _reply(session, FOLLOWUP_Q, followup_case=prior["session_id"])


def followup_reply(session, text):
    when = audit.commitment_from(text)
    ack = ("Note kar liya. ", "नोट कर लिया। ")
    if when:
        d = datetime.fromisoformat(when)
        months = ("January February March April May June July August September October November December").split()
        hi_months = "जनवरी फ़रवरी मार्च अप्रैल मई जून जुलाई अगस्त सितंबर अक्टूबर नवंबर दिसंबर".split()
        ack = _join(ack, (f"Unhone {d.day} {months[d.month - 1]} tak dene ko kaha hai. Card par yaad dila dunga. ",
                          f"उन्होंने {d.day} {hi_months[d.month - 1]} तक देने को कहा है। कार्ड पर याद दिला दूँगा। "))
    ack = _join(ack, ("Na de to Escalate button se shikayat ka draft bana sakte hain. "
                      "Naya hisaab karna ho to bataiye, kya pareshani hai?",
                      "न दे तो एस्केलेट बटन से शिकायत का ड्राफ़्ट बना सकते हैं। नया हिसाब करना हो तो बताइए, क्या परेशानी है?"))
    session["state"] = START
    return _reply(session, ack, followup={"at": _now(), "text": text}, commitment_date=when)


# ---------- privacy: "mera case delete karo" (any time, after a spoken yes) ----------

_DELETE_WORDS = {"delete", "hatao", "hata", "mitao", "mita", "remove", "erase", "डिलीट", "हटाओ", "मिटाओ"}


def wants_delete(text):
    words = set(tokens(text))
    return bool(words & _DELETE_WORDS) and bool(words & {"case", "kes", "data", "hisaab", "record", "केस", "हिसाब"})


def handle_command(session, text, has_case):
    """Commands that work in any state. Returns a reply, or None for a normal turn.
    `has_case`: a saved case exists for this session (or the earlier one being followed up)."""
    if session["state"] == CONFIRM_DELETE:
        record_turn(session, text, CONFIRM_DELETE)
        back = session.pop("before_delete", START)
        if parse_yes_no(text) is True:
            session["state"] = DONE
            session["case"] = None
            return _reply(session, DELETED, delete=True)
        session["state"] = back
        q = STATES[back]["question_hi"] if back in STATES and "question_hi" in STATES[back] else ("", "")
        return _reply(session, _join(NOT_DELETED, q) if q[0] else NOT_DELETED)
    if wants_delete(text):
        record_turn(session, text, session["state"])
        if not has_case:
            q = STATES[session["state"]].get("question_hi") if session["state"] in STATES else None
            return _reply(session, _join(NO_CASE, q) if q else NO_CASE)
        session["before_delete"] = session["state"]
        session["state"] = CONFIRM_DELETE
        return _reply(session, DELETE_ASK)
    return None


def mark_sent(session):
    """The worker tapped "Send to contractor" (SHOW_PREVIEW → DONE)."""
    if session["state"] != SHOW_PREVIEW:
        return None
    _advance_to(session, DONE)
    return _reply(session, SENT)


# Words that say which fact an amount belongs to: "6 din", "700 roz", "500 advance", "3000 mile".
_TAGS = {
    "days": {"din", "dino", "dinon", "day", "days", "दिन", "दिनों", "divas", "दिवस"},
    "rate": {"roz", "roj", "rozana", "daily", "rate", "dihadi", "dihaadi", "mazdoori", "per", "रोज़", "रोज",
             "रोजाना", "रोज़ाना", "दिहाड़ी", "मज़दूरी", "मजदूरी", "मजुरी", "majuri", "रोजची"},
    "advance": {"advance", "advanced", "peshgi", "एडवांस", "पेशगी", "ॲडव्हान्स", "अ‍ॅडव्हान्स", "अॅडव्हान्स", "ऍडव्हान्स",
                "एडव्हान्स", "उचल"},
    "payments": {"mile", "mila", "mili", "milaa", "paid", "received", "diye", "diya", "payment", "मिले", "मिला",
                 "मिली", "दिए", "दिया", "milale", "मिळाले", "मिळाला"},
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
