"""Hinglish number words, both ways.

- to_words(4200) -> "chaar hazaar do sau"   (what the agent speaks)
- parse_amounts("teen hazaar") -> [3000]     (local fallback when no LLM key, and for scripted mode)

Parsing a spoken number is not arithmetic on the worker's case: it only reads one number.
Combining several amounts (advance + payments) is done in wage_math.py.
"""
import re
import unicodedata

_WORDS_0_99 = (
    "shunya ek do teen chaar paanch chhe saat aath nau das gyaarah baarah terah chaudah pandrah "
    "solah satrah athaarah unnees bees ikkees baais teis chaubees pachchees chhabbees sattaais "
    "atthaais untees tees iktees battees taintees chauntees paintees chhattees saintees adtees "
    "untaalees chaalees iktaalees bayaalees taintaalees chauvaalees paintaalees chhiyaalees "
    "saintaalees adtaalees unchaas pachaas ikyaavan baavan tirpan chauvan pachpan chhappan "
    "sattaavan atthaavan unsath saath iksath baasath tirsath chaunsath painsath chhiyaasath sadsath "
    "adsath unhattar sattar ikhattar bahattar tihattar chauhattar pachhattar chhihattar sathattar "
    "athattar unaasi assi ikyaasi bayaasi tiraasi chauraasi pachaasi chhiyaasi sattaasi atthaasi "
    "nawaasi nabbe ikyaanave baanave tiraanave chauraanave pachaanave chhiyaanave sattaanave "
    "atthaanave ninyaanave"
).split()
assert len(_WORDS_0_99) == 100


def to_words(n):
    """Indian system: lakh, hazaar, sau. 4200 -> 'chaar hazaar do sau'."""
    n = int(n)
    if n < 100:
        return _WORDS_0_99[n]
    parts = []
    for size, name in ((10_000_000, "crore"), (100_000, "lakh"), (1000, "hazaar"), (100, "sau")):
        if n >= size:
            parts.append(f"{to_words(n // size)} {name}")
            n %= size
    if n:
        parts.append(_WORDS_0_99[n])
    return " ".join(parts)


# Spoken forms -> value. Includes common spellings and Devanagari, since Saaras codemix
# often writes Hindi number words in Devanagari ("छह दिन").
_UNITS = {w: i for i, w in enumerate(_WORDS_0_99)}
_UNITS.update({
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "twenty": 20, "thirty": 30, "fifty": 50,
    "chheh": 6, "chhah": 6, "chah": 6, "che": 6, "chhe": 6, "cheh": 6, "chhey": 6, "panch": 5,
    "char": 4, "chaar": 4, "sat": 7, "aat": 8, "dus": 10, "dass": 10, "gyarah": 11, "barah": 12,
    "pandrah": 15, "pachas": 50, "pachaas": 50, "bis": 20, "tis": 30, "chalis": 40, "saath": 60,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "छे": 6,
    "सात": 7, "आठ": 8, "नौ": 9, "दस": 10, "ग्यारह": 11, "बारह": 12, "पंद्रह": 15, "बीस": 20,
    "तीस": 30, "चालीस": 40, "पचास": 50, "साठ": 60, "सत्तर": 70, "अस्सी": 80, "नब्बे": 90,
    # Marathi (Devanagari and Roman), as Wispr Flow may write them
    "सहा": 6, "पाच": 5, "दहा": 10, "नऊ": 9, "अकरा": 11, "चाळीस": 40, "पन्नास": 50, "साठ": 60,
    "saha": 6, "paach": 5, "pach": 5, "daha": 10, "nau": 9,
})
# Marathi hundreds are one word ("सातशे" = 700)
_UNITS.update({
    "शंभर": 100, "दोनशे": 200, "तीनशे": 300, "चारशे": 400, "पाचशे": 500, "सहाशे": 600, "सातशे": 700,
    "आठशे": 800, "नऊशे": 900, "shambhar": 100, "donshe": 200, "teenshe": 300, "tinshe": 300, "chaarshe": 400,
    "charshe": 400, "paachshe": 500, "pachshe": 500, "sahashe": 600, "saatshe": 700, "satshe": 700,
    "aathshe": 800, "naushe": 900,
})
_UNITS = {unicodedata.normalize("NFC", k): v for k, v in _UNITS.items()}
_SCALES = {
    "sau": 100, "so": 100, "hundred": 100, "सौ": 100,
    "hazaar": 1000, "hazar": 1000, "hajar": 1000, "hajaar": 1000, "thousand": 1000, "k": 1000,
    "हज़ार": 1000, "हजार": 1000, "हजाराचे": 1000,
    "lakh": 100_000, "lac": 100_000, "लाख": 100_000,
}
_SCALES = {unicodedata.normalize("NFC", k): v for k, v in _SCALES.items()}
_FRACTIONS = {"dedh": 1.5, "डेढ़": 1.5, "dhai": 2.5, "dhaai": 2.5, "ढाई": 2.5}
_FRACTIONS = {unicodedata.normalize("NFC", k): v for k, v in _FRACTIONS.items()}
_PLUS_HALF = {unicodedata.normalize("NFC", w) for w in ("saadhe", "sadhe", "साढ़े")}
_SPLIT = re.compile(r"\s+(?:aur|and|या|और|phir)\s+|\s*\+\s*")
_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
# Devanagari letters + combining marks (nukta, chandrabindu), minus the danda; then Latin words.
_TOKEN = re.compile(r"\d+(?:\.\d+)?|[\u0900-\u0963\u0970-\u097F]+|[a-z]+")


