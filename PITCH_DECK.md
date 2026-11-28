# PagarSaathi: pitch deck (8 slides)

Every figure is labelled **[SOURCED]**, **[UNVERIFIED]** or **[TARGET]**. Sources are in the README.

---

## 1. PagarSaathi

**Bolo, hisaab pao.**
A daily-wage worker speaks; PagarSaathi works out what they are still owed and drafts the payment request.

India Runs on Voice · Scaler × Wispr Flow · Nov 2026

---

## 2. Problem

The daily rate is agreed by word of mouth. The contractor pays "something", minus an advance given earlier. **Nothing is written down.**

- The worker can't easily do the sum on the spot, so the gap goes unclaimed.
- Unpaid wages are real. In a survey of 950 rescued bonded labourers, more than half had not been paid. **[SOURCED: NCCEBL]**
- The formal route exists (the SAMADHAN portal takes unpaid-wage claims) **[SOURCED]**, but it starts with forms, not a conversation.

---

## 3. User

**A daily-wage worker** in construction, loading, domestic or farm work:
- speaks Hindi or Hinglish;
- has a phone;
- may not want to type or calculate.

**Second user:** a union or NGO volunteer sitting with that worker.

---

## 4. Solution

One spoken conversation, four questions:
1. Days worked?
2. Daily rate?
3. Advance?
4. Paid so far?

The agent **reads all four back and waits for "haan"**. Then **Python, not the AI,** calculates:

> 6 × ₹700 = ₹4,200 − ₹500 advance − ₹3,000 paid = **₹700 outstanding**

Then: message preview → **Send to contractor** → WhatsApp opens with the request filled in.

---

## 5. Why Wispr Flow

**The voice layer is the product's interface.**
- Wispr Flow is OS-level dictation: double-tap Fn on Mac, the Wispr Flow keyboard on iPhone.
- The worker speaks; the words land in the answer box. PagarSaathi needs **no mic code and no speech-to-text service.**
- An LLM replies to what the worker actually said, and Sarvam speaks it in natural Hindi. **With no keys, the whole flow still works** using built-in rules and a recorded voice.
- Wispr Flow lists Hindi and Hinglish support and writes romanised Hindi **[SOURCED: wisprflow.ai]**. The app reads digits, Roman and Devanagari.
- Voice fits this user: spoken numbers instead of typed ones. A speed gain for this user is **[UNVERIFIED]**: not yet measured.

---

## 6. Competitors and our wedge

| Product | Who it serves |
|---|---|
| PagarBook (10M+ downloads **[SOURCED: app listing]**), HajariBook, WorkPe, Haajri | **The contractor or employer**: attendance, payroll, advances |
| SAMADHAN (Ministry of Labour) | **Formal claims**: registration and forms |

**Wedge:** none of these is built for the **worker** to speak and get a number. PagarSaathi is worker-side, voice-first, and works from memory, with no records needed. Its output is a clear request that can lead to SAMADHAN if the contractor still doesn't pay.

Note: "Labor Mistri" and "HaazriPro" from an earlier draft could not be found, so they were replaced with the apps above, which could be verified.

---

## 7. Dependencies and risks

| Dependency | Status |
|---|---|
| Wispr Flow (OS-level) | The worker or volunteer installs it. No API key. |
| OpenAI / OpenRouter LLM | Optional. Understands and replies; never calculates. Falls back to built-in rules. |
| Sarvam voice | Optional. Natural Hindi voice; falls back to recorded clips and the browser voice. |

**Biggest objection:** "The contractor will just ignore the message."
**Answer:** PagarSaathi doesn't promise payment. It gives the worker an exact, read-back figure and a written request. That's the first step of any claim, including SAMADHAN.

**Other risks:**
- Real dictation brings phrasings the reader hasn't seen. Answers are re-asked, and the read-back catches mistakes.
- Simple daily-rate cases only, for now.

---

## 8. Go-to-market and ask

- **Free for workers.** Always.
- **Pilot through unions and NGOs** that already help workers with wage disputes. A volunteer runs the conversation with the worker. **[TARGET: one pilot partner]**
- **Next:** half days and overtime, a printable summary for a SAMADHAN claim, and more Indian languages.

**Ask:** introductions to one workers' union or NGO for a 4-week pilot. **[TARGET]**
