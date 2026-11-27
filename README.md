# Proofline

**Voice evidence at the delivery handover.** The rider holds one button and says one line ("Gate 3, customer not home, gave it to the security guard"). Proofline turns it into a structured evidence card, scores it with fixed rules, and gives the platform's dispute team a record it can check later.

Built for the *India Runs on Voice* hackathon. Hindi, English and Hinglish.

## Why

Zomato's CEO has said that in about 50–70% of disputed cases the platform refunds the customer and keeps the rider, because it cannot tell who is right. There is no record of what happened at the door. Proofline captures one at the moment of handover. (Sources in [`pitch_metrics.md`](pitch_metrics.md).)

## What it does

### Rider page (`/rider`)

- **Hold-to-record:** hold the green button, speak for up to 10 seconds, let go. The button shows `Recording… 3s / 10s` while it listens.
- **Customer confirmation by QR:** the rider types the customer's 10-digit number, and the page shows a QR code. The customer scans it and taps "Yes, I received this". The rider page sees the confirmation within 2 seconds.
- **Checklist chips:** Phone · QR · GPS · Photo turn green as each signal is captured.
- **Optional delivery photo:** shrunk on the phone to at most 1280px before upload. It is stored, but it does not change the score.
- **Evidence card:** a recommendation pill, a score out of 100, what the rider said, the extracted fields (handover location, obstacle, customer instruction), and integrity details (server receive time, audio hash, session status).
- **Survives reloads:** the confirmation, phone number and photo are kept per order for the browser session. "Record again" keeps them, and "Reset confirmation" clears them.
- **Works offline:** if there is no connection, the recording is saved on the phone (IndexedDB). It uploads when the connection returns or the page reloads, and retries every 30 seconds. The page shows how many uploads are pending.
- **Speech help:** "Need help? Ask →" opens a bottom sheet. The rider can type or speak a question about what to say, a failed QR scan, or a wrong phone number. Answers are at most 2 sentences, and any other question gets one fixed reply. Nothing is stored.

### Platform pages (login required)

- **Dashboard (`/dashboard`):** summary tiles, plus one row per evidence record with confirmation, GPS, confidence, strength and recommendation. Expand a row to see what the rider said next to the customer's claim. Rows marked LIVE come from the database; the rest are demo data.
- **History (`/history`):** every stored record, newest first. Expand a row for all fields, or download it as JSON.
- **Accounts:** sign up, log in and log out. Passwords are stored as salted hashes, and the `next` redirect is checked so it cannot send users to another site.

### Platform API (`POST /evidence`)

One endpoint for platform integration. It takes the platform's own OTP and GPS signals plus the voice note, and returns the evidence card and the score. See [`api_spec.md`](api_spec.md).

## How the score works

The scoring is plain additive rules, with no model involved:

| Signal | Points |
|---|---|
| Customer confirmed (QR or platform OTP) | +40 |
| GPS matched the drop point | +30 |
| Extraction confidence not low | +20 |
| Handed over at a known place (door, reception, security, neighbour) | +10 |

- **80 or more:** favour rider
- **50–79:** inconclusive
- **Under 50:** favour customer

The rider's own words override the score. If the rider says the delivery failed or was partial, or the customer's complaint is about the contents of the package, the result is never "favour rider". The platform makes the final call.

## Integrity

Each record carries:

- `audio_hash`: SHA-256 of the raw audio as received.
- `received_at`: server time in UTC.
- `recorded_at_client`: the phone's clock. Shown only if it is more than 2 minutes off.
- `hash`: covers the audio plus the sealed fields.

Customer confirmation is tied to the recording:

- The QR code carries a one-time code.
- Confirming creates a recording session.
- Only a page holding the code can read the session ID back.
- A recording with a wrong or expired session is rejected.
- A recording with no session is accepted but marked *not verified*.

This proves the audio was not edited after upload. It does not prove the delivery happened.

## Pipeline

```
voice note ─▶ speech-to-text ─▶ structured extraction ─▶ rule score ─▶ SQLite
              Sarvam saaras:v3     OpenRouter gpt-4o
              (codemix)            fallback: OpenAI gpt-4o-mini
              fallback: Whisper
```

A Wispr Flow STT hook exists, but its endpoint is a placeholder. Leave `WISPR_API_KEY` empty.

## Run with Docker

You need Docker with Compose 2.24 or newer. From the project folder:

```bash
docker compose up
```

Then open http://localhost:5050. Port 5050 is used on the host because macOS uses port 5000 for AirPlay; inside the container the app runs on 5000.

- **Keys are optional.** If a `.env` file exists, Compose loads it. If it doesn't, the app still starts.
- **Without keys:** the app shows "key not set" messages. The UI and routing work; only STT/extraction calls fail gracefully. The rider page shows an "API keys not configured" banner, and recording, `/evidence` and help return a clear 503 error instead of crashing.
- **No secrets in the image.** `.dockerignore` keeps `.env`, the database, photos and recordings out of it.
- **Data is not kept.** The SQLite database lives inside the container, so records are lost when you run `docker compose down`.

## Run locally

You need Python 3.11.

```bash
pip3 install -r requirements.txt
```

```bash
cp .env.example .env
```

Fill in `.env`:

| Variable | Needed for |
|---|---|
| `SARVAM_API_KEY` | Hindi/English speech-to-text and the help mic. Without it, Whisper is used. |
| `OPENROUTER_API_KEY` | Extraction and help answers. |
| `OPENAI_API_KEY` | Fallback for extraction and speech-to-text. |
| `FLASK_SECRET_KEY` | Signs login sessions. Use a long random string; without it, logins reset on every restart. |
| `DATABASE_PATH` | Optional. Defaults to `evidence.db` next to `app.py`. |

```bash
python3 app.py
```

Open:

- Rider page: http://127.0.0.1:5050/rider?order_id=ORD123&rider_id=RID456
- Dashboard: http://127.0.0.1:5050/dashboard. On first start the app creates the demo login `demo@example.com` / `demo1234`.

To try the QR flow on one laptop, open the QR link (click the code) in a second tab.

For production, use the `Procfile` (gunicorn).

## Demo limits (honest list)

- **QR confirmation is simulated.** In the demo, the customer page opens on the same server. In production the customer scans with their own phone, or the platform's existing OTP is used through `/evidence`.
- **Demo data:** dashboard rows not marked LIVE are mock data for illustration.
- **Public demo login:** `demo@example.com` / `demo1234` is public. Remove it before any real deployment.
- **Endpoints that spend API credits:** `/process`, `/evidence` and `/help` need no login and call paid APIs. `/help` and `/help/stt` share a limit of 10 requests a minute per IP; the others have no limit, so set spend limits on your API keys.
- **Database:** SQLite on local disk. A hosted deploy needs a persistent volume and `DATABASE_PATH`.

## Files

| Path | What it is |
|---|---|
| `app.py` | Flask routes, speech-to-text, extraction, help |
| `dispute_engine.py` | Rule-based scoring |
| `db.py` | SQLite: users, deliveries, confirmations, one-time QR codes |
| `prompts/` | Extraction and help prompts |
| `templates/` | Rider, confirm, dashboard, history, login and signup pages |
| `api_spec.md` | `POST /evidence` contract |
| `pitch_metrics.md` | Market claims with source labels |
