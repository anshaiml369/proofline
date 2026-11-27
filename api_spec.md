# Proofline API — `POST /evidence`

One endpoint. The platform sends what it already knows plus the rider's voice note, and gets back a structured evidence card and a rule-based dispute score.

## Request

`POST /evidence` · `multipart/form-data`

| Field | Type | Required | Notes |
|---|---|---|---|
| `order_id` | string | yes | Platform order ID. Max 64 chars. |
| `rider_id` | string | yes | Platform rider ID. Max 64 chars. |
| `otp_confirmed` | boolean | yes | `true` / `false` (or `1` / `0`). From the platform, never from the voice note. |
| `gps_matched` | boolean | yes | Whether the rider's location matched the drop point. From the platform. |
| `audio` | file | yes | Rider's spoken note. WAV or MP3 (WebM, OGG, MP4/M4A also accepted). Keep it to ≤ 10 s; hard limits are 10 MB per file and 30 s for speech-to-text. |
| `customer_claim` | string | no | e.g. `not delivered`, `wrong item`. Used only for the recommendation. |
| `gps_lat`, `gps_lng` | string | no | Raw coordinates to seal into the record. Shown as `unavailable` if absent or invalid. |

```bash
curl -X POST https://<host>/evidence \
  -F order_id=ZMT-482913 -F rider_id=R-1042 \
  -F otp_confirmed=true -F gps_matched=true \
  -F customer_claim="not delivered" \
  -F audio=@note.wav
```

## Response `200`

```json
{
  "evidence_card": {
    "order_id": "ZMT-482913",
    "rider_id": "R-1042",
    "otp_confirmed": true,
    "gps_matched": true,
    "delivery_status": "delivered",
    "handover_location": "security",
    "obstacle": "customer_unavailable",
    "customer_instruction": "not_mentioned",
    "spoken_context": "On the third floor, the gate was locked, customer's phone was off, handed it to the watchman, photo taken.",
    "confidence": "high"
  },
  "dispute_score": {
    "evidence_strength": 79,
    "recommendation": "inconclusive",
    "reasoning": "OTP confirmed, but the rider reports the customer was unavailable at handover."
  },
  "customer_claim": "not delivered",
  "record": {
    "timestamp": "2026-11-27T04:41:09Z",
    "gps": "unavailable",
    "hash": "<64 hex chars>",
    "hash_short": "<12 hex chars>",
    "sealed_fields": "2026-11-27T04:41:09Z|unavailable|ZMT-482913|R-1042|True|True",
    "audio_url": "/static/audio/<id>.wav"
  },
  "transcript": "तीसरी फ्लोर पर गेट … photo ले ली।",
  "stt_engine": "sarvam",
  "extraction_engine": "openrouter"
}
```

### Field values

| Field | Values |
|---|---|
| `delivery_status` | `delivered` · `failed` · `partial` · `not_mentioned` |
| `handover_location` | `door` · `reception` · `security` · `neighbor` · `other` · `not_mentioned` |
| `obstacle` | `none` · `gate_locked` · `customer_unavailable` · `address_issue` · `refused` · `other` · `not_mentioned` |
| `confidence` | `high` · `medium` · `low` (how clearly the rider described the handover) |
| `recommendation` | `favor_rider` · `favor_customer` · `inconclusive` |
| `stt_engine` | `wispr` · `sarvam` · `whisper` (whichever produced the transcript) |
| `extraction_engine` | `openrouter` · `openai` |

## Who decides what ("trust but verify")

| Decided by | What |
|---|---|
| **The platform** (request) | `order_id`, `rider_id`, `otp_confirmed`, `gps_matched`, `customer_claim` |
| **The server** (fixed, on receipt) | `timestamp` (UTC), `gps`, `hash` |
| **The AI** (extraction only) | `delivery_status`, `handover_location`, `obstacle`, `customer_instruction`, `spoken_context`, `confidence`. Values outside the lists above are clamped by the server. |
| **Fixed rules** (`dispute_engine.py`) | `evidence_strength` and `recommendation` |
| **The platform** (always) | The final dispute decision |

**Scoring bands:** 80–100 when OTP is confirmed, GPS matched, a known handover location is named, confidence isn't low and the customer was available. 50–79 when OTP is confirmed but something is weaker. 0–49 when there's no OTP or no spoken account. A `wrong item`-type claim is always `inconclusive`, because a handover record can't show what was inside the package.

## Verifying a record

`hash = SHA-256(audio_bytes + sealed_fields)`. To check a record later, recompute the hash from the stored audio file and `sealed_fields`. If one byte of the audio, the timestamp, GPS, IDs or flags changes, the hash no longer matches. It shows the record was not edited after capture. It does **not** show that the delivery happened.

## Errors

Every error is JSON with an `error` field.

| HTTP | `error` | When |
|---|---|---|
| 400 | `invalid_request` + `fields` list | A required field is missing or a boolean isn't `true`/`false` |
| 413 | `Audio file too large (max 10 MB)` | Upload over 10 MB |
| 502 | `parse_failed` + `raw` | The model reply wasn't valid JSON (`record` is still returned) |
| 500 | message | Speech-to-text or extraction both failed (e.g. no keys configured) |

Typical latency: 3–4 s (Sarvam ~0.5 s + extraction ~2–3 s).

## Not in this hackathon build

- **Authentication:** production needs a per-platform API key header. Right now anyone who can reach the URL can call it.
- **Durable audio storage:** files are on local disk and are lost on redeploy. Production needs object storage.
- **Wispr:** the code path is ready, but its endpoint is unverified until a key is issued.
