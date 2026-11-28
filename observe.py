"""Rule-based observation reader: what the worker said, tagged by type (see derive.py). No maths.

Used with no API key (and as a backstop to the LLM's observations). It reads periods ("kuch 5-6
mahine", "teen hafte", "aadha mahina"), weekly frequency ("har hafte ke paanch din", "7 din mein se
5 din", "sirf Sunday chhutti", "alternate din"), rates per day/week/month/trip and ranges
("600-700 roz"), deductions, bonuses, and context (health, threat, questions, emotion, legal).
Plain "6 din" / "700 roz" / "500 advance" / "3000 mile" are tagged too.
"""
import re
import unicodedata

from hinglish_numbers import _number_groups, parse_yes_no, says_none, tokens

N = lambda *ws: {unicodedata.normalize("NFC", w) for w in ws}  # noqa: E731

MONTH = N("mahina", "mahine", "mahino", "mahinon", "month", "months", "महीना", "महीने", "महीनों", "महिना", "महिने")
WEEK = N("hafta", "hafte", "hafton", "week", "weeks", "हफ़्ता", "हफ्ता", "हफ़्ते", "हफ्ते", "आठवडा", "आठवडे")
DAY = N("din", "dino", "dinon", "day", "days", "दिन", "दिनों", "divas", "दिवस")
YEAR = N("saal", "year", "years", "baras", "साल", "बरस", "varsh")
RATE_DAY = N("roz", "roj", "rozana", "daily", "dihadi", "dihaadi", "रोज़", "रोज", "रोजाना", "रोज़ाना", "दिहाड़ी",
             "majuri", "मजुरी", "rate")
TRIP = N("trip", "trips", "chakkar", "fera", "phera", "ट्रिप", "चक्कर", "फेरा")
ADVANCE = N("advance", "advanced", "peshgi", "एडवांस", "पेशगी", "ॲडव्हान्स", "उचल")
LOAN = N("loan", "udhaar", "udhar", "karz", "karza", "qarz", "karj", "उधार", "कर्ज़", "कर्ज", "लोन", "liya", "liye",
         "लिया")
PAID = N("mile", "mila", "mili", "milaa", "paid", "received", "payment", "मिले", "मिला", "मिली", "मिळाले", "मिळाला",
         "upi", "cash", "nakad", "gpay", "phonepe", "paytm", "transfer")
GAVE = N("diye", "diya", "दिए", "दिया")
CUT = N("kata", "kaata", "kate", "kaate", "kaat", "kat", "katauti", "katoti", "deduction", "deductions", "jurmana",
        "fine", "charge", "कटौती", "जुर्माना", "कटे", "काटा", "काटे", "कपात")
BONUS = N("bonus", "inaam", "inam", "इनाम", "बोनस", "extra")
OFF = N("chhutti", "chutti", "off", "छुट्टी", "holiday")
WEEKDAYS = {"sunday": "Sunday", "itwar": "Sunday", "itvaar": "Sunday", "raviwar": "Sunday", "रविवार": "Sunday",
            "इतवार": "Sunday", "monday": "Monday", "somvar": "Monday", "सोमवार": "Monday"}
CORRECTION = N("nahi", "nahin", "galat", "sorry", "arre", "arey", "actually", "matlab", "asal", "balki", "गलत",
               "नहीं", "बल्कि", "maaf", "correction")
WORK = N("kaam", "work", "worked", "kiya", "kiye", "काम", "gaya", "gaye", "jata", "jaata")