def _norm(text):
    return unicodedata.normalize("NFC", (text or "").lower())


def _tokens(text):
    return _TOKEN.findall(_norm(text))


_GROUP_TOKEN = re.compile(r"\d+(?:\.\d+)?|[\u0900-\u0963\u0970-\u097F]+|[a-z]+|;")


def _number_groups(text):
    """Separate spoken amounts in one chunk, each with the word before and after it.
    'chaar hazaar do sau' -> [(4200, None, None)]; '6 din 700 roz' -> [(6, None, 'din'), (700, 'din', 'roz')].
    A new amount starts after any other word ("din"), a comma, or a number right after a complete
    number ("2000 1000"). Reading numbers is not arithmetic on the worker's case."""
    text = _norm(text).translate(_DEVANAGARI_DIGITS)
    text = re.sub(r"(?<=\d),(?=\d{2,3}\b)", "", text) # 3,000 -> 3000; 1,20,000 -> 120000
    text = text.replace(",", " ; ")                       # any other comma separates amounts
    text = re.sub(r"(\d)\s*k\b", r"\1 k", text)          # 3k -> 3 k
    toks = _GROUP_TOKEN.findall(text)
    groups = []                                           # [value, start_index, end_index]
    total = current = 0.0
    seen = half = prev_number = gap = False
    last_unit, start, end = None, 0, 0

    def flush():
        nonlocal total, current, seen
        value = total + current
        if seen and abs(value - round(value)) < 1e-6:
            groups.append([int(round(value)), start, end])
        total = current = 0.0
        seen = False

    for i, tok in enumerate(toks):
        is_digit = bool(re.fullmatch(r"\d+(?:\.\d+)?", tok))
        is_unit = tok in _UNITS
        if is_digit or is_unit or tok in _FRACTIONS:
            value = float(tok) if is_digit else _UNITS[tok] if is_unit else _FRACTIONS[tok]
            # "twenty five" stays one number; "6 700" or "6 din 700" are two
            tens_then_unit = (is_unit and prev_number and last_unit is not None and last_unit >= 20
                              and last_unit % 10 == 0 and value < 10)
            if seen and (gap or (prev_number and not tens_then_unit)):
                flush()
            if not seen:
                start = i
            current += value + (0.5 if is_unit and half else 0)
            half, seen, gap, prev_number, end = False, True, False, True, i
            last_unit = value if is_unit else None
        elif tok in _PLUS_HALF:                           # "saadhe teen hazaar"
            if seen and (gap or prev_number):
                flush()
            half, prev_number = True, False
        elif (tok in _SCALES and seen and (prev_number or tok == "k")
              and not (_SCALES[tok] == 100 and current >= 100)):   # "700 so far" is not 70000
            scale = _SCALES[tok]
            if scale == 100:
                current = (current or 1) * 100
            else:
                total += (current or 1) * scale
                current = 0
            prev_number, last_unit, gap, end = False, None, False, i
        else:                                             # any other word ends the amount
            gap = gap or seen
            prev_number = False
    flush()
    words = [t for t in toks if t != ";"]
    if not groups and len(words) == 1 and _SCALES.get(words[0], 0) >= 1000:
        groups.append([_SCALES[words[0]], 0, 0])          # a bare "hazaar" is one thousand

    def nearby(j, step, n=2):
        """Up to n words next to an amount, stopping at a comma or another number."""
        found = []
        while 0 <= j < len(toks) and len(found) < n:
            t = toks[j]
            if t == ";" or t[0].isdigit() or t in _UNITS:
                break
            if t not in _SCALES:
                found.append(t)
            j += step
        return tuple(found)

    return [(v, nearby(s_ - 1, -1), nearby(e_ + 1, 1)) for v, s_, e_ in groups]


