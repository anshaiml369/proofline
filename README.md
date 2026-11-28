# PagarSaathi

**Bolo, hisaab pao.** A daily-wage worker tells PagarSaathi what happened, by voice through Wispr Flow. A Hinglish agent asks four questions, reads the facts back, and Python works out exactly how much is still owed. With one tap, a payment request opens in WhatsApp, ready to send to the contractor.

Built for the *India Runs on Voice* hackathon (Scaler × Wispr Flow).

> **Live app: https://pagarsaathi.up.railway.app** · Backup demo: [`/?mode=scripted`](https://pagarsaathi.up.railway.app/?mode=scripted) · Pitch deck: [`PITCH_DECK.md`](PITCH_DECK.md) · Where each reply comes from: [`PIPELINE.md`](PIPELINE.md) · Demo video: _link to be added_

## The problem

A daily-wage worker (construction, loading, domestic or farm work) agrees a daily rate by word of mouth. At the end of the week the contractor pays "something", minus an advance given earlier. Nothing is written down.

- The worker often can't say on the spot how much is still owed.
- Without a clear figure, a written request is hard to make.
- Formal routes exist, but they start with paperwork. The government's [SAMADHAN portal](https://samadhan.labour.gov.in) takes unpaid-wage claims, for example.

## The user

A daily-wage worker who speaks Hindi or Hinglish, has a phone, and may not be comfortable typing or doing the sums under pressure. A union or NGO volunteer helping that worker is the second user.

## The solution: one flow

```
Worker speaks (Wispr Flow) → text box → agent asks: days? rate? advance? paid so far?
→ agent reads all four back: "Sahi hai?" → "Haan" → Python calculates
→ agent says what is owed → "Payment request bhejun?" → "Haan"
→ message preview → green "Send to contractor" → WhatsApp opens, message pre-filled
```

- **Python does all the arithmetic** in [`wage_math.py`](wage_math.py):
  - `expected = days × rate`
  - `received = advance + payments`
  - `outstanding = max(0, expected − received)`
  - No model ever calculates.
- **The read-back is mandatory.** Nothing is calculated until the worker says "haan". "Nahi" starts the questions again.
- **Unclear answers** get the same question again in simpler words. After two misses the case is flagged *needs assistance*:
  - For advance or payments, the agent records zero, says so, and moves on. The worker can correct it at the read-back.
  - For days or the daily rate, it keeps asking, with a hint to get help, because those can't be guessed.
- **Nothing owed:** the agent says *"Hisaab ke hisaab se koi paisa baaki nahi hai"*, and no send button appears.
- **WhatsApp is a plain link** (`https://wa.me/?text=…`), with no WhatsApp API. The worker picks the contractor's chat and presses send.

## How Wispr Flow is used (the architectural rule)

**Wispr Flow is the product's voice layer.** It is OS-level dictation:
- **Mac:** double-tap Fn.
- **iPhone:** the Wispr Flow keyboard.

The worker speaks, and the words land in PagarSaathi's text box. **The app receives text, and needs no Wispr Flow API key and no speech-to-text service.** The page has no microphone button by design.

Setup steps are in [`WISPR_FLOW_SETUP.md`](WISPR_FLOW_SETUP.md).

| Part | With keys | With no keys |
|---|---|---|
| Voice in | Wispr Flow (OS-level dictation) | Same: Wispr Flow needs no key |
| Understanding and replying | An LLM (OpenAI `gpt-4.1-mini`, or OpenRouter) reads each message, hears several facts at once, takes corrections, and replies to what the worker actually said | Built-in Hinglish rules: digits, Roman, Devanagari, "nahi mila" |
| Maths | `wage_math.py` (Python) | Same |
| Voice out | Sarvam Bulbul, a natural Hindi voice | Pre-recorded Sarvam clips for fixed lines, then the browser's own voice |

**Every line shows its source.** A small grey badge under each agent line reads, for example, `Text: LLM · Voice: Sarvam` or `Text: Rules · Voice: Recorded`. Worker lines read `Wispr Flow / typed`. The full pipeline, with the exact model and voice names, is in [`PIPELINE.md`](PIPELINE.md).