# context categories -> trigger words (multi-word triggers are matched on the joined text)
CONTEXT = (
    ("health", N("hospital", "aspatal", "aspataal", "bimar", "beemar", "bimaar", "bukhar", "sick", "ill", "chot",
                 "injury", "injured", "अस्पताल", "बीमार", "बुखार", "चोट", "accident"), ()),
    ("threat", N("dhamki", "dhamkaya", "dhamka", "threat", "maarega", "maarne", "marne", "pitai", "dhamkate",
                 "धमकी", "मारेगा", "मारने"), ("nikal dega", "nikal dunga", "kaam se nikal", "nikaal dunga", "nikaal dega", "kaam se nikaal", "police bula",
                                                "dekh lunga")),
    ("question_identity", set(), ("tum kaun", "aap kaun", "kaun ho", "who are you", "तुम कौन", "आप कौन",
                                  "kaun bol", "insaan ho", "robot ho")),
    ("question_cost", set(), ("free hai", "paisa lagega", "paise lagenge", "fees", "kitna lagega", "charge lagega",
                              "फ्री है", "kitne paise lagenge", "free me", "free mein")),
    ("question_privacy", set(), ("data safe", "safe hai", "kisko dikhega", "kaun dekhega", "privacy",
                                 "record rakhoge", "data kahan", "mera data", "डेटा")),
    ("legal_court", N("court", "adalat", "vakeel", "vakil", "lawyer", "कोर्ट", "अदालत", "वकील", "police",
                      "पुलिस", "fir", "case"), ("case karunga", "case karenge")),
    ("legal_proof", N("proof", "saboot", "sabut", "praman", "सबूत", "प्रूफ"), ()),
    ("legal_refusal", set(), ("manna kare", "mana kare", "mana kar", "nahi maane", "nahi mana", "inkaar",
                              "nahi dega to", "na de to", "nahi diya to", "manne se", "इनकार")),
    ("legal_when", set(), ("kitne din mein", "kab tak milega", "kab milega", "kitne dino mein", "kab tak paisa",
                           "कब मिलेगा")),
    ("emotion", N("pareshan", "pareshaan", "tension", "dukhi", "gussa", "thak", "ro", "rona", "majboor",
                  "परेशान", "दुखी", "गुस्सा", "मजबूर"), ("bahut bura", "kya karun", "samajh nahi aa")),
    ("wage_raise", set(), ("pagar badha", "pagar badhao", "salary badha", "tankhwah badha", "पगार बढ़ा",
                           "पगार बढाओ", "increment")),
    ("market_rate", set(), ("market rate", "bazaar bhav", "jo sab ko milta", "sarkari rate", "minimum wage")),
)
_RANGE_JOIN = N("se", "to", "ya", "से", "या", "-", "–", "aur", "or")


def _norm(text):
    return unicodedata.normalize("NFC", (text or "").lower())


def _ranges(chunk):
    """Amount groups in one clause, with adjacent pairs ("5-6", "paanch chhe", "5 se 6", "600 ya 700")
    folded into one range. Returns [(lo, hi, before, after)]."""
    groups = _number_groups(chunk)
    out, i = [], 0
    while i < len(groups):
        v, before, after = groups[i]
        if i + 1 < len(groups):
            v2, before2, after2 = groups[i + 1]
            join = (not after or set(after[:1]) & _RANGE_JOIN) and (not before2 or set(before2[-1:]) & _RANGE_JOIN)
            # "aur" joins a range only for small counts ("5 aur 6 mahine" is rare; "1000 aur 2000 mile" is two)
            and_ok = not (set(after[:1]) | set(before2[-1:])) & N("aur", "or") or v2 <= 12
            close = v < v2 <= max(v * 2, v + 3)
            if join and and_ok and close:
                out.append((v, v2, before, after2))
                i += 2
                continue
        out.append((v, v, before, after))
        i += 1
    return out


def _context(text):
    t = _norm(text)
    words = set(tokens(text))
    found = []
    for cat, keys, phrases in CONTEXT:
        if (keys and words & keys) or any(p in t for p in phrases):
            found.append({"type": "context", "category": cat,
                          "text": next((p for p in phrases if p in t), None) or next(iter(words & keys), cat)})
    return found


def _clauses(text):
    return [c for c in re.split(r"[,.;!?।]|\s(?:par|lekin|but|magar)\s", _norm(text)) if c.strip()]


