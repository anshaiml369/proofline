# PagarSaathi design spec

The page should feel like part of the Wispr Flow world (warm cream, ink, lavender, a serif voice) while staying usable for a worker who reads little, under stress, on a 390 px phone. Accessibility rules win over looks every time.

This is a palette and type direction inspired by Wispr Flow's public site. It does not use Wispr Flow's logo, name as our brand, or copy any of its pages.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--canvas` | `#ffffeb` | Page background, card fill, glass fallback |
| `--ink` | `#1a1a1a` | All text, 2 px card borders, the ₹ amount |
| `--lavender` | `#f0d7ff` | Primary button fill (black text) |
| `--lavender-hover` | `#e6c4ff` | Primary button hover |
| `--teal` | `#034f46` | "Safe / confirmed": Escalate outline, confirmed ticks, listening ring, "Bheja gaya" |
| `--ember` | `#ffa946` | **Fills and underlines only**: the underline under the amount owed, error marker bar |
| `--ember-ink` | `#8a4b00` | Ember-coloured **text** (error line): `#ffa946` text on cream is 1.88:1 and fails AA |
| `--muted` | `#555555` | Helper text, never lighter |
| `--line` | `#1a1a1a` at 2 px | Card borders |
| `--glass` | `rgba(255,255,235,0.72)` + `backdrop-filter: blur(12px)` | Only the final-card overlay and the turn-log backdrop; solid `--canvas` when `backdrop-filter` is unsupported |

| Type | Font | Weight | Size / tracking / leading |
|---|---|---|---|
| Agent's spoken line (`h1`) | EB Garamond | 400 | 32 px on 390 px, 40 px at ≥768 px; tracking −0.03em; line-height 1.05 for multi-line Hindi (0.9 clips Devanagari matras, see note) |
| Amount owed (₹700) | EB Garamond | 400 | 72 px (floor 64 px); tracking −0.03em; line-height 0.9 |
| UI labels, buttons | Figtree | 600 | 16–18 px |
| Body, turn log, calculation labels | Figtree | 400 | 16 px minimum |
| Helper text | Figtree | 400 | 14 px minimum, `--muted` or darker |
| Case-hash caption | Figtree | 400 | 14 px (the old 12 px exception is removed) |

Note: line-height 0.9 is kept for the number, which is one line of digits. For the agent's line it is raised to 1.05, because Devanagari and wrapped Hinglish at 0.9 overlap between lines.

| Shape | Value |
|---|---|
| Main card | 40 px radius on 390 px, 64 px at ≥768 px |
| Buttons, inputs, pills | 12 px |
| Chips (facts, context notes, language) | full radius (999 px) |
| Touch targets | 48 px minimum; the "Bolo" button 160 px |

## Components

The app has no microphone: Wispr Flow is the only voice input. The "Bolo" button (2) is a 160 px round button that focuses the answer box, so Wispr Flow's dictation lands there, and it shows what the input is doing. "Listening" means Wispr Flow text is arriving in the box; it does not record audio.

| # | Component | Default | Hover | Active | Disabled | Error |
|---|---|---|---|---|---|---|
| 1 | Agent question block (`h1`) | Garamond line on cream, "PagarSaathi" label above in Figtree 14 px muted | — | Speaking: a small teal "bol raha hai…" tag | — | Replaced by the Hinglish error line, never JSON |
| 2 | Bolo button (160 px) | Lavender circle, ink 2 px border, "Bolo" label + Wispr Flow hint below; soft pulse | Lavender-hover fill | Pressed: scale 0.97 for 120 ms; listening: teal ring + stronger pulse while text arrives; processing: rotating teal ring | Flat, 50% opacity, no pulse | Shakes; "Sun nahi paya, phir se boliye" below in `--ember-ink` with an ember bar |
| 3 | Turn-log bubble | Agent: left, cream with ink border; worker: right, lavender fill; Figtree 16 px | — | Newest bubble fades in | — | A failed turn shows the Hinglish error as an agent bubble |
| 4 | Calculation card (`section` + `dl`) | Cream, 2 px ink border, 40 px radius; four lines (calendar Kaam, wallet Advance, wallet Ab tak mila, check Baaki), each icon + 16 px label + amount; total ₹ in Garamond 72 px with ember underline | — | Springs in once | — | Not shown until Python has calculated |
| 5 | Message preview | Cream, 2 px ink border, 12 px radius, Figtree 16 px, pre-wrapped | — | — | — | — |
| 6 | Send button | Lavender fill, ink text and border, 56 px tall, WhatsApp glyph | Lavender-hover | Scale 0.97 for 120 ms | 50% opacity, `aria-disabled` | Popup blocked: "WhatsApp nahi khula. Neeche message copy karein." + Copy button |
| 7 | Escalate button | Transparent, 2 px teal border, teal text | Teal 8% tint | Scale 0.97 | 50% opacity | Request failed: Hinglish error line under it |
| 8 | Case-hash footer | "Case ID" + 12-char mono hash in ink, 14 px caption in muted; "Bheja gaya: <time>" in teal | — | — | — | Hidden if there is no sealed case |
| 9 | Language toggle | Pill select, top right, 48 px tall, 2 px ink border | Lavender tint | Focus ring 3 px teal | — | — |
| 10 | Keyless banner | Small cream chip, 2 px ink border, full radius, 14 px ink text; sits under the header, never over the Bolo button | — | — | — | — |

