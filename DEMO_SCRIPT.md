# Demo script (90 seconds)

**Bold** = the worker speaks it with Wispr Flow (double-tap Fn on Mac). *Italic* = what to do on screen.

The arc: a worker who was ill last week → three facts in one breath → the read-back → ₹700 and a sealed case → three choices → "Bheja gaya".

## Before you record

- [ ] Wispr Flow installed, signed in, languages Hindi + English, double-tap Fn tested. **Its on-screen dictation pill must be visible in the recording** (record the full screen, not just the browser window).
- [ ] Mac volume up, so the agent's voice is in the recording.
- [ ] Screen recording on (QuickTime → New Screen Recording, with sound).
- [ ] App open at https://pagarsaathi.up.railway.app in a fresh private window (no saved case, so no follow-up question; language Hindi).
- [ ] `curl -s https://pagarsaathi.up.railway.app/health` shows `"llm": true, "voice": true`. Without keys the demo still works on rules and recorded clips.
- [ ] WhatsApp Web signed in, so the Send button opens a real chat.
- [ ] Backup tab: https://pagarsaathi.up.railway.app/?mode=scripted (plays the same arc by itself, no keys, no outside calls). Add `&debug=1` to show the `node_path` under the card.

## Script

| Time | Who | What |
|---|---|---|
| 0–5s | Screen | *Wispr Flow's pill is visible at the bottom of the screen. Click **Shuru karein**.* The agent: "Namaste, main PagarSaathi hoon. Bataiye, paise ko lekar kya pareshani hai?" |
| 5–18s | Worker | *Click the answer box, double-tap Fn, speak:* **"Thekedar ne poore paise nahi diye. Teen saal se unke saath hoon, pichhle hafte bimar bhi tha."** *The words appear in the box.* Continue. |
| 18–25s | Agent | Responds to the illness first, then asks the days, e.g. "Yeh sunkar dukh hua… Aapne kitne din kaam kiya?" *The "Aapne bataya" chips show the context it kept.* |
| 25–37s | Worker | **"Chhe din kaam kiya, saat sau roz, paanch sau advance mila tha."** Continue. *Three fact chips fill at once: 6, ₹700, ₹500.* |
| 37–42s | Agent | "Ab tak kitne paise mile?" (the one number still missing) |
| 42–47s | Worker | **"Teen hazaar mile."** Continue. |
| 47–55s | Agent | The read-back: "Confirm karta hoon: chhe din, saat sau roz, paanch sau advance, teen hazaar paid. Sahi hai? Overtime ya katauti thi to woh bhi bataiye." |
| 55–58s | Worker | **"Haan."** Continue. |
| 58–70s | Agent + screen | Python calculates. The card shows **Baaki ₹700** in large type, every line with an icon, and **Case ID: <12 characters>** with its caption. The agent reads each line, then: "Ab kya karun: message bhejun, escalate karun, ya sirf case save karun?" *Point at the Case ID.* |
| 70–75s | Worker | **"Message bhej do."** Continue. *The message preview appears, then the lavender **WhatsApp par bhejein** button.* |
| 75–83s | Worker | *Tap **WhatsApp par bhejein**.* WhatsApp opens with the message filled in. *Switch back:* the card now says **"Bheja gaya: <time>"**. |
| 83–90s | Close | *Point at the Escalate and "Union / legal aid" buttons.* "PagarSaathi. Bolo, hisaab pao. Built with Wispr Flow and Claude Code." End card: **pagarsaathi.up.railway.app** |

With keys set, the agent's acknowledgement and questions are written live by the LLM, so the exact words vary between takes. The read-back, the result, the choices and every number are Python's and do not vary.

## If something goes wrong

- **Wispr Flow text lands somewhere else:** click the answer box first, then double-tap Fn.
- **The agent asks again in simpler words:** it didn't understand. Say just the number ("700").
- **Wrong number at the read-back:** say **"Nahi, roz 800 tha"**. The agent reads everything back again.
- **The agent asks "Aapne pehle … kaha, ab … : kaunsa sahi hai?":** a number changed. Say which one is right.
- **A follow-up question instead of the greeting:** the browser kept an earlier case. Use a private window.
- **No agent voice:** check the Mac isn't muted. The text is always on screen.
- **Anything else: switch to `?mode=scripted`** in the backup tab and record that.