**The LLM never calculates.** It returns the facts it heard as JSON. Python checks each one, adds multiple amounts, still insists on the "Sahi hai?" read-back, and does all the maths. If the LLM fails or takes over 8 seconds, that turn uses the built-in rules.

### A real conversation (LLM path)

```
Agent:  Namaste, main PagarSaathi hoon. Bataiye, paise ko lekar kya pareshani hai?
Worker: Bhai thekedar ne poore paise nahi diye, kya karun?
Agent:  Chinta mat kijiye, main aapki madad karunga. Kitne din kaam kiya tha aapne?
Worker: Monday se Saturday tak kaam kiya
Agent:  Achha, aapne Monday se Saturday tak 6 din kaam kiya. Roz ki mazdoori kitni tay hui thi?
...
Worker: Nahi, rate 800 tha
Agent:  Theek hai, aapka roz ka rate 800 rupaye hai. Confirm karta hoon: chhe din, aath sau roz, ... Sahi hai?
```

## Run locally

You need Python 3.11.

```bash
pip3 install -r requirements.txt
```

```bash
python3 app.py
```

Open http://127.0.0.1:5050. No `.env` is needed. The dev server uses port 5050, not 5000, because macOS AirPlay Receiver already listens on port 5000.

## Run with Docker

```bash
docker compose up
```

Open http://localhost:5000. On a Mac, macOS AirPlay already holds port 5000. Use another port there:

```bash
HOST_PORT=5050 docker compose up
```

## What happens without keys

Everything in the core flow works:
- the page,
- the conversation,
- the maths,
- the spoken replies (browser voice),
- the WhatsApp message,
- the scripted demo.

`GET /health` returns `{"status": "ok", "llm": false, "voice": false, "stt": false, "mode": "keyless", "missing": [...]}`, and the page shows a banner naming the missing keys. Keys in `.env` (see `.env.example`) or in Railway → web → Variables switch on the LLM conversation and the Sarvam voice.

## Modes

- `/`: normal use. Dictate with Wispr Flow, or type, then press **Continue**.
- `/?mode=text`: the same flow, labelled "Text mode", for a judge who will type rather than dictate.
- `?debug=1` (with any mode): logs every audio play, pause, end and error in the browser console.
- `/?mode=scripted`: the backup demo. It types each demo answer into the box as Wispr Flow would and presses Continue by itself, in about 55 seconds. It always uses the built-in rules and pre-recorded voice, so it calls no outside service and runs the same every time.

## API

`POST /turn` with JSON `{session_id, text}` returns `{agent_text, speak_text, state, done, case_data}`.
- Leave out `session_id` to start a conversation; the agent speaks first.
- Send `{session_id, event: "sent"}` when the worker taps Send.
- States: `START → ASK_DAYS → ASK_RATE → ASK_ADVANCE → ASK_PAYMENTS → CONFIRM → CALCULATE → READ_RESULT → ASK_SEND → SHOW_PREVIEW → DONE`.

## Tests

```bash
pip3 install -r requirements-dev.txt
```

```bash
python3 -m pytest
```

There are 54 tests. They need no network or keys (the LLM is faked). They cover:
- the three required wage cases: (6, 700, 500, 3000) → 700; (5, 800, 0, 4000) → 0; (10, 500, 200, 3000) → 1800;
- the demo conversation and Wispr-style text (digits, ₹, Devanagari);
- the mandatory confirm step;
- re-ask, then *needs assistance*;
- multiple payments added in Python;
- "pata nahi" not being read as ₹0;
- the nothing-owed path;
- the LLM path: several facts in one sentence, corrections at the read-back, Python adding amounts, "haan" never read as ₹0, the reply never asking its own question, falling back to rules when the LLM fails;
- "so far" not being read as "sau";
- several amounts in one answer without keys ("6 din, 700 roz" is 6 days and ₹700, not 706);
- Hinglish error pages, and the `/health` fields.

## Built with

