"""OPTIONAL: pre-record the agent's fixed lines with Sarvam, so browsers without a Hindi
voice still hear the agent. Not needed to run the app.

Runs the demo conversation through the real state machine and saves static/demo/<hash>.mp3
for every agent line (the same file name app.py looks up). Needs SARVAM_API_KEY:

    python3 scripts/make_demo_audio.py
"""
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()
import conversation as c  # noqa: E402
import sarvam_tts  # noqa: E402

WORKER_LINES = ["Mujhe thekedar ne is hafte poore paise nahi diye.", "Chhe din.", "Saat sau rupaye.",
                "Paanch sau.", "Teen hazaar.", "Haan.", "Haan."]
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "demo")


def agent_lines():
    s = c.new_session()
    lines = [c.opening(s)["agent_text"]]
    for w in WORKER_LINES:
        lines.append(c.step(s, w, c.local_extract)["agent_text"])
    lines.append(c.mark_sent(s)["agent_text"])
    return lines


if __name__ == "__main__":
    key = os.getenv("SARVAM_API_KEY")
    if not key:
        sys.exit("SARVAM_API_KEY not set")
    os.makedirs(OUT, exist_ok=True)
    for line in agent_lines():
        print(sarvam_tts.synthesize(line, key, OUT) or "FAILED", "|", line)