def extract(text, frame=None):
    """Observations in one utterance. `frame` (optional): {"asking": slot, "days_per_week": n} for
    reading a bare "5 din" as a restated frequency rather than a day count."""
    frame = frame or {}
    t = _norm(text)
    words = set(tokens(text))
    obs = []
    has_week = bool(words & WEEK)
    correcting = bool(words & CORRECTION) and len(_number_groups(t)) >= 2 and "nahi" in t

    # weekly frequency: "hafte mein 5 din", "har hafte ke paanch din", "7 din mein se 5 din"
    freq = None
    m = re.search(r"(\d+|saat|सात)\s*(?:din|दिन)\s*(?:mein|me|में)\s*(?:se|से)\s*(\d+|\w+)", t)
    if m:
        vals = [v for v, *_ in _number_groups(m.group(0))]
        if len(vals) >= 2 and vals[0] == 7 and 0 < vals[1] <= 7:
            freq = vals[1]
    if freq is None and has_week:
        # a small day count in a sentence about weeks is per week ("har hafte ke paanch din"), unless
        # the sentence only counts weeks and days ("ek hafte mein 6 din" = 6 days in one week)
        groups = _ranges(t)
        weeks = [lo for lo, hi, _, a in groups if set(a[:1]) & WEEK]
        # per-week phrasing only: "har hafte", "hafte mein/ke", "per week", "N din hafte mein";
        # "pichhle hafte" / "is hafte" is a time reference, not a frequency
        per_week = re.search(r"(?<!pichhle )(?<!pichle )(?<!is )(?<!agle )(?<!last )(?<!this )"
                             r"(hafte|हफ्ते|हफ़्ते|week)\S*\s+(mein|me|ke|में|के)\b|\b(har|every|per|हर)\s+(hafte|week|हफ्ते|हफ़्ते)|"
                             r"din\s+(hafte|week)", t)
        for lo, hi, before, after in groups:
            if lo == hi and 0 < lo <= 7 and set(after[:1]) & DAY:
                if weeks == [1] and not re.search(r"\b(har|every|हर)\b", t):
                    break                                # one week, N days: a day count
                if per_week:
                    freq = lo
                break
    if freq is None and words & OFF:
        off = [WEEKDAYS[w] for w in words if w in WEEKDAYS]
        if off or "sirf" in words or "ek" in words:
            freq = 6
            obs.append({"type": "frequency", "days_per_week": 6, "explicit_off": off or None})
    if freq is None and re.search(r"alternate|ek din chhod|ek din chod|din chhod ke|din chod ke|एक दिन छोड़", t):
        obs.append({"type": "frequency", "days_per_week": 3.5, "explicit_off": None})
        freq = 3.5
    if freq is None and re.search(r"\b(roz|har din|rozana|daily|रोज़|रोज)\s+(kaam|jata|jaata|gaya|काम)", t) and \
            not re.search(r"\d", t):
        obs.append({"type": "frequency", "days_per_week": 7, "explicit_off": None})
        freq = 7
    if freq is not None and not any(o["type"] == "frequency" for o in obs):
        obs.append({"type": "frequency", "days_per_week": freq, "explicit_off": None})

    # fractions of a month/week: "aadha mahina", "dedh mahina", "dhai hafte"
    for word, val in (("aadha", 0.5), ("adha", 0.5), ("आधा", 0.5), ("dedh", 1.5), ("डेढ़", 1.5), ("dhai", 2.5),
                      ("dhaai", 2.5), ("ढाई", 2.5), ("sava", 1.25), ("paune", 0.75)):
        mm = re.search(r"(?<!\w)" + word + r"\s+(\S+)", t)
        if mm and mm.group(1) in MONTH | WEEK:
            obs.append({"type": "period", "value": val, "unit": "month" if mm.group(1) in MONTH else "week",
                        "range": None})
    if re.search(r"pichhle mahine se|pichle mahine se|पिछले महीने से|last month se", t):
        obs.append({"type": "period", "value": "1-2", "unit": "month", "range": [1, 2]})

    # numbers, clause by clause
    days_said = []
    for clause in _clauses(t):
        cw = set(tokens(clause))
        for lo, hi, before, after in _ranges(clause):
            rng = [lo, hi] if lo != hi else None
            val = f"{lo}-{hi}" if rng else lo
            nxt, prv = set(after[:2]), set(before[-2:])
            if freq is not None and lo == hi == freq and (nxt & DAY):
                continue                                 # the frequency itself ("5 din" a week)
            if lo == hi and freq is not None and lo == 7 and nxt & DAY and "se" in clause:
                continue                                 # "7 din mein se 5"
            if nxt & YEAR or prv & YEAR:
                continue                                 # "teen saal se": tenure, not the unpaid period
            if (nxt & MONTH or nxt & WEEK) and hi <= 36:
                obs.append({"type": "period", "value": val, "unit": "month" if nxt & MONTH else "week", "range": rng})
                continue
            if (prv & MONTH or nxt & MONTH or "month" in cw) and lo >= 500 and not (cw & PAID or cw & ADVANCE):
                obs.append({"type": "rate", "value": val, "per": "month", "range": rng})
                continue
            if (prv & WEEK or nxt & WEEK) and lo >= 200 and not (cw & PAID or cw & ADVANCE):
                obs.append({"type": "rate", "value": val, "per": "week", "range": rng})
                continue
            if (prv & TRIP or nxt & TRIP) and lo >= 30:
                obs.append({"type": "rate", "value": val, "per": "trip", "range": rng})
                continue
            if (nxt & TRIP) and lo < 30:
                if after[1:2] and after[1] in N("ke", "ka", "ki", "का", "के", "की"):
                    continue                             # "ek trip ke 150": per trip, not 1 trip a day
                obs.append({"type": "trips", "per_day": lo})
                continue
            if nxt & DAY and cw & TRIP:
                continue                                 # "ek din mein 4 trip"
            if after[:1] == ("per",) and nxt & DAY or (nxt & DAY and lo > 366):
                obs.append({"type": "rate", "value": val, "per": "day", "range": rng})
                continue                                 # "seven hundred per day": a rate, not 700 days
            if nxt & DAY:
                if lo != hi:
                    obs.append({"type": "period", "value": val, "unit": "day", "range": rng})
                else:
                    days_said.append(lo)
                continue
            def tag_of(ws):
                return ("cut" if ws & CUT else "bonus" if ws & BONUS else "advance" if ws & ADVANCE else
                        "paid" if ws & PAID else "loan" if ws & LOAN else None)
            tag = tag_of(nxt) or tag_of(prv - N("aur", "and", "or"))   # the words after an amount win
            if set(before[-1:]) & ADVANCE and tag == "paid":
                tag = "advance"                          # "advance 1000 mila tha": named right before it
            if tag is None:
                tag = ("cut" if cw & CUT else "bonus" if cw & BONUS else None)
            if tag == "cut":
                reason = next((w for w in ("khana", "khane", "tools", "tool", "rehna", "room", "kiraya", "transport",
                                           "jurmana", "khaana") if w in cw), None)
                obs.append({"type": "deduction", "value": lo, "reason": reason})
                continue
            if tag == "bonus":
                obs.append({"type": "bonus", "value": lo, "promised": bool(re.search(r"bola|kaha|promise|wada|vaada", clause))})
                continue
            if nxt & RATE_DAY or prv & RATE_DAY or "per" in prv and "din" in nxt:
                obs.append({"type": "rate", "value": val, "per": "day", "range": rng})
                continue
            if tag is None and nxt & (GAVE | PAID) and not cw & N("maine", "मैंने"):
                tag = "paid"                             # "…advance diya aur kal teen hazaar diye"
            if tag is None:
                tag = ("advance" if cw & ADVANCE else "loan" if cw & LOAN and not cw & PAID else
                       "paid" if cw & PAID or (cw & GAVE and not cw & N("maine", "मैंने")) else None)
            if tag == "advance":
                obs.append({"type": "advance", "value": lo, "ambiguous": False})
                continue
            if tag == "loan":
                if words & N("alag", "separate", "अलग"):
                    obs.append({"type": "context", "category": "private_loan", "text": f"{lo} alag"})
                    continue                             # "udhaar liya, woh alag hai": a private loan
                obs.append({"type": "advance", "value": lo, "ambiguous": True})
                continue
            if tag == "paid":
                obs.append({"type": "payment", "value": lo})
                continue
            if rng and frame.get("asking") == "rate":
                obs.append({"type": "rate", "value": val, "per": "day", "range": rng})
    for d in days_said:
        obs.append({"type": "explicit_days", "value": d})
    # "…800 roz, advance nahi, 2000 mile": no advance, said inside a longer sentence
    if not any(o["type"] == "advance" for o in obs) and any(
            set(tokens(c)) & ADVANCE and set(tokens(c)) & N("nahi", "nahin", "नहीं", "na") and not _number_groups(c)
            for c in _clauses(t)):
        obs.append({"type": "advance", "value": 0, "ambiguous": False})
    if correcting and obs:
        same = [o for o in obs if o["type"] not in ("context",)]
        if len(same) >= 2 and same[-1]["type"] == same[-2]["type"]:
            obs.remove(same[-2])                       # "6 nahi 5 din": keep the second
        for o in obs:
            o["correction"] = True
    if frame.get("asking") in ("advance", "payments") and says_none(text) and not obs:
        obs.append({"type": "advance" if frame["asking"] == "advance" else "payment", "value": 0, "ambiguous": False})
    obs += _context(text)
    return obs


def is_yes(text):
    return parse_yes_no(text) is True


def is_no(text):
    return parse_yes_no(text) is False
