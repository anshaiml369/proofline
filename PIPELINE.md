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
| Live with an LLM key | **OpenAI `gpt-4.1-mini`** via `OPENAI_API_KEY`, tried first. If that fails: **OpenRouter `openai/gpt-4.1-mini`** via `OPENROUTER_API_KEY`. Settings: temperature 0.4, max 400 tokens, JSON output, 8 s timeout (`LLM_TIMEOUT_S`). Models can be overridden with `OPENAI_MODEL` / `OPENROUTER_MODEL`. | `agent_llm.providers()`, `agent_llm.decide()` |
| | **The LLM is the dialogue policy.** Each turn it gets the frame, the whole conversation and the latest message, and chooses the next move and writes the line (see "The dialogue policy" below). **Python** keeps the frame, accepts only numbers the worker said, breaks loops, forces the read-back and does all the maths. The read-back and the result lines are fixed text from `conversation.py`. | `conversation.step_policy()`, `wage_math.py` |
| | Fallback: if every provider fails or times out, that turn uses the rules below. | `app.turn()` |
| Live without keys | **Rules:** the state machine in `conversation.py` plus the Hinglish number reader in `hinglish_numbers.py` (digits, Roman, Devanagari; tags amounts by "din", "roz", "advance", "mile"). The rules also answer a few off-script topics (hospital or illness, a loan, "3 saal", "ek hafta", "ek mahina") and never repeat the same line twice in a row. | `conversation.step()`, `conversation.local_extract()` |
| `?mode=scripted` | Rules only, always, even when keys are set, so the demo runs the same every time. | `app.turn()` (`scripted` flag) |

Badge: `Text: LLM` or `Text: Rules`, from the `text_source` field of each `/turn` reply.

## The dialogue policy (LLM path)

The conversation is not a fixed list of questions. With a key set, the LLM decides every next move.

**The frame** (Python, per session): the four numbers `days`, `rate`, `advance`, `payments`; `context_notes` (what the worker volunteered: hospital, a loan, years at the site); `unresolved` (numbers heard but unclear); the last question; the turn count. It is sent to the LLM every turn, with the whole conversation (`agent_llm.frame()`, `agent_llm.build_user_message()`).

**The LLM returns** (`prompts/policy.txt`):

```json
{"action": "ask_slot | follow_up | clarify | acknowledge_context | handle_off_topic | rephrase | conclude",
 "target_slot": "days | rate | advance | payments | none",
 "agent_text": "...", "agent_text_hi": "...",
 "extracted": [{"slot": "rate", "value": 650, "confidence": "high"}],
 "context_delta": "Was in hospital for 4 days",
 "intent": "yes | no | other"}
```

**Python's guards** (`conversation.step_policy()`):

| Guard | What it stops |
|---|---|
| A number is stored only if the worker said it (this message or the one before), it is in range, and ₹0 only if they said "nothing" | The model turning "ek hafta" into 7 days or "3 saal" into 1,095 days; "haan" read as ₹0 |
| Several amounts come back as a list; Python adds them | The model doing arithmetic |
| The line may not contain any amount of ₹32 or more that the worker did not say | The model stating a total or an amount owed |
| The line may not be the same words as the last one | Asking the same question again and again |
| A number asked once and rephrased twice with nothing new: Python moves on and marks it `unresolved` (advance and payments assumed ₹0 and flagged; days and rate asked again after the others) | Going round in circles |
| The same question twice in a row with nothing new is replaced by a rephrase; a line identical to either of the last two is never said | "question one, question one" |
| 12 worker turns without all four numbers: the agent stops and points to a union or India Labourline (1800 1800 999) | Endless conversations |
| A number the worker clearly tagged ("rate 700", "advance nahi") is kept if the model missed it | Lost facts in a bundle |
| When all four numbers are known, the next line is always Python's read-back, and the maths runs only on a "haan" the rules also do not read as "nahi" | Skipping the read-back |
| A rejected line is replaced by the rules' answer or a fixed question | Saying anything unsafe |
| A known number comes back different, with no "nahi", "galat" or "sorry": Python asks "Aapne pehle X kaha, ab Y: kaunsa sahi hai?" and keeps both values in the turn log (`conflict_asked`, then `conflict` with the choice) | Silently overwriting a number |
| The three choices, overtime and deductions, the follow-up reply and delete are read by Python, not the LLM | A model choosing to send, escalate or delete |

