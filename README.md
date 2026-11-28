# PagarSaathi

**Bolo, hisaab pao.** A daily-wage worker tells PagarSaathi what happened, by voice through Wispr Flow. A Hinglish agent collects four numbers, reads them back, and Python works out exactly how much is still owed. The case is sealed with a sha256 hash. The worker then chooses: send a payment request on WhatsApp, draft a complaint for the labour office, or just save the case. A day after sending, the agent asks what the contractor said.

What PagarSaathi does not claim is in [`LIMITATIONS.md`](LIMITATIONS.md).

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
→ agent reads all four back: "Sahi hai? Overtime ya katauti thi to woh bhi bataiye." → "Haan"
→ Python calculates and seals the case (sha256) → agent reads every line, then:
  "Message bhejun, escalate karun, ya sirf case save karun?"
     message  → preview → green "WhatsApp par bhejein" → card shows "Bheja gaya: <time>"
     escalate → a Hinglish complaint draft with the hash, for SAMADHAN or the labour office
     save     → the case stays on the card with its hash
→ 24 h after sending: "Pichhle case ke baare mein: thekedar ya manager ne kya kaha?"
```

- **Python does all the arithmetic** in [`wage_math.py`](wage_math.py):
  - `expected = days × rate + overtime_hours × overtime_rate − deductions` (overtime and deductions are optional, and only if the worker mentions them at the read-back)
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
| Deciding what to say next | An LLM dialogue policy (OpenAI `gpt-4.1-mini`, or OpenRouter) reads the whole conversation and chooses each move: ask, follow up, clarify, respond to what the worker volunteered (hospital, a loan, "3 saal"), answer an off-topic question, rephrase | Built-in Hinglish rules: digits, Roman, Devanagari, "nahi mila", plus answers for hospital, loan, years, "ek hafta" |
| Maths | `wage_math.py` (Python) | Same |
| Voice out | Sarvam Bulbul, a natural Hindi voice | Pre-recorded Sarvam clips for fixed lines, then the browser's own voice |

**Every line shows its source.** A small grey badge under each agent line reads, for example, `Text: LLM · Voice: Sarvam` or `Text: Rules · Voice: Recorded`. Worker lines read `Wispr Flow / typed`. The full pipeline, with the exact model and voice names, is in [`PIPELINE.md`](PIPELINE.md).

**The LLM decides the conversation, never the money.** Each turn it returns an action, the line to say, the numbers it heard and any new context, as JSON. Python stores a number only if the worker actually said it, adds multiple amounts, blocks any line that states an amount the worker did not say, never lets the same line repeat, moves on after one ask and two rephrases of a number, stops at 12 turns, and always runs the "Sahi hai?" read-back before the maths. If the LLM fails or takes over 8 seconds, that turn uses the built-in rules. The full contract and guards are in [`PIPELINE.md`](PIPELINE.md#the-dialogue-policy-llm-path).

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

## How the agent decides what to ask

**Measured improvement** ([EVALUATION.md](EVALUATION.md), 32 held-out cases): slot accuracy **86.7% → 100.0%**, math correctness **75.0% → 100.0%**, context acknowledgement **0% → 83.3%** (v2 → v3, the same run). The first held-out v3 run, before one round of fixes, scored 97.7% slots and 90.6% math; repetition stayed at 0.0%. Architecture choice: [ARCHITECTURE.md](ARCHITECTURE.md).

There is no fixed question order. Each turn the LLM gets the **frame** (the four numbers, `context_notes`, `unresolved`, `last_question`, `turn_count`) and the whole conversation, and returns:

```json
{"action": "ask_slot | follow_up | clarify | acknowledge_context | handle_off_topic | rephrase | conclude",
 "target_slot": "days | rate | advance | payments | none",
 "agent_text": "...", "agent_text_hi": "...",
 "extracted": [{"slot": "rate", "value": 650, "confidence": "high"}],
 "context_delta": "4 days in hospital", "intent": "yes | no | other"}
