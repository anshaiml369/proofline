# PagarSaathi: pitch deck (11 slides)

Every figure is labelled **[SOURCED]**, **[UNVERIFIED]** or **[TARGET]**. Sources are in the README and on each slide. The worked ₹700 case on slide 3 is an example the demo worker says; its numbers are inputs, marked *(example input)*, not claims.
Live app: **https://pagarsaathi.up.railway.app**

---

## 1. PagarSaathi

**Bolo, hisaab pao.**
A daily-wage worker speaks; PagarSaathi works out what they are still owed, seals the case, and helps them send, escalate or keep it.

India Runs on Voice · Scaler × Wispr Flow · https://pagarsaathi.up.railway.app

---

## 2. Problem and user

A daily-wage worker (construction, loading, domestic or farm work) agrees a daily rate by word of mouth. The contractor pays "something", minus an advance given earlier. **Nothing is written down.**

- The worker can't easily do the sum on the spot, so the gap goes unclaimed.
- Unpaid wages are real. In a survey of 950 rescued bonded labourers, more than half had not been paid. **[SOURCED: NCCEBL, via The Quint]**
- The formal route exists (the SAMADHAN portal takes unpaid-wage claims) **[SOURCED]**, but it starts with forms, not a conversation.

**User:** a worker who speaks Hindi or Hinglish, has a phone, and may not want to type or calculate. **Second user:** a union or NGO volunteer sitting with them.

---

## 3. The ₹700 demo

A worker who was ill last week, three facts in one breath, one confirmation:

| Worker says (Wispr Flow) | Agent |
|---|---|
| "Thekedar ne poore paise nahi diye… pichhle hafte bimar bhi tha." | Responds to the illness, then asks the days |
| "Chhe din kaam kiya, saat sau roz, paanch sau advance mila tha." | Hears three facts at once *(example input)* |
| "Teen hazaar mile." | Reads everything back: *"Sahi hai?"* *(example input)* |
| "Haan." | Python calculates |

> 6 × ₹700 = ₹4,200 − ₹500 advance − ₹3,000 paid = **₹700 outstanding** *(example input)*

The case is sealed with a sha256 hash (the card shows its first 12 characters), then: *"Message bhejun, escalate karun, ya sirf case save karun?"* → "Message bhej do" → WhatsApp opens with the request → the card shows **"Bheja gaya: <time>"**.

---

## 4. Why voice is the form

A wage claim is a form: days, rate, advance, paid, signature. This user doesn't fill forms. **The conversation is the form.**

- **Wispr Flow is the voice layer.** OS-level dictation: double-tap Fn on a Mac, the Wispr Flow keyboard on an iPhone. The worker speaks; the words appear in the box on camera. The app has no mic code and no speech-to-text of its own.
- Wispr Flow lists Hindi and Hinglish support and writes romanised Hindi **[SOURCED: wisprflow.ai]**.
- **Every field gets filled the way people talk:** several facts in one sentence, out of order, with a hospital visit or a loan in the middle. The agent answers the person first, then asks for the one number still missing.
- **The read-back is the signature.** Nothing is calculated until the worker hears all four numbers and says "haan".
- **The form talks back** in the worker's language: Hindi and Marathi in full, Bengali, Tamil, Telugu, Bhojpuri in beta, each with its own Sarvam voice checked by speech-to-text.
- Speaking numbers fits this user better than typing them. A speed gain is **[UNVERIFIED]**: not measured.

---

## 5. Competitors and our wedge

| Product | Who it serves |
|---|---|
| PagarBook (10M+ downloads **[SOURCED: app listing]**), HajariBook, WorkPe, Haajri | **The contractor or employer**: attendance, payroll, advances |
| SAMADHAN (Ministry of Labour) | **Formal claims**: registration and forms |

**Wedge:** these tools keep the contractor's records. PagarSaathi is **worker-side reconstruction**: the worker rebuilds the week from memory, by voice, and gets an exact figure and a written request. That request can lead to SAMADHAN if the contractor still doesn't pay.

Note: "Labor Mistri" and "HaazriPro" from an earlier draft could not be found, so they were replaced with apps that could be verified.

---

## 6. Auditable by design

**A case a volunteer or a labour officer can check.**