Each `/turn` reply has `action` (what the policy chose; `python_conflict` when Python asked about a contradiction), `policy_source` (`llm` or `fallback`), `node_path` (the states so far) and `context_notes`; the server log has `action=` and `guarded=` for every turn. The page shows the notes under the four boxes as "Aapne bataya".

## The agent's voice

The browser tries these in order (`speak()` in `static/app.js`):

1. **Recorded clip:** if `static/demo/<hash>.mp3` exists for the line. There are 7 clips, one per agent line of the scripted demo, made with Sarvam Bulbul `bulbul:v4-flash`, speaker `shubh_enhi_companion`, each checked with Saaras speech-to-text. Badge: `Voice: Recorded`.
2. **Sarvam, live:** with `SARVAM_API_KEY` set and not in scripted mode, `/turn` synthesises the line with **Sarvam Bulbul `bulbul:v4-flash`**, mp3, pace 1.0, temperature 0.3, with a 12 s hard deadline, in the speaker for the line's language (`voice_lang` in the reply; `sarvam_tts.VOICES`):

   | Line language | `language_code` | Speaker |
   |---|---|---|
   | hi, bho, en-mix | `hi-IN` | `shubh_enhi_companion` |
   | mr | `mr-IN` | `nilesh_mr_conversation` |
   | bn | `bn-IN` | `arnab_bn_conversation` |
   | ta | `ta-IN` | `gokul_ta_narration` |
   | te | `te-IN` | `kavitha_te_conversation` |

   In the beta languages (bn, ta, te) Python's fixed lines stay Hindi, so they are spoken in the Hindi voice; a reply is never split across two voices. Badge: `Voice: Sarvam`.
3. **Browser voice:** `speechSynthesis` with a voice for the line's language (a Hindi voice such as macOS "Lekha" for Hindi and Marathi), if a clip is missing or cannot play. Badge: `Voice: Browser`.
4. If the browser has no voice at all, the line stays on screen for reading time. Badge: `Voice: off`.

| Mode | Usual voice |
|---|---|
| Live with `SARVAM_API_KEY` | Recorded for the 7 fixed demo lines, Sarvam for everything else |
| Live without keys | Recorded for the 7 fixed lines, browser voice for the rest |
| `?mode=scripted` | Recorded only, all 7 lines. No outside network: every request goes to the app's own origin |

## The case record (audit layer)

| Step | Where |
|---|---|
| Python calculates → `audit.seal()` builds the canonical JSON (sorted keys, no spaces) and its sha256 | `app.save_sealed()`, `audit.py` |
| Stored once in `wage_cases.case_json` / `case_hash`; later saves never overwrite them | `database.save_case()` (`COALESCE`) |
| The card shows `case_hash[:12]`; `GET /state` recomputes the hash (`hash_verified`) | `static/app.js`, `app.state_route()` |
| Send → `POST /mark-sent` → `sent_at` | `database.mark_sent()` |
| Next visit, case sent over 24 h ago (`FOLLOWUP_AFTER_H`) → follow-up question → `followup_log`, `commitment_date` | `app.due_followup()`, `conversation.followup_reply()`, `audit.commitment_from()` |
| Escalate → complaint draft with the hash; Share → `/case/<id>/share` | `audit.escalation_draft()`, `audit.share_text()` |
| "mera case delete karo" → spoken "haan" → `DELETE` | `conversation.handle_command()`, `database.delete_case()` |

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
