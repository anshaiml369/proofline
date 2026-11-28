"""Sarvam Bulbul v4 Flash voice (hi-IN, mp3) for the agent's replies. Optional: needs SARVAM_API_KEY.

When the key is set, every agent line without a pre-recorded clip is synthesised here (the
recorded clips in static/demo/ were made with the same model and speaker). Returns None on any
failure, timeout or missing key; the page then speaks with the browser's own voice instead.
"""
import base64
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

import httpx

TTS_URL = "https://api.sarvam.ai/text-to-speech"
TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v4-flash")
# Always name a speaker: in testing, a v4-flash request without one hung for minutes.
TTS_SPEAKER = os.getenv("SARVAM_TTS_SPEAKER", "shubh_enhi_companion")
TTS_DEADLINE_S = 12  # hard wall-clock limit; httpx's timeout is per read, not total

_pool = ThreadPoolExecutor(max_workers=4)

# Spoken-only spellings for words Bulbul misreads in Roman script (checked by sending the
# audio back through Saaras). The on-screen text is unchanged.
PRONOUNCE = {
    "PagarSaathi": "पगार साथी",
    "WhatsApp": "व्हाट्सऐप",
    "bhejun": "भेजूँ",
    "Thekedar": "ठेकेदार",
    "thekedar": "ठेकेदार",
    "escalate karun": "एस्केलेट करूँ",
    "katauti": "कटौती",
}


def spoken(text):
    for word, say in PRONOUNCE.items():
        text = text.replace(word, say)
    return text


# One verified speaker per language: each was checked by sending its audio of a test line
# (including "700 rupaye") back through Saaras speech-to-text. Bhojpuri and code-mixed English
# use the Hindi voice (no Bhojpuri voice; the Hindi one misheard Bhojpuri words in that check).
VOICES = {
    "hi": ("hi-IN", TTS_SPEAKER), "bho": ("hi-IN", TTS_SPEAKER), "en-mix": ("hi-IN", TTS_SPEAKER),
    "mr": ("mr-IN", "nilesh_mr_conversation"),
    "bn": ("bn-IN", "arnab_bn_conversation"),
    "ta": ("ta-IN", "gokul_ta_narration"),
    "te": ("te-IN", "kavitha_te_conversation"),
}


def voice(lang):
    return VOICES.get(lang or "hi", VOICES["hi"])


def audio_name(text, lang="hi"):
    code, speaker = voice(lang)
    tag = f"{TTS_MODEL}|{speaker}|{text}" if code == "hi-IN" else f"{TTS_MODEL}|{code}|{speaker}|{text}"
    return hashlib.sha1(tag.encode()).hexdigest()[:20] + ".mp3"


def _request(text, api_key, lang="hi"):
    code, speaker = voice(lang)
    resp = httpx.post(
        TTS_URL,
        headers={"api-subscription-key": api_key},
        json={"text": spoken(text) if code == "hi-IN" else text, "language_code": code, "model": TTS_MODEL,
              "speaker": speaker,
              "output_audio_codec": "mp3", "pace": 1.0, "temperature": 0.3},
        timeout=httpx.Timeout(10.0),
    )
    resp.raise_for_status()
    return base64.b64decode(resp.json()["audios"][0])


def speak(text, api_key=None, out_dir=None, log=None, lang="hi"):
    """Alias: speak(text) -> mp3 file name, or None if the key is missing or the call fails."""
    return synthesize(text, api_key, out_dir, log, lang) if api_key and out_dir else None


def synthesize(text, api_key, out_dir, log=None, lang="hi"):
    """Write <out_dir>/<hash>.mp3 for `text` if needed. Returns the file name, or None if TTS failed."""
    if not api_key or not text:
        return None
    name = audio_name(text, lang)
    path = os.path.join(out_dir, name)
    if os.path.exists(path):
        return name
    try:
        audio = _pool.submit(_request, text, api_key, lang).result(timeout=TTS_DEADLINE_S)
    except FutureTimeout:
        if log:
            log.warning("Sarvam TTS timed out after %ss", TTS_DEADLINE_S)
        return None
    except Exception as e:  # network, 4xx/5xx, bad JSON
        if log:
            log.warning("Sarvam TTS failed (%s)", type(e).__name__)
        return None
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(audio)
    os.replace(tmp, path)
    return name
