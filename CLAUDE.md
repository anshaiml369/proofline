# Project: India Runs on Voice — Voice Skeleton

## Tech stack
- Python 3.11 + Flask
- Single-page HTML/JS frontend (MediaRecorder API for audio)
- OpenAI API for LLM extraction (key in .env)
- Wispr Flow API for STT (key will be added later; fallback to OpenAI Whisper until then)

## Rules
- Do NOT refactor existing files without asking.
- Test after every file change. Run the app and confirm it loads.
- Commit after every working milestone.
- Keep scope to ONE loop: voice in → structured JSON out → card displayed.
- Kill any feature not in the 30-second demo.

## The 30-second demo (the only thing that matters)
User presses one button → speaks one sentence → structured cards appear with green/pass or red/fail status. Nothing else.
