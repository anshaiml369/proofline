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
})
_UNITS = {unicodedata.normalize("NFC", k): v for k, v in _UNITS.items()}
_SCALES = {
    "sau": 100, "so": 100, "hundred": 100, "सौ": 100,
    "hazaar": 1000, "hazar": 1000, "hajar": 1000, "hajaar": 1000, "thousand": 1000, "k": 1000,
    "हज़ार": 1000, "हजार": 1000,
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


def _parse_one(text):
    """One spoken amount, or None. 'chaar hazaar do sau' -> 4200, '3,000' -> 3000, 'dedh hazaar' -> 1500."""
    text = _norm(text).translate(_DEVANAGARI_DIGITS)
    text = re.sub(r"(?<=\d),(?=\d)", "", text)          # 3,000 -> 3000
    text = re.sub(r"(\d)\s*k\b", r"\1 k", text)          # 3k -> 3 k
    total, current, seen, half = 0.0, 0.0, False, False
    prev_number = False      # a scale word counts only right after a number: "so far" is not "sau"
    for tok in _TOKEN.findall(text):
        is_number = False
        if re.fullmatch(r"\d+(?:\.\d+)?", tok):
            current += float(tok)
            seen = is_number = True
        elif tok in _UNITS:
            current += _UNITS[tok] + (0.5 if half else 0)
            half = False
            seen = is_number = True
        elif tok in _FRACTIONS:
            current += _FRACTIONS[tok]
            seen = is_number = True
        elif tok in _PLUS_HALF:
            half = True
        elif tok in _SCALES and seen and (prev_number or tok in ("k",)):
            scale = _SCALES[tok]
            if scale == 100:
                if current < 100:                         # "saat sau" = 700, but "700 so far" stays 700
                    current = (current or 1) * 100
            else:
                total += (current or 1) * scale
                current = 0
        prev_number = is_number
    if not seen:
        return None
    value = total + current
    return int(round(value)) if abs(value - round(value)) < 1e-6 else None


def parse_amounts(text):
    """All amounts in an utterance, split on 'aur' / '+': 'do hazaar aur ek hazaar' -> [2000, 1000]."""
    values = []
    for chunk in _SPLIT.split(text or ""):
        value = _parse_one(chunk)
        if value is not None:
            values.append(value)
    return values


_YES = {"haan", "haa", "ha", "han", "haanji", "ji", "jee", "yes", "yeah", "yep", "ok", "okay", "theek",
        "thik", "sahi", "bilkul", "bhejo", "bhej", "bhejiye", "kardo", "हाँ", "हां", "हा", "जी", "सही",
        "ठीक", "बिल्कुल", "भेजो", "भेज"}
_NO = {"nahi", "nahin", "nai", "na", "naa", "no", "nope", "galat", "mat", "नहीं", "नही", "ना", "गलत", "मत"}


_YES = {unicodedata.normalize("NFC", w) for w in _YES}
_NO = {unicodedata.normalize("NFC", w) for w in _NO}


def parse_yes_no(text):
    """True / False / None. Any negation wins: 'sahi nahi hai' -> False."""
    tokens = set(_tokens(text))
    if tokens & _NO:
        return False
    if tokens & _YES:
        return True
    return None


_UNSURE = {unicodedata.normalize("NFC", w) for w in
           ("pata", "maloom", "malum", "yaad", "shayad", "पता", "मालूम", "याद", "शायद")}


def says_none(text):
    """'kuch nahi', 'nahi mila', 'zero' -> worker received nothing."""
    tokens = set(_tokens(text))
    if tokens & _UNSURE:          # "pata nahi" = don't know, not "got nothing"
        return False
    return bool(tokens & (_NO | {"kuch", "zero", "shunya", "कुछ"})) and not parse_amounts(text)