def amount_groups(text):
    """[(value, words_before, words_after)] for every separate amount in the utterance."""
    out = []
    for chunk in _SPLIT.split(text or ""):
        out.extend(_number_groups(chunk))
    return out


def parse_amounts(text):
    """All amounts in an utterance: 'do hazaar aur ek hazaar' -> [2000, 1000], '6 din 700 roz' -> [6, 700]."""
    return [g[0] for g in amount_groups(text)]


def _parse_one(text):
    """Exactly one spoken amount, or None."""
    values = parse_amounts(text)
    return values[0] if len(values) == 1 else None


_YES = {"haan", "haa", "ha", "han", "haanji", "ji", "jee", "yes", "yeah", "yep", "ok", "okay", "theek",
        "thik", "sahi", "bilkul", "bhejo", "bhej", "bhejiye", "kardo", "हाँ", "हां", "हा", "जी", "सही",
        "ठीक", "बिल्कुल", "भेजो", "भेज", "होय", "hoy", "बरोबर", "barobar", "पाठवा"}
_NO = {"nahi", "nahin", "nai", "na", "naa", "no", "nope", "galat", "mat", "नहीं", "नही", "ना", "गलत", "मत",
       "नाही", "naahi", "चूक", "chuk"}
_ONLY_YES = {"हो", "ho"}       # Marathi "yes", but also part of Hindi "हो गया": counts only on its own


_YES = {unicodedata.normalize("NFC", w) for w in _YES}
_NO = {unicodedata.normalize("NFC", w) for w in _NO}


def parse_yes_no(text):
    """True / False / None. Any negation wins: 'sahi nahi hai' -> False."""
    tokens = set(_tokens(text))
    if tokens & _NO:
        return False
    if tokens & _YES or (tokens and tokens <= _ONLY_YES):
        return True
    return None


_UNSURE = {unicodedata.normalize("NFC", w) for w in
           ("pata", "maloom", "malum", "yaad", "shayad", "पता", "मालूम", "याद", "शायद")}


def says_none(text):
    """'kuch nahi', 'nahi mila', 'zero' -> worker received nothing."""
    tokens = set(_tokens(text))
    if tokens & _UNSURE:          # "pata nahi" = don't know, not "got nothing"
        return False
    return bool(tokens & (_NO | {"kuch", "zero", "shunya", "कुछ", "nil", "nothing", "none"})) and not parse_amounts(text)


def tokens(text):
    """Lower-case words of the text (Roman and Devanagari), for keyword checks."""
    return _tokens(text)


def says_nothing(text):
    """The worker says they got nothing for some fact, even if other amounts are in the same
    sentence: 'advance nahi mila, 3000 mile'. 'pata nahi' (don't know) is not nothing."""
    words = set(_tokens(text))
    if words & _UNSURE:
        return False
    return bool(words & (_NO | {"kuch", "zero", "shunya", "कुछ", "nothing", "none"})) or 0 in parse_amounts(text)