- **Sealed at the result:** the transcript with timestamps, the numbers, the language, which path decided each turn (LLM or rules) and the states the conversation went through, as one canonical JSON record with a **sha256 hash**. The card shows the first 12 characters.
- **Sent and followed up:** "Bheja gaya: <time>" is stored. A day later the agent asks "Pichhle case ke baare mein: manager ne kya kaha?"; "kal dega" becomes a dated reminder.
- **Escalate:** a Hinglish complaint draft with the full hash, for SAMADHAN or the labour office. **Share:** one printable page for a union or legal-aid volunteer.
- **Every line shows its source:** `Text: LLM · Voice: Sarvam`, `Text: Rules · Voice: Recorded`. The money figure always comes from `wage_math.py`, never from a model.
- **The worker can delete it:** "mera case delete karo", a spoken "haan", and the row is gone.

---

## 7. Dependencies and fallbacks

| Dependency | If it is missing or fails |
|---|---|
| Wispr Flow (on the device) | The worker types instead; the same box works. |
| OpenAI / OpenRouter LLM | That turn uses the built-in rules. They still read "6 din, 700 roz" and still reach ₹700 *(example input)*. |
| Sarvam Bulbul voice | The recorded demo clips play, then the browser's own voice. Nothing goes silent. |
| Network (demo day) | `?mode=scripted` runs the whole demo from the app's own server, with no outside calls. |

**Biggest objection:** "The contractor will just ignore the message."
**Answer:** PagarSaathi doesn't promise payment. It gives the worker an exact, read-back figure and a written request: the first step of any claim, including SAMADHAN.

---

## 8. What we do not claim

- **We do not guarantee payment.** The message is a request; the contractor can ignore it.
- **We file nothing.** The complaint is a draft the worker or a volunteer submits. There is no SAMADHAN API behind the button.
- **The hash shows changes; it does not prevent them.** It is not anchored outside our server.
- **The numbers are the worker's memory**, checked only by the read-back. No attendance data, no legal check of the rate.
- **Small, scripted evaluation:** 32 cases we wrote. First held-out run of the current agent: 97.7% slot accuracy and 90.6% maths correctness **[SOURCED: EVALUATION.md, our own run]**. Not yet tested with real workers.
- **Beta languages** read the result in Hindi.

Full list: [LIMITATIONS.md](LIMITATIONS.md).

---

## 9. Who pays

| Who | Pays | Status |
|---|---|---|
| The worker | **₹0**, always | **[TARGET]**: a product rule, not a measured figure |
| A union or NGO running cases with workers | **about ₹5 per case** | **[TARGET]**: a price we would propose, not agreed with anyone |
| Our cost per case, with keys | **about ₹1–2** | **[UNVERIFIED]**: an estimate, worked out below |

How the cost estimate is made (list prices, not a measured bill):
- **LLM:** about 6 policy turns × about 2,300 input and 150 output tokens each, on `gpt-4.1-mini` at $0.40 per million input and $1.60 per million output tokens **[UNVERIFIED: OpenAI list price, not re-checked for this deck]** ≈ $0.007 ≈ ₹0.6 at about ₹88 per dollar **[UNVERIFIED]**.
- **Voice:** the demo conversation speaks 542 characters **[SOURCED: counted from the app's own lines]**. Sarvam Bulbul v4 flash is ₹1 per 1,000 characters in Sarvam's docs and ₹20 per 10,000 on its product page, so ₹0.5–1.1 **[UNVERIFIED: Sarvam's two pages disagree]**.
- **Not included:** hosting, and a volunteer's time.
- The scripted demo, the rules path and the recorded voice cost nothing per case.

---

## 10. Dependencies at a glance

The core (conversation, maths, read-back, case, hash, WhatsApp link) runs with **no keys**. Keys add the LLM policy and the live voice; each falls back on its own (slide 7).

---

## 11. Go-to-market and ask

- **Free for workers.** Always.
- **Pilot through unions and NGOs** that already help workers with wage disputes. A volunteer runs the conversation with the worker and uses the share page and the complaint draft. **[TARGET: one pilot partner]**
- **Next:** half days and piece rates, full Bengali, Tamil and Telugu read-backs, a timestamp for the hash outside our server.

**Ask:** introductions to one workers' union or NGO for a 4-week pilot. **[TARGET]**

Try it: **https://pagarsaathi.up.railway.app** · backup demo: `/?mode=scripted`
