# Demo script (90 seconds)

**Bold** = the worker speaks it with Wispr Flow (double-tap Fn on Mac). *Italic* = what to do on screen.

## Before you record

- [ ] Wispr Flow installed, signed in, languages set to Hindi + English, and the double-tap Fn shortcut tested.
- [ ] Mac volume up, so the agent's voice is heard in the recording.
- [ ] Screen recording on (QuickTime → New Screen Recording, with sound).
- [ ] App open at the start screen: a fresh tab, nothing typed.
- [ ] Backup: https://pagarsaathi.up.railway.app/?mode=scripted open in a second tab. It plays the whole demo by itself.
- [ ] `curl -s https://pagarsaathi.up.railway.app/health` shows `"llm": true, "voice": true` (keys set in Railway Variables). Otherwise the agent runs on rules and recorded clips; the demo still works.
- [ ] WhatsApp Web or the WhatsApp app signed in, so Send opens a real chat.

## Script

| Time | Who | What |
|---|---|---|
| 0s | Worker | *Open the app, press Shuru karein. The agent says hello.* Double-tap Fn: **"Mujhe thekedar ne is hafte poore paise nahi diye."** *The text appears in the box.* Continue. |
| 10s | Agent | "Aapne kitne din kaam kiya?" |
| | Worker | Double-tap Fn: **"Chhe din."** Continue. *The Din chip shows 6.* |
| 20s | Agent | "Roz ki mazdoori kitni tay hui thi?" |
| | Worker | **"Saat sau rupaye."** Continue. |
| 30s | Agent | "Koi advance mila tha pehle?" |
| | Worker | **"Paanch sau."** Continue. |
| 40s | Agent | "Ab tak kitne paise mile?" |
| | Worker | **"Teen hazaar."** Continue. |
| 50s | Agent | "Confirm karta hoon: chhe din, saat sau roz, paanch sau advance, teen hazaar paid. Sahi hai?" |
| | Worker | **"Haan."** Continue. |
| 60s | Agent | "Kul kamaai chaar hazaar do sau. Mila teen hazaar paanch sau. Baaki saat sau rupaye. Thekedar ko payment request bhejun?" *The calculation card shows **₹700 outstanding**.* |
| | Worker | **"Haan."** Continue. |
| 70s | Screen | *The message preview appears: the full Hinglish payment request.* |
| 80s | Worker | *Tap the green **Send to contractor**. WhatsApp opens with the message filled in.* |
| 85s | Screen | *Point at a grey badge under any agent line: "Text: LLM · Voice: Sarvam". Every line shows where it came from.* |
| 90s | Close | "PagarSaathi. Bolo, hisaab pao. Built with Wispr Flow and Claude Code." End card: **pagarsaathi.up.railway.app** |

With keys set, the agent's short replies are written live by the LLM, so the exact words vary from take to take; the questions, the read-back and the numbers do not. Try one off-script line in the live demo, such as **"Bhai, kya karun, thekedar sunta nahi"**, to show that it answers what you said.

## If something goes wrong

- **Wispr Flow text lands somewhere else:** click the answer box first, then double-tap Fn.
- **The agent asks again in simpler words:** it didn't understand. Say just the number ("700").
- **Wrong number at the read-back:** say **"Nahi"**. The agent starts the four questions again.
- **No agent voice:** check that the Mac isn't muted. The text is always on screen.
- **Anything else: switch to `?mode=scripted`** in the second tab and record that. It needs no keys and no outside network.
