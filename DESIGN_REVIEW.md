# Design review: before recording

About 10 minutes. Go through each item on a real phone and a laptop, tick it, and note anything to fix. Nothing in the UI has been changed for this sheet.

Each item has a **Current build** note from the code, so you know what to expect before you look.

## Rider page (`/rider`, check on your phone)

- [ ] **Rider page: record button is the largest element on screen. Check on phone.**
  Current build: the button is full width and 140px tall, bigger than anything else on the page.

- [ ] **Rider page: phone input, OTP input, photo button all fit above the fold on a 6-inch screen.**
  Current build: there is **no OTP input**, because customer confirmation is the QR scan. On a 375×812 screen, the phone input, record button and photo button all fit before the number is entered. After the number is entered, the 220px QR card appears and pushes the record button and photo button below the fold until the customer confirms.

- [ ] **Rider page: offline banner is visible and in Hinglish, not English.**
  Current build: the banner shows, but it is in **English**: "Saved offline — will upload when connection returns."

- [ ] **Rider page: "Keep this screen open" iOS banner is visible on iPhone.**
  Current build: **this banner does not exist yet.**

## Dashboard (`/dashboard`, check on a laptop)

- [ ] **Dashboard: metric tiles readable from 3 feet on a laptop.**
  Current build: 48px numbers with 13px uppercase labels on a dark background.

- [ ] **Dashboard: color coding (green/amber/red) is obvious at a glance.**
  Current build: the colour is in the Recommendation pill and the small strength bar. Since Phase F, rows are no longer tinted.

- [ ] **Dashboard: clicking a row expands to show spoken context.**
  Current build: click the **View evidence** button, not the row itself. It opens "Rider said" next to "Customer says".

## Login (`/login`)

- [ ] **Login page: one input per row, large button.**
  Current build: Email and Password are stacked, with a 52px full-width button.

## History (`/history`)

- [ ] **History page: table rows expand, download JSON works.**
  Current build: clicking a row, or pressing Enter on it, expands it. **Download JSON** saves one file per record.

## All pages

- [ ] **All pages: no horizontal scroll on mobile.**
  Current build: checked in Phase F at 375px for the rider, dashboard and history pages.

## Your notes

| Page | What to fix | Priority (before / after recording) |
|---|---|---|
| | | |
| | | |
| | | |

Tell me what to fix after you review. I will not change the UI until you do.
