"""Pre-record the scripted demo (?mode=scripted) so it plays with no network.

Runs the demo conversation through the real state machine, then saves:
  static/demo/<hash>.mp3   every agent line (same file name the server looks up)
  static/demo/worker_N.mp3 every worker line, in a different voice

Run once with SARVAM_API_KEY set:  python3 scripts/make_demo_audio.py
"""
import base64
import os
import sys

import httpx
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()
import conversation as c  # noqa: E402
import sarvam_tts  # noqa: E402

WORKER_LINES = [
    "Mujhe thekedar ne is hafte poore paise nahi diye.",
    "Chhe din.",
    "Saat sau rupaye.",
    "Paanch sau.",
    "Teen hazaar.",
    "Haan.",
    "Haan.",
]
# Worker voice is spoken from Devanagari: romanised "Saat sau" came back from STT as ₹600.
WORKER_TTS_TEXT = [
    "मुझे ठेकेदार ने इस हफ्ते पूरे पैसे नहीं दिए।",
    "छह दिन।",
    "सात सौ रुपये।",
    "पाँच सौ।",
    "तीन हज़ार।",
    "हाँ।",
    "हाँ।",
]
WORKER_SPEAKER = "aditya_hi_conversational"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "demo")


def agent_lines():
    s = c.new_session()
    lines = [c.opening(s)["agent_text"]]
    for w in WORKER_LINES:
        lines.append(c.step(s, w, c.local_extract)["agent_text"])
    lines.append(c.mark_sent(s)["agent_text"])  # after "Send to contractor"
    return lines


def main():
    key = os.getenv("SARVAM_API_KEY")
    if not key:
        sys.exit("SARVAM_API_KEY not set")
    os.makedirs(OUT, exist_ok=True)
    for line in agent_lines():
        name = sarvam_tts.synthesize(line, key, OUT)
        print("agent ", name or "FAILED", "|", line)
    for i, line in enumerate(WORKER_LINES):
        path = os.path.join(OUT, f"worker_{i}.mp3")
        if os.path.exists(path):
            continue
        r = httpx.post(sarvam_tts.TTS_URL, headers={"api-subscription-key": key},
                       json={"text": WORKER_TTS_TEXT[i], "language_code": "hi-IN", "model": sarvam_tts.TTS_MODEL,
                             "speaker": WORKER_SPEAKER, "output_audio_codec": "mp3", "pace": 0.95},
                       timeout=httpx.Timeout(15.0))
        r.raise_for_status()
        open(path, "wb").write(base64.b64decode(r.json()["audios"][0]))
        print("worker", f"worker_{i}.mp3", "|", line)


if __name__ == "__main__":
    main()