```

| Action | Worker said | Agent replied |
|---|---|---|
| `ask_slot` | "roz ke 650 bole the" | "Rozana 650 rupaye the, samajh gaya. Kya aapko kaam ke dauran ya pehle koi advance mila tha?" |
| `follow_up` | "pichhle mahine ka baaki hai" | "Samajh gaya, pichhle mahine ka paisa baaki hai. Us mahine mein kitne din kaam kiya tha?" |
| `clarify` | "manager se 2000 ka loan liya tha" | "Samajh gaya. Kya woh 2000 rupaye aapki mazdoori mein se kaate gaye hain?" |
| `acknowledge_context` | "maine wahan 3 saal kaam kiya" | "Teen saal ka saath hai. Jis time ka paisa baaki hai, jaise pichhla hafta ya mahina, usme kitne din kaam kiya?" |
| `handle_off_topic` | "aap kaun ho waise?" | "Main PagarSaathi hoon, aapki madad ke liye. Ab bataye, aapko ab tak kitna payment mila hai?" |
| `rephrase` | "samjha nahi" | "Main aapki madad karna chahta hoon. Aapne kitne din kaam kiya tha? Sirf din ka number batayein, jaise 6 din." |
| `conclude` | "teen hazaar" (the last number) | "Aapko ab tak 3000 rupaye aur mile hain." + Python's read-back: "Confirm karta hoon: chhe din, saat sau roz, paanch sau advance, teen hazaar paid. Sahi hai?" |

These are real replies from live and evaluation runs, so the exact words vary from run to run.

**What Python enforces** (`conversation.step_policy`):
- A number is stored only if the worker said it, and Python adds multiple amounts.
- A line is blocked if it states an amount the worker didn't say.
- The same line, or the same question with nothing new, never comes twice in a row.
- Each number gets 1 ask and 2 rephrases, then Python moves on and marks it `unresolved`. Advance and payments are then assumed ₹0 and flagged.
- After 12 turns the agent stops and points to a union or India Labourline (1800 1800 999).
- The read-back always comes before the maths.

Each `/turn` reply carries `action` and `policy_source` (`llm` or `fallback`).

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

## The audit layer

A finished case is a record that a union volunteer or a labour officer can check.

- **Sealed at the result.** When Python calculates, the case becomes one canonical JSON record: the slots, expected, received, outstanding, the full transcript with a timestamp on every turn, the language, `created_at`, `policy_source` (LLM or fallback) and `node_path` (the states the conversation went through). Its **sha256** is stored with it in `wage_cases` (`case_json`, `case_hash`) and is never overwritten.
- **The card shows the first 12 characters** of the hash. The caption is honest: a hash does not stop anyone editing the database, but any edit makes the hash stop matching, so the change can be detected. `GET /state` recomputes it (`hash_verified`).
- **Three choices, by voice:** "Message bhejun, escalate karun, ya sirf case save karun?" Python reads the choice words ("bhejo", "escalate", "sirf save") before the LLM.
- **Sent.** Tapping the WhatsApp button calls `POST /mark-sent`, which stores `sent_at`. The card shows "Bheja gaya: <time>".
- **Follow-up.** The browser keeps the last case id (localStorage). If that case was sent more than 24 hours ago (`FOLLOWUP_AFTER_H`), the next visit opens with "Pichhle case ke baare mein: thekedar ya manager ne kya kaha?". The reply goes into `followup_log`. "Kal dega", "parson", "agle hafte" set `commitment_date`, and the card shows a reminder chip.
- **Escalate.** A Hinglish complaint draft with the days, rate, amounts, the send date, follow-ups and the full hash, addressed to the Labour Commissioner / SAMADHAN portal. It is text to copy. **Nothing is submitted for the worker; there is no complaint API.**
- **Share with a union or legal aid.** `GET /case/<id>/share` is one printable page (Print → PDF) with the case, the hash, the calculation, the transcript, follow-ups and the draft, plus a copy button.

## Privacy

- **Local SQLite only.** Finished cases are in one SQLite file on the server (`pagarsaathi.db`). There are no accounts, no analytics, no tracking scripts and no third-party logging of cases.
- **Outside calls, only with keys:** the worker's text goes to the LLM provider (OpenAI or OpenRouter) to decide the next line, and the agent's line goes to Sarvam to be spoken. The scripted demo makes no outside call.
- **The worker can delete the case.** Say "mera case delete karo" (or tap "Case delete"). The agent asks "Pakka case delete karun? Yeh wapas nahi aayega." and deletes only after a spoken "haan". The row is removed from SQLite (a hard `DELETE`, not a flag).
- On Railway the SQLite file lives on the service's disk. A redeploy without a volume starts a new file.

## Languages

The first message decides the language (`language.py`, from the script and a few common words); when unsure it stays Hindi. The worker can also pick one with the toggle at the top right, which switches the voice and the page's labels.

| Language | Status | Agent lines | Voice (Sarvam Bulbul v4 flash) |
|---|---|---|---|
| Hindi / Hinglish | Full | All | `shubh_enhi_companion` |
| Marathi | Full | Every fixed line, the read-back and the result are translated; the LLM replies in Marathi | `nilesh_mr_conversation` |
| Bengali, Tamil, Telugu | **Beta** | The LLM replies in the language; the read-back, result and choices stay Hindi in the Hindi voice | `arnab_bn_conversation`, `gokul_ta_narration`, `kavitha_te_conversation` |
| Bhojpuri | **Beta** | The LLM replies in Bhojpuri; fixed lines are Hindi | The Hindi voice: Sarvam has no Bhojpuri voice |
| English mix | **Beta** | The LLM replies in the worker's mix; fixed lines are Hinglish | The Hindi voice |

Each voice was checked by sending its audio of a test line, including "700 rupaye", back through Sarvam Saaras speech-to-text, offline. The Bengali, Tamil, Telugu and Marathi voices came back with the right words and the right amount. The Hindi voice reading Telugu text misheard 700 as 200, which is why each language has its own voice. **The app itself never uses speech-to-text**: the worker's words always come from Wispr Flow.

## Help lines

The result card has tap-to-call links. Only numbers we could source are used:
- **India Labourline 1800 1800 999** (`tel:18001800999`), a helpline for informal workers that helps recover unpaid wages ([The Leaflet](https://theleaflet.in/india-labourline-launched-a-new-national-labour-helpline-to-serve-indias-informal-workers), [The Mooknayak](https://en.themooknayak.com/labourer/india-labour-line-helps-788-laborers-to-claim-outstanding-wages-of-rs-1-crore-34-lakhs)).
- **SAMADHAN portal** (https://samadhan.labour.gov.in), the Ministry of Labour's portal for wage claims.
- **Not used: 1916.** It was suggested as a labour helpline. A web search found no national 1916 labour line; listings tie the number to local services instead, for example a Deccan Herald list of Bengaluru SOS numbers gives 1916 as the water board's (BWSSB) ([Deccan Herald](https://www.deccanherald.com/india/karnataka/bengaluru/no-one-picks-up-sos-numbers-760942.html)).

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
- `?debug=1` (with any mode): shows the `node_path` (the states this conversation went through), the policy source, the language and the full hash under the card, and logs every audio event in the console.
- `/?mode=scripted`: the backup demo. It types each demo answer into the box as Wispr Flow would and presses Continue by itself: the worker mentions three years at the site and an illness (the agent acknowledges it), then gives three facts in one sentence, and it ends at ₹700. It always uses the built-in rules and pre-recorded voice, so it calls no outside service and runs the same every time.

## API

`POST /turn` with JSON `{session_id, text}` returns `{agent_text, speak_text, state, done, case_data, facts, context_notes, action, policy_source, node_path, language, voice_lang, case_hash, case_hash_short, sent_at, choice, conflict, prior_case}`.
- Leave out `session_id` to start a conversation; the agent speaks first. Add `prior_session` to get the follow-up question when that case was sent more than 24 hours ago, and `language` to fix the language.
- `POST /mark-sent {session_id}`: the worker tapped Send; stores `sent_at` (`{session_id, event: "sent"}` on `/turn` still works).
- `GET /state?session_id=`: live state, `node_path`, the transcript, and the sealed case with `hash_verified`.
- `POST /escalate {session_id}`: the complaint draft. `GET /case/<session_id>/share`: the one-page share sheet.
- States: `START → ASK_DAYS → ASK_RATE → ASK_ADVANCE → ASK_PAYMENTS → CONFIRM [→ ASK_EXTRAS → CONFIRM] → CALCULATE → READ_RESULT → ASK_SEND → SHOW_PREVIEW → DONE`, plus `FOLLOWUP` and `CONFIRM_DELETE`.

## Tests

```bash
pip3 install -r requirements-dev.txt
```

```bash
python3 -m pytest
```

There are 111 tests. They need no network or keys (the LLM is faked). They cover:
- the three required wage cases: (6, 700, 500, 3000) → 700; (5, 800, 0, 4000) → 0; (10, 500, 200, 3000) → 1800;
- the demo conversation and Wispr-style text (digits, ₹, Devanagari);
- the mandatory confirm step;
- re-ask, then *needs assistance*;
- multiple payments added in Python;
- "pata nahi" not being read as ₹0;
- the nothing-owed path;
- the LLM policy path: hospital, loan and "3 saal" handled as context, off-topic questions, a number the worker never said being refused, a total never spoken, no line repeated, Python stepping in when stuck, several facts in one sentence, corrections at the read-back, Python adding amounts, "haan" never read as ₹0, falling back to rules when the LLM fails;
- the rules path without keys: "3 saal" and "ek hafta" not stored as days, "teen saal" never read as money, hospital and loan acknowledged, no line repeated;
- the v3 guards: two rephrases then move on, the 12-turn cap with the help line, no repeated question, the backstop for tagged numbers, the acknowledgement kept before the read-back, the scripted demo ending at ₹700;
- "so far" not being read as "sau";
- several amounts in one answer without keys ("6 din, 700 roz" is 6 days and ₹700, not 706);
- Hinglish error pages, and the `/health` fields;
- the audit layer: the hash is stored, verifies, and is never overwritten, and an edited record fails; `/mark-sent` and `/state`; the follow-up after a simulated 25 hours (and none after 2), with "kal dega" setting tomorrow's date; the escalation draft and share page carrying the hash; delete only after a spoken yes, and the row really gone;
- the three choices; a contradiction ("6 din", later "5 din") asked about with both values kept, and an explicit "nahi nahi, 5 din" taken without a question;
- language detection for all seven codes, Marathi switching the voice and the lines, Marathi number words ("सहा", "सातशे"), Hindi staying Hindi, the toggle;
- overtime and deductions: the maths, the read-back again, and the four-number path unchanged.

## Built with

- **Flask** (Python 3.11) and **gunicorn**
- **Wispr Flow**: the voice layer (OS-level dictation)
- **Browser SpeechSynthesis**: the agent's voice
- **OpenAI `gpt-4.1-mini`**, with **OpenRouter** as backup: the optional conversational layer; it never calculates
- **Sarvam Bulbul `bulbul:v4-flash`**: the agent's voice, one speaker per language (live, and the 7 recorded clips of the scripted demo)
- **Sarvam Saaras v3**: used offline only, to check that every recorded clip and every language's voice says the right words. The app has no speech-to-text; Wispr Flow does that on the device.
- **Railway**: hosting
- **SQLite**: finished cases, in the `wage_cases` table, with the sealed JSON and its sha256
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
| India Labourline (1800 1800 999) is a helpline for informal workers that helps recover unpaid wages. The agent names it after 12 turns. | SOURCED (one web search; check before a pilot) | [The Leaflet](https://theleaflet.in/india-labourline-launched-a-new-national-labour-helpline-to-serve-indias-informal-workers), [The Mooknayak](https://en.themooknayak.com/labourer/india-labour-line-helps-788-laborers-to-claim-outstanding-wages-of-rs-1-crore-34-lakhs) |
| How many workers are short-paid each week, and by how much | UNVERIFIED | No reliable national figure found |
| Speaking is faster than typing for this user | UNVERIFIED | Not measured |

## Honest limits

- **It calculates; it does not enforce.** The message is sent by the worker, if they choose to.
- **Simple cases only:** one daily rate. Overtime and deductions are optional extras at the read-back; half days and a bonus are not handled.
- **No accounts.** Conversations in progress live in server memory (one gunicorn worker); finished cases go to SQLite. The follow-up depends on the same browser keeping the case id.
- More in [`LIMITATIONS.md`](LIMITATIONS.md).
- **Not yet tested with real workers.** Real dictation will bring new phrasings. The LLM handles more of them than the built-in rules, and the read-back catches what either gets wrong.
- **With keys, each conversation costs a little:** a few LLM calls and short Sarvam clips.

## Files

| Path | What it is |
|---|---|
| `app.py` | Flask: `GET /`, `POST /turn`, `POST /mark-sent`, `POST /escalate`, `GET /state`, `GET /case/<id>/share`, `GET /health` |
| `audit.py` | Canonical case JSON, sha256 seal and verify, follow-up dates, escalation draft, share text |
| `language.py`, `i18n.py` | Language detection; Marathi lines and the beta-language rules |
| `LIMITATIONS.md` | What PagarSaathi does not claim |
| `conversation.py` | The frame and states, the built-in Hinglish reader, and the guarded LLM policy turn (`step_policy`) |
| `agent_llm.py`, `prompts/policy.txt` | The optional LLM dialogue policy: chooses the next move and writes the line |
| `PIPELINE.md` | Exactly where each line's text and voice come from, in each mode |
| `ARCHITECTURE.md` | Why an LLM policy plus a frame, and not a trained RNN or LSTM |
| `evaluate.py`, `test_cases.json`, `TEST_SET.md`, `EVALUATION.md` | The 32-case test set, the harness, and the measured v1 → v2 → v3 results |
| `legacy/` | v1 (tag `v1-original`) and v2 (tag `v2-current`) conversation logic, frozen for the evaluation only |
| `wage_math.py` | All arithmetic, as pure functions |
| `hinglish_numbers.py` | Number words, both ways (4200 ⇄ "chaar hazaar do sau") |
| `sarvam_tts.py` | Sarvam voice |
| `database.py` | SQLite `wage_cases`: `save_case()`, `get_case()`, `mark_sent()`, `add_followup()`, `delete_case()` |
| `templates/index.html`, `static/app.js` | The one screen |
| `WISPR_FLOW_SETUP.md` | Mac and iPhone setup |
| `PITCH_DECK.md`, `DEMO_SCRIPT.md` | Pitch and demo |

The earlier Proofline project is kept on the `proofline-archive` branch.
