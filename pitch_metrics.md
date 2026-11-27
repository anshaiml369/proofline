# Proofline — B2B pitch metrics

Status labels: **[SOURCED]** has a public source below. **[UNVERIFIED]** must not be said on stage until a source is found. **[TARGET]** is a goal, not a result.

## The problem (what Zomato's own CEO has said)

- **[SOURCED]** In roughly **50–70% of disputed cases, Zomato refunds the customer and lets the delivery partner keep working.** The platform pays because it cannot tell who is right. (Deepinder Goyal on Raj Shamani's podcast, reported by Outlook Business and others.)
  - Say it this way. Do **not** say "50–70% of disputes are inconclusive". That is our interpretation, not his words.
- **[SOURCED]** Zomato removes **about 5,000 delivery partners a month** for repeated fraud, for example marking orders delivered without handing them over. (Same podcast, widely reported.)
  - Goyal also said: "We don't remove people for a single mistake." Detecting fraud reliably is the hard part, and that's our opening.
- **[UNVERIFIED]** "35% of disputed refunds are invalid or erroneous." No public source found. Drop it, or find the original before the pitch.

**One-line problem:** Every "not delivered" claim forces the platform to choose between refunding a possible fraudster and punishing a possibly honest rider, usually with no evidence from the doorstep.

## The product

- Voice evidence captured at the **OTP-confirmed handover moment**: the rider speaks one line.
- **Sarvam AI codemix STT** (`saaras:v3`) keeps Hinglish as spoken: English words in English, Hindi words in Devanagari.
- The LLM only **extracts** an evidence card (status, handover location, obstacle, instruction, context, confidence).
- **Fixed rules score** the evidence 0–100 and recommend *favour rider / favour customer / inconclusive*. The platform makes the final call.
- **Tamper-evident record:** a SHA-256 hash over the audio plus server timestamp, GPS, order ID, rider ID, OTP status and GPS-match flag. It proves the record was not edited afterwards, not that the delivery happened.
- **API-first:** the platform sends order_id, rider_id, otp_confirmed, gps_matched and the audio, and gets back the evidence card plus the score.

## Competitors and the wedge (never say "no competitors")

| Competitor | What it does | Why it is not the same thing |
|---|---|---|
| **Platform OTP + photo** (Zomato, Swiggy, Blinkit) | Confirms a code was entered; some orders require a photo | Records *that* a handover happened, not *how*. No spoken context for edge cases (watchman, reception, locked gate). |
| **Route4Me driver app** | Fleet route planning; supports voice recording as proof task on done *and* failed stops | Built for company fleets, not gig platforms. Raw audio only: no Indic codemix transcription, no structured fields, no dispute score. |
| **Onfleet, Locus and similar PoD tools** | Photo, signature and notes proof of delivery | Typed or photo proof, English-first, no dispute scoring. |
| **ERRA, RouteProof** | **[UNVERIFIED]**: named in our research notes, no public product pages found | Confirm they exist and what they do before naming them on stage. |

**Wedge:** We turn a spoken Hinglish line at the OTP handover into a structured, rule-scored, tamper-evident evidence record that a platform's dispute team can act on. Others store a photo or a raw clip.

## Integration path

1. **Direct API to platforms.** Highest value, long sales cycle.
2. **Through logistics middleware.** UrbanPiper, Shadowfax and Dispatch Network already sit between platforms and riders, so a pilot is faster. **[UNVERIFIED]** Check which of these integrate with which platforms before claiming it.

## The ask (hackathon framing)

- **Pilot:** one dark-store cluster, **500 deliveries**.
- **Measure:** share of disputes the evidence resolves (favour rider or favour customer) versus the baseline where the platform refunds by default.
- **[TARGET]** The dashboard's "12%, down from 68%" is an illustrative goal. Say "target" whenever you show it.

## Honest limits (have these ready for Q&A)

- A voice note proves what the rider **said** at that moment, not what happened.
- "Wrong item" claims stay *inconclusive*: a handover recording can't show what was inside the package.
- The scoring rules are hand-set and need tuning on real dispute outcomes during the pilot.

## Sources

- [Outlook Business — Inside Zomato's Karma Score: what Deepinder Goyal reveals about fraud, refunds](https://www.outlookbusiness.com/news/inside-zomatos-karma-score-what-deepinder-goyal-reveals-about-fraud-refunds)
- [StartupTalky — Zomato terminates about 5,000 delivery partners a month](https://startuptalky.com/news/zomato-terminates-about-5-000-delivery-partners-a-month/)
- [NewsX — Zomato terminates nearly 5,000 gig workers a month](https://www.newsx.com/business/zomato-terminates-nearly-5000-gig-workers-a-month-deepinder-goyal-rejects-exploitation-amid-10-minute-delivery-row-on-a-podcast-140304/)
- [Madhyamam — Zomato sacks 5,000 delivery partners monthly over food theft and fraud](https://madhyamamonline.com/business/zomato-sacks-5000-delivery-partners-monthly-over-food-theft-and-fraud-1483291)
- [Route4Me — Proof of delivery and visit driver tasks (voice recording)](https://support.route4me.com/workflows/)
- [Onfleet — Proof of delivery apps for couriers](https://onfleet.com/blog/proof-of-delivery-apps-couriers/)
