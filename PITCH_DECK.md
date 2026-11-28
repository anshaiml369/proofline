# PagarSaathi: pitch deck (8 slides)

Every figure is labelled **[SOURCED]**, **[UNVERIFIED]** or **[TARGET]**. Sources are in the README.
Live app: **https://pagarsaathi.up.railway.app**

---

## 1. PagarSaathi

**Bolo, hisaab pao.**
A daily-wage worker speaks; PagarSaathi works out what they are still owed and drafts the payment request.

India Runs on Voice · Scaler × Wispr Flow · Nov 2026 · https://pagarsaathi.up.railway.app

---

## 2. Problem and user

A daily-wage worker (construction, loading, domestic or farm work) agrees a daily rate by word of mouth. The contractor pays "something", minus an advance given earlier. **Nothing is written down.**

- The worker can't easily do the sum on the spot, so the gap goes unclaimed.
- Unpaid wages are real. In a survey of 950 rescued bonded labourers, more than half had not been paid. **[SOURCED: NCCEBL]**
- The formal route exists (the SAMADHAN portal takes unpaid-wage claims) **[SOURCED]**, but it starts with forms, not a conversation.

**User:** a worker who speaks Hindi or Hinglish, has a phone, and may not want to type or calculate. **Second user:** a union or NGO volunteer sitting with them.

---

## 3. The ₹700 demo

One spoken conversation, four facts, one confirmation:

| Worker says (Wispr Flow) | Fact |
|---|---|
| "Chhe din" | 6 days |
| "Saat sau rupaye" | ₹700 a day |
| "Paanch sau" | ₹500 advance |
| "Teen hazaar" | ₹3,000 paid |

The agent reads all four back: *"Sahi hai?"* → **"Haan"**. Then **Python, not the AI,** calculates:

> 6 × ₹700 = ₹4,200 − ₹500 advance − ₹3,000 paid = **₹700 outstanding**

Then: message preview → green **Send to contractor** → WhatsApp opens with the full Hinglish request filled in.

---

## 4. Why voice is the interface

- **Wispr Flow is the voice layer.** It is OS-level dictation: double-tap Fn on a Mac, the Wispr Flow keyboard on an iPhone. The worker speaks, and the words appear in the answer box on camera.
- PagarSaathi needs **no mic code and no speech-to-text service**: it receives text.
- Wispr Flow lists Hindi and Hinglish support and writes romanised Hindi **[SOURCED: wisprflow.ai]**. The app reads digits, Roman and Devanagari.
- The agent talks back: an LLM dialogue policy decides each next move from the whole conversation (it follows up, clarifies, and responds to "main hospital mein tha" or "manager se loan liya"), and Sarvam Bulbul speaks it in natural Hindi.
- Speaking numbers fits this user better than typing them. A speed gain is **[UNVERIFIED]**: not yet measured.

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

**Every agent line shows whether it came from the LLM, the rules, or a recorded clip.**

```
Achha, chhe din aur saat sau roz.  Koi advance mila tha pehle?
Text: LLM · Voice: Sarvam
```

- `Text: LLM`: the LLM policy chose the move and wrote the line. Python still checks every number against what the worker said.
- `Text: Rules`: the built-in rules, which need no key.
- `Voice: Recorded / Sarvam / Browser`: which voice actually spoke.
- The worker's lines say `Wispr Flow / typed`.

A judge, a volunteer or a worker's family can see exactly where each line came from. The money figure always comes from `wage_math.py`, never from a model.

---

## 7. Dependencies and fallbacks

| Dependency | If it is missing or fails |
|---|---|
| Wispr Flow (on the device) | The worker types instead; the same box works. |
| OpenAI / OpenRouter LLM | That turn uses the built-in rules. They still read "6 din, 700 roz" and still reach ₹700. |
| Sarvam Bulbul voice | The 9 recorded clips play, then the browser's own Hindi voice. Nothing goes silent. |
| Network (demo day) | `?mode=scripted` runs the whole demo from the app's own server, with no outside calls. |

**Biggest objection:** "The contractor will just ignore the message."
**Answer:** PagarSaathi doesn't promise payment. It gives the worker an exact, read-back figure and a written request: the first step of any claim, including SAMADHAN.

---

## 8. Go-to-market and ask

- **Free for workers.** Always.
- **Pilot through unions and NGOs** that already help workers with wage disputes. A volunteer runs the conversation with the worker. **[TARGET: one pilot partner]**
- **Next:** half days and overtime, a printable summary for a SAMADHAN claim, more Indian languages.

**Ask:** introductions to one workers' union or NGO for a 4-week pilot. **[TARGET]**

Try it: **https://pagarsaathi.up.railway.app** · backup demo: `/?mode=scripted`
