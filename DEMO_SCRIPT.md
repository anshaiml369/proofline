# Proofline demo video script

**Total: 2 min 50 s.** Read the lines in **bold**; *italic* lines are what to do on screen.

> Note: no earlier demo script was found in past sessions, so this is a new draft written against the current app. Claims match the deck: nothing unverified is said as fact.

---

## Before you record

- [ ] Phone charged above 50%, Do Not Disturb on.
- [ ] Screen recording on: phone (iOS Control Centre → Screen Recording, mic on) and laptop (QuickTime or OBS).
- [ ] Quiet room: no fan, no TV. Do one 5-second test recording and play it back.
- [ ] QR second device ready: a second phone, camera open, on the same Wi-Fi as the laptop.
- [ ] Demo login ready: logged in on the laptop as `demo@example.com` / `demo1234`, dashboard open in a tab.
- [ ] Server running with API keys set. The rider page must not show the "API keys not configured" banner.
- [ ] Fresh order ID in the rider URL, for example `/rider?order_id=ORD-DEMO1&rider_id=R-1042`.
- [ ] Phone brightness up so the QR code scans first time.
- [ ] Rehearse the line you will speak at 0:55 out loud twice.

---

## Segment 1: Problem (0:00 – 0:30)

*Face to camera, or the deck's slide 2 on screen.*

**[0:00]**
**A customer says, "My order never came."**
**The rider says, "I handed it over."**

**[0:08]**
**The platform can't tell who's right.**
**So it refunds the customer,**
**and lets the rider keep working.**

**[0:16]**
**Public reporting suggests that's what happens**
**in a large share of contested disputes.**

**[0:22]**
**Why? Because nothing records**
**what actually happened at the door.**
**Proofline does.**

---

## Segment 2: Rider flow (0:30 – 1:40)

*Phone screen recording, rider page open.*

**[0:30]**
**This is the rider's screen at the door.**
**Four checks at the top: Phone, QR, GPS, Photo.**

*Type the customer's 10-digit number.*

**[0:38]**
**The rider enters the customer's number,**
**and a QR code appears.**

*Second phone scans the QR → taps "Yes, I received this". The QR chip turns green.*

**[0:46]**
**The customer scans it and taps "Yes, I received this."**
**That's the confirmation, tied to this recording.**

*Hold the green button. Speak clearly, about 5 seconds.*

**[0:55]**
**Now the rider holds one button and says one line —**
*(spoken into the app)* **"Gate three, customer not home, gave it to the security guard."**

*Let go. Wait for the evidence card.*

**[1:08]**
**Hindi, English, or both. It just works.**

**[1:14]**
**Here's the evidence card.**
**Where it was handed over, to whom,**
**and what went wrong, in plain words.**

**[1:24]**
**A fixed set of rules scores it out of 100.**
**The AI only writes down what was said.**
**It never decides.**

**[1:32]**
**And it's tamper-evident:**
**the audio is hashed and timestamped on our server,**
**so nobody can edit it later.**

---

## Segment 3: Dashboard (1:40 – 2:30)

*Laptop screen recording, dashboard tab.*

**[1:40]**
**This is what the platform's dispute team sees.**

*Point to the LIVE row at the top.*

**[1:46]**
**The delivery we just recorded is already here,**
**marked LIVE.**
**Confirmed, GPS matched, its score,**
**and a recommendation.**

*Click "View evidence" on the LIVE row.*

**[1:58]**
**One click shows what the rider said,**
**next to what the customer claims.**

**[2:08]**
**Green means the evidence favours the rider.**
**Amber means a person should look.**
**Red means the evidence is weak.**
**The platform still makes the final call.**

*Click History, expand the row, click Download JSON.*

**[2:20]**
**Every record is kept, and can be exported**
**for an audit.**

---

## Segment 4: Close (2:30 – 2:50)

*Face to camera, or the deck's slide 8.*

**[2:30]**
**Proofline turns one spoken line at the door**
**into evidence a platform can act on.**

**[2:38]**
**We're looking for one 3PL or dark-store operator**
**to pilot it with our riders.**

**[2:45]**
**Proofline. Evidence, not memories.**

*Stop recording at 2:50.*

---

## If something goes wrong while recording

- **QR won't scan:** turn brightness up. If it still fails, reload the rider page for a fresh code and restart Segment 2.
- **"Could not save the evidence":** check the laptop's internet and API keys, then use **Record again**.
- **Card shows "Inconclusive" when you expected "Strong":** the spoken line probably mentioned a failed or partial delivery. Re-record with a clear successful handover.
- **Mistake mid-sentence:** keep going, and cut that part in editing. Each segment can be recorded on its own.