## Motion

Motion (motion.dev) from a CDN, vanilla (`Motion.animate`, `Motion.spring`), no React. Every animation goes through one guard: with `prefers-reduced-motion: reduce`, only opacity changes, nothing moves or scales, and numbers appear at their final value.

| Moment | What moves | Duration / easing |
|---|---|---|
| Page load | Main card enters: y 24→0, opacity 0→1 | Spring, stiffness 300, damping 30 |
| Turn advance | Old question opacity 1→0, then new question opacity 0→1 and y 8→0 | 150 ms ease-in, then 200 ms ease-out |
| New turn-log bubble | Opacity 0→1, y 6→0 | 200 ms ease-out |
| Bolo idle | Scale 1→1.03→1, every 3 s | 1.2 s ease-in-out, repeats |
| Bolo listening (text arriving) | Scale 1→1.08→1 + teal ring opacity in | 0.8 s ease-in-out, repeats while typing, stops 1 s after the last keystroke |
| Bolo processing (request in flight) | Teal ring rotates | 1.6 s linear, until the reply arrives |
| Calculation card (state reaches READ_RESULT / ASK_SEND / SHOW_PREVIEW, once) | y 24→0, scale 0.96→1, opacity 0→1 | Spring, stiffness 300, damping 30 (about 400 ms) |
| Amount count-up | ₹0 → ₹700, plays once per case | 600 ms ease-out |
| Send tap | Button scale 1→0.97→1, then preview opacity 1→0.6 | 120 ms, then 200 ms |
| Error | Bolo x 0, −6, 6, −3, 0; error line fades in | 300 ms; 200 ms |

## Accessibility checklist (each item is tested in Phase 5)

- [ ] A1 The amount owed is EB Garamond, ink, at least 64 px, with an ember underline.
- [ ] A2 Every calculation line has an icon and a 16 px text label; no line is icon-only.
- [ ] A3 No body text under 16 px; no helper text under 14 px or lighter than `#555`.
- [ ] A4 Every interactive element is at least 48 × 48 px; the Bolo button is 160 px.
- [ ] A5 Every text/background pair passes WCAG AA (4.5:1 normal text, 3:1 for text 24 px+ or 18.66 px bold).
- [ ] A6 On a 390 × 844 viewport the agent's current question is visible without scrolling, in every state.
- [ ] A7 `prefers-reduced-motion: reduce` leaves only opacity changes.
- [ ] A8 No horizontal scroll at 390 px.
- [ ] A9 Glass is used only on the final-card overlay and the turn-log backdrop, with a solid cream fallback.
- [ ] A10 The turn log is an `ol` with `aria-live="polite"`; the question is the page's `h1`.

Contrast of the token pairs (computed with the WCAG formula):

| Text | Background | Ratio | AA |
|---|---|---|---|
| ink `#1a1a1a` | canvas `#ffffeb` | 17.2 | Pass |
| ink | lavender `#f0d7ff` | 13.15 | Pass |
| ink | lavender-hover `#e6c4ff` | 11.36 | Pass |
| teal `#034f46` | canvas | 9.39 | Pass |
| canvas | teal | 9.39 | Pass |
| muted `#555555` | canvas | 7.37 | Pass |
| ember-ink `#8a4b00` | canvas | 6.72 | Pass |
| ink | ember `#ffa946` | 9.13 | Pass |
| ember `#ffa946` | canvas | 1.88 | **Fail**, so ember is never used for text |

## Constraints carried over from the product

- No microphone and no speech-to-text in the page: Wispr Flow types into the answer box.
- Every number on the card comes from the server (`wage_math.py`); the count-up only animates the server's final value.
- Backend routes, state names and `conversation.py` / `wage_math.py` / `app.py` logic do not change in the redesign. (The brief mentions a LangGraph graph; this app has none, so there is nothing to keep there.)
- Fonts and Motion come from CDNs (Google Fonts, jsDelivr). If they fail to load, the page falls back to system serif/sans fonts and no animation; it still works.
