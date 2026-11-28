# Where does each reply come from?

This page is written from the code (`app.py`, `agent_llm.py`, `conversation.py`, `sarvam_tts.py`, `static/app.js`). Every agent line in the app also shows its source in a small grey badge, for example `Text: LLM · Voice: Sarvam`.

## The worker's words (input)

| Mode | Source |
|---|---|
| All modes | **Wispr Flow**, OS-level dictation on the worker's device (Mac: double-tap Fn; iPhone: the Wispr Flow keyboard). The words land in the answer box as text. |
| `?mode=scripted` | `static/app.js` types each line of `SCRIPT` into the box and presses Continue. |

**There is no microphone, MediaRecorder or speech-to-text in the app, by design.** Wispr Flow does the speech-to-text on the device, so `/health` always reports `"stt": false`. The page can't tell dictated text from typed text, so the worker badge reads `Wispr Flow / typed`. (Sarvam Saaras was used only offline, to check the recorded clips. The app never calls it.)

## The agent's text

| Mode | Source | Code |
|---|---|---|
| Live with an LLM key | **OpenAI `gpt-4.1-mini`** via `OPENAI_API_KEY`, tried first. If that fails: **OpenRouter `openai/gpt-4.1-mini`** via `OPENROUTER_API_KEY`. Settings: temperature 0.3, max 300 tokens, JSON output, 8 s timeout (`LLM_TIMEOUT_S`). Models can be overridden with `OPENAI_MODEL` / `OPENROUTER_MODEL`. | `agent_llm.providers()`, `agent_llm.understand()` |
| | The LLM returns the facts it heard plus a short reply (`say`) and an optional clarifying question (`ask`). **Python** validates the facts, adds multiple amounts, runs the read-back and does all the maths. The questions, the read-back and the result lines are fixed text from `conversation.py`. | `conversation.step_llm()`, `wage_math.py` |
| | Fallback: if every provider fails or times out, that turn uses the rules below. | `app.turn()` |
| Live without keys | **Rules:** the state machine in `conversation.py` plus the Hinglish number reader in `hinglish_numbers.py` (digits, Roman, Devanagari; tags amounts by "din", "roz", "advance", "mile"). | `conversation.step()`, `conversation.local_extract()` |
| `?mode=scripted` | Rules only, always, even when keys are set, so the demo runs the same every time. | `app.turn()` (`scripted` flag) |

Badge: `Text: LLM` or `Text: Rules`, from the `text_source` field of each `/turn` reply.

## The agent's voice

The browser tries these in order (`speak()` in `static/app.js`):

1. **Recorded clip:** if `static/demo/<hash>.mp3` exists for the line. There are 9 clips, one per line of the scripted demo, made with Sarvam Bulbul `bulbul:v4-flash`, speaker `shubh_enhi_companion`. Badge: `Voice: Recorded`.
2. **Sarvam, live:** with `SARVAM_API_KEY` set and not in scripted mode, `/turn` synthesises the line with **Sarvam Bulbul `bulbul:v4-flash`, speaker `shubh_enhi_companion`**, `hi-IN`, mp3, pace 1.0, temperature 0.3, with a 12 s hard deadline. Badge: `Voice: Sarvam`.
3. **Browser voice:** `speechSynthesis` with a Hindi (`hi-IN`) voice, such as macOS "Lekha", if a clip is missing or cannot play. Badge: `Voice: Browser`.
4. If the browser has no voice at all, the line stays on screen for reading time. Badge: `Voice: off`.

| Mode | Usual voice |
|---|---|
| Live with `SARVAM_API_KEY` | Recorded for the 9 fixed demo lines, Sarvam for everything else |
| Live without keys | Recorded for the 9 fixed lines, browser voice for the rest |
| `?mode=scripted` | Recorded only, all 9 lines. No outside network: every request goes to the app's own origin |

## `/health`

`GET /health` shows what the running server can do:

```json
{"status": "ok", "key_set": false, "llm": false, "llm_provider": null, "voice": false,
 "stt": false, "mode": "keyless", "missing": ["OPENAI_API_KEY or OPENROUTER_API_KEY", "SARVAM_API_KEY"]}
```

- `llm`: an OpenAI or OpenRouter key is set.
- `llm_provider`: which provider is tried first.
- `voice`: `SARVAM_API_KEY` is set.
- `stt`: always false, because Wispr Flow does speech-to-text on the device.
- `mode`: `live` if any key is set, otherwise `keyless`. Scripted mode is chosen per page (`?mode=scripted`), not per server.

### Live Railway right now

```
$ curl -s https://pagarsaathi.up.railway.app/health
{"key_set":true,"llm":true,"llm_provider":"openai","missing":[],"mode":"live","status":"ok","stt":false,"voice":true}
# captured 28 Nov 2026 after the keys were added in Railway Variables
```

### To switch on the LLM and the Sarvam voice on Railway

Go to Railway → project **perceptive-growth** → service **web** → **Variables** → **New Variable**, and add:

| Variable | Switches on |
|---|---|
| `OPENAI_API_KEY` (or `OPENROUTER_API_KEY`) | `"llm": true`: conversational replies |
| `SARVAM_API_KEY` | `"voice": true`: Sarvam Bulbul voice |

Railway redeploys on its own. Then `curl -s https://pagarsaathi.up.railway.app/health` should show `"llm": true, "voice": true, "mode": "live"`.
