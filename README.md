# PagarSaathi

**A Hinglish voice agent that works out a daily-wage worker's unpaid wages.**

A worker says: *"Thekedar ne poore paise nahi diye."* PagarSaathi asks four questions, one at a time, by voice:
1. How many days did you work?
2. What daily rate was agreed?
3. Did you get an advance?
4. How much have you been paid so far?

It reads all four facts back and waits for "haan". Python then works out what is still owed, and the agent says the result out loud. If the worker wants, it prepares a payment request and opens WhatsApp with the message ready to send.

Built for the *India Runs on Voice* hackathon (Scaler × Wispr Flow).

## The demo conversation

| | |
|---|---|
| Worker | Mujhe thekedar ne is hafte poore paise nahi diye. |
| Agent | Aapne kitne din kaam kiya? |
| Worker | Chhe din. |
| Agent | Roz ki mazdoori kitni tay hui thi? |
| Worker | Saat sau rupaye. |
| Agent | Koi advance mila tha pehle? |
| Worker | Paanch sau. |
| Agent | Ab tak kitne paise mile? |
| Worker | Teen hazaar. |
| Agent | Confirm karta hoon: chhe din, saat sau roz, paanch sau advance, teen hazaar paid. Sahi hai? |
| Worker | Haan. |
| Agent | Kul kamaai chaar hazaar do sau. Mila teen hazaar paanch sau. Baaki saat sau rupaye. Thekedar ko payment request bhejun? |
| Worker | Haan. |

The screen then shows the calculation (6 × ₹700 = ₹4,200, minus ₹500 advance, minus ₹3,000 paid = **₹700 outstanding**). The message preview appears next, and only then the green **Send to contractor** button.

## How it works

```
mic ─▶ Sarvam Saaras v4 (codemix STT) ─▶ OpenRouter: read ONE number or yes/no ─▶ conversation.py (state machine)
                                                                                         │
                       Sarvam Bulbul v4 Flash (hi-IN TTS) ◀─ agent's next line ◀─ wage_math.py (all arithmetic)
```

- **The LLM never does arithmetic.** It only returns `{"field", "value", "confidence"}` for the question just asked. If the worker names several amounts ("do hazaar aur ek hazaar"), it lists them in `parts`, and Python adds them.
- **Python does all the maths** in `wage_math.py`:
  - `expected = days × rate`
  - `received = advance + payments`
  - `outstanding = max(0, expected − received)`
- **The read-back is mandatory.** Nothing is calculated until the worker says "haan" to all four facts. "Nahi" starts the questions again.
- **Unclear answers:** a low-confidence or empty answer gets the same question again in simpler words. After a second miss, the page switches to typing.
- **Implausible numbers are re-asked,** for example 500 days or ₹5 a day.
- **Nothing owed:** the agent says *"Hisaab ke hisaab se koi paisa baaki nahi hai"*, and no send button appears.
- **WhatsApp is a plain deep link** (`https://wa.me/?text=…`). There is no WhatsApp API. The worker picks the contractor's chat and presses send.
- **Saved records:** each finished case is stored in SQLite (`wage_cases`).

### State machine (`conversation.py`)

`START → ASK_DAYS → ASK_RATE → ASK_ADVANCE → ASK_PAYMENTS → CONFIRM → CALCULATE → READ_RESULT → ASK_SEND → SHOW_PREVIEW → SEND_BUTTON → DONE`

## Modes

| URL | What it does |
|---|---|
| `/` | Voice: tap the mic, speak, tap again. The agent replies by voice. |
| `/?mode=text` | Typed answers instead of the mic. It also works with no API keys, using simple built-in rules. |
| `/?mode=scripted` | Replays the demo conversation above with pre-recorded audio (about 55 s). It needs no mic and no internet. Use it as a backup for the video. |

If speech-to-text hears nothing, the page shows *"Sun nahi paya, phir se boliye"* and the worker can try again. If text-to-speech fails, the question is shown as text and the conversation carries on.

## Run with Docker

```bash
docker compose up
```

Open http://localhost:5050. Port 5050 is used on the host because macOS uses port 5000 for AirPlay; inside the container the app runs on 5000.

- **Keys are optional.** With no `.env`, the app still starts and the main screen shows **"API key not set"** with the missing keys. Typed mode and the scripted demo still work fully.
- **No secrets in the image.** `.dockerignore` keeps `.env` and the database out.
- **Data is not kept.** The SQLite file lives inside the container.

## Run locally

You need Python 3.11.

```bash
pip3 install -r requirements.txt
```

```bash
cp .env.example .env
```

| Variable | Used for |
|---|---|
| `SARVAM_API_KEY` | Speech-to-text (Saaras v4, codemix) and the agent's voice (Bulbul v4 Flash) |
| `OPENROUTER_API_KEY` | Reading numbers and yes/no from the worker's words (default model `openai/gpt-4o-mini`) |
| `OPENAI_API_KEY` | Optional fallback for both: Whisper for speech-to-text, gpt-4o-mini for understanding |

```bash
python3 app.py
```

Then open http://127.0.0.1:5050.

## Tests

```bash
python3 -m unittest discover tests
```

The tests cover:
- the wage maths, including the never-negative outstanding amount and bad input;
- Hinglish number words in both directions;
- the demo conversation;
- the mandatory confirm step;
- a re-ask, then the typed fallback;
- multiple payments added in Python;
- the nothing-owed path.

## Pre-recorded audio

`static/demo/` holds the agent's fixed lines and the worker's demo lines. Each clip was checked by sending it back through Saaras. Live mode reuses these clips too, so the fixed lines play instantly. To regenerate them (needs `SARVAM_API_KEY`):

```bash
python3 scripts/make_demo_audio.py
```

## Honest limits

- **It calculates; it does not enforce.** The payment request is a message the worker chooses to send. Nothing is sent automatically.
- **Simple wage cases only:** one daily rate. Overtime, half days and deductions are not handled yet.
- **No login and no accounts.** Conversations in progress live in server memory (one gunicorn worker); finished cases go to SQLite.
- **Voice testing so far:** recognition was tested with synthetic Hindi voices fed through Chrome's recorder, not yet with workers in a noisy site. The read-back step is there to catch mishearings.
- **`/turn` needs no login and calls paid APIs.** Set spend limits on your keys before any public deploy.

## Files

| Path | What it is |
|---|---|
| `app.py` | Flask: `GET /`, `POST /turn`, `GET /health`; Sarvam STT and the OpenRouter call |
| `conversation.py` | The state machine and the local rule-based reader |
| `wage_math.py` | All arithmetic, as pure functions |
| `hinglish_numbers.py` | Number words, both ways (4200 ⇄ "chaar hazaar do sau") |
| `sarvam_tts.py` | Bulbul v4 Flash TTS, hi-IN, mp3, cached |
| `database.py` | SQLite `wage_cases` table |
| `prompts/turn.txt` | The extraction prompt |
| `templates/index.html`, `static/app.js` | The one screen: mic, question, turn log, calculation, preview, send |
| `scripts/make_demo_audio.py` | Records the scripted-mode audio |

The earlier Proofline project is kept on the `proofline-archive` branch.
