"""Which language is the worker speaking? Text only (Wispr Flow output), no audio, no outside call.

detect(text) -> (code, confidence) with code in {hi, mr, bho, ta, te, bn, en-mix}.
Low confidence means the caller keeps Hindi. The script decides Tamil, Telugu and Bengali; for
Devanagari and Roman text a few common words separate Marathi and Bhojpuri from Hindi.
"""
import re
import unicodedata

SUPPORTED = ("hi", "mr", "bho", "ta", "te", "bn", "en-mix")
# Full fixed-line translations exist for hi and mr. The others are beta (see README "Languages").
BETA = {"bho", "ta", "te", "bn", "en-mix"}
MIN_CONFIDENCE = 0.6

_SCRIPTS = (("ta", "஀", "௿"), ("te", "ఀ", "౿"), ("bn", "ঀ", "৿"))
_N = lambda *ws: {unicodedata.normalize("NFC", w) for w in ws}  # noqa: E731
_MARKERS = {
    "mr": _N("आहे", "आहेत", "केलं", "केले", "दिवस", "मिळाले", "मिळाला", "मला", "माझे", "माझा", "नाही", "किती",
             "पैसे", "मजुरी", "होतो", "होते", "झाले", "aahe", "ahe", "kela", "kele", "divas", "milale",
             "milala", "mala", "majha", "majhe", "naahi", "zale", "zhale", "hoto"),
    "bho": _N("बानी", "बा", "कइनी", "कइले", "हमरा", "हमार", "रहनी", "मिलल", "नइखे", "bani", "baani", "kaini",
              "kaile", "hamra", "hamaar", "milal", "naikhe", "rahni"),
    "hi": _N("है", "हैं", "किया", "मिले", "मिला", "नहीं", "मेरा", "मुझे", "था", "थे", "hai", "hain", "kiya",
             "mile", "mila", "nahi", "mera", "mujhe", "tha", "the", "din", "roz", "paise", "diye"),
}
# "नाही" is Marathi, "नहीं" Hindi; "किती" Marathi, "कितना" Hindi.
_EN = {"i", "the", "worked", "days", "day", "rate", "got", "paid", "salary", "my", "is", "was", "and",
       "so", "far", "received", "per", "advance", "money", "not", "he", "gave", "only"}
_WORD = re.compile(r"[ऀ-ॿ]+|[a-z]+")


def detect(text):
    text = unicodedata.normalize("NFC", (text or "").lower())
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return "hi", 0.0
    for code, lo, hi in _SCRIPTS:
        share = sum(lo <= ch <= hi for ch in letters) / len(letters)
        if share > 0.5:
            return code, round(min(1.0, share), 2)
    words = _WORD.findall(text)
    if not words:
        return "hi", 0.0
    hits = {code: sum(w in ws for w in words) for code, ws in _MARKERS.items()}
    english = sum(w in _EN for w in words)
    best = max(("mr", "bho"), key=lambda c: hits[c])
    if hits[best] >= 2 and hits[best] > hits["hi"]:
        return best, round(min(1.0, 0.5 + 0.1 * (hits[best] - hits["hi"]) + 0.1 * hits[best]), 2)
    if english / len(words) >= 0.5 and hits["hi"] <= 1:
        return "en-mix", round(min(1.0, english / len(words)), 2)
    return "hi", round(min(1.0, 0.5 + 0.1 * hits["hi"]), 2)


def choose(text):
    """The language to switch to, or 'hi' when unsure."""
    code, conf = detect(text)
    return code if conf >= MIN_CONFIDENCE else "hi"