- **Flask** (Python 3.11) and **gunicorn**
- **Wispr Flow**: the voice layer (OS-level dictation)
- **Browser SpeechSynthesis**: the agent's voice
- **OpenAI `gpt-4.1-mini`**, with **OpenRouter** as backup: the optional conversational layer; it never calculates
- **Sarvam Bulbul `bulbul:v4-flash`**: the agent's natural Hindi voice (live, and the 9 recorded clips)
- **Sarvam Saaras v4**: used offline only, to check that every recorded clip says the right words. The app has no speech-to-text; Wispr Flow does that on the device.
- **Railway**: hosting
- **SQLite**: finished cases, in the `wage_cases` table
- **Tailwind CSS**: compiled to a static file, so pages need no CDN
- **Docker**
- Built with **Wispr Flow + Claude Code**

### Optional LLM fallback

The **Hugging Face Inference API** is a documented alternative LLM provider: any OpenAI-compatible chat endpoint can be added to `agent_llm.providers()`. It is **not wired by default**.

## Claims and sources

| Claim | Status | Source |
|---|---|---|
| Unpaid wages are a real, recurring problem. In a survey of 950 rescued bonded labourers, more than half had not been paid. | SOURCED (survey of rescued bonded labourers, not all daily-wage workers) | NCCEBL survey, reported by [The Quint](https://www.thequint.com/jobs/migrant-bonded-labour-abolition-rescued-workers-dalit-adivasi-obc-rehabilitation-survey-data-latest-news) |
| Much of India's services workforce is informal, with limited social security. | SOURCED | NITI Aayog, [*India's Services Sector: Insights from Employment Trends* (2025)](https://www.niti.gov.in/node/2028) |
| A government route exists for unpaid-wage claims (Payment of Wages Act, Minimum Wages Act). | SOURCED | [SAMADHAN portal](https://samadhan.labour.gov.in) |
| Wispr Flow supports Hindi and Hinglish, including romanised Hindi output. | SOURCED | [wisprflow.ai/india](https://wisprflow.ai/india), [Wispr Flow blog](https://wisprflow.ai/post/supporting-languages) |
| Existing wage apps are built for the employer or contractor, not the worker. PagarBook lists 10M+ downloads. | SOURCED (app listings) | [PagarBook](https://pagarbook.com/), [AppBrain listing](https://appgoblin.info/apps/com.gyantech.pagarbook) |
| How many workers are short-paid each week, and by how much | UNVERIFIED | No reliable national figure found |
| Speaking is faster than typing for this user | UNVERIFIED | Not measured |

## Honest limits

- **It calculates; it does not enforce.** The message is sent by the worker, if they choose to.
- **Simple cases only:** one daily rate. Overtime, half days and deductions are not handled yet.
- **No accounts.** Conversations in progress live in server memory (one gunicorn worker); finished cases go to SQLite.
- **Not yet tested with real workers.** Real dictation will bring new phrasings. The LLM handles more of them than the built-in rules, and the read-back catches what either gets wrong.
- **With keys, each conversation costs a little:** a few LLM calls and short Sarvam clips.

## Files

| Path | What it is |
|---|---|
| `app.py` | Flask: `GET /`, `POST /turn`, `GET /health` |
| `conversation.py` | The state machine, the built-in Hinglish reader, and the LLM turn (`step_llm`) |
| `agent_llm.py`, `prompts/agent.txt` | The optional LLM layer: hears facts, writes the reply |
| `PIPELINE.md` | Exactly where each line's text and voice come from, in each mode |
| `wage_math.py` | All arithmetic, as pure functions |
| `hinglish_numbers.py` | Number words, both ways (4200 ⇄ "chaar hazaar do sau") |
| `sarvam_tts.py` | Sarvam voice |
| `database.py` | SQLite `wage_cases`: `save_case()`, `get_case()` |
| `templates/index.html`, `static/app.js` | The one screen |
| `WISPR_FLOW_SETUP.md` | Mac and iPhone setup |
| `PITCH_DECK.md`, `DEMO_SCRIPT.md` | Pitch and demo |

The earlier Proofline project is kept on the `proofline-archive` branch.
