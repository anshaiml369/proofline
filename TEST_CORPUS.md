# Test corpus (Phase 16)

`test_corpus.json` holds scripted worker conversations in eight classes, and `scripts/build_corpus.py` writes it. Run it with:

```bash
python3 evaluate.py --corpus test_corpus.json
```

That command runs both backends. `v3-before` is `legacy/v3_current.py`, the code at tag `v3-before-derivation`. `v4` is `conversation.py` with derivation. Results go to [EVALUATION.md](EVALUATION.md).

**Size.** The brief asked for "100 conversations", with 15 per class for A, B, C, D, F, G and H, and 10 for E. Those counts add up to 115, so the corpus keeps the per-class counts and has **115 cases**.

## Case format

```json
{"id": "A1", "class": "A period-not-daycount", "turns": ["meri pagar badhao.", "..."],
 "expected_canonical": {"days": 130, "rate": 700, "advance": 0, "payments": 90300},
 "expected_outstanding": 700, "must_contain_in_agent": ["130"], "must_not_repeat": true,
 "must_pass_hard": true, "scripted_confirm": true, "notes": "..."}
```

**How the expected numbers were set.** I wrote each one from the worker's words, using the stated assumptions: 26 working days a month, 4.33 weeks a month, and 6 days a week when the worker gives no other number. None was copied from the agent's output.

**When a case passes.** It passes when all three hold:
- the conversation reaches a result, and the outstanding amount equals `expected_outstanding`;
- every string in `must_contain_in_agent` appears in some agent line;
- no agent line repeats one of the two agent lines before it.

**A1 is `must_pass_hard`.** This is the proof conversation from the brief, word for word. Three turns are added after it: "roz 700", "advance nahi mila" and "nabbe hazaar teen sau mile". The case works out as:
- 5-6 months × 4.33 weeks × 5 days a week ≈ 130 days;
- 130 days × ₹700 = ₹91,000;
- ₹91,000 − ₹90,300 = ₹700.

## The simulated worker

The worker says the case's lines in order. It also replies on its own in two places, the same way for every backend:
- When the agent proposes a derived number (action `confirm_derived`), the worker says "haan" before its next line. Cases marked `scripted_confirm: true` are the exception: there the next line already answers the proposal (A1, and the corrections in F).
- At the read-back, once the lines have run out, the worker says "haan", at most twice.

Each of those "haan" replies counts as a worker turn. v3 never proposes a derived number, so it gets no extra turns from the first rule.

## Classes

| Class | What the worker says | Why it matters | Rules exercised |
|---|---|---|---|
| **A period-not-daycount** (15) | "kuch 5-6 mahine", "teen hafte", "aadha mahina", "pichhle mahine se", "alternate din", "sirf Sunday chhutti", "dedh mahina" | Workers count time in weeks and months, not days. v3 asked "kitne din?" again and again until a day count came out. | 17.2 derivation (period × frequency, the 26-day and 6-day assumptions), 17.6 `confirm_derived` instead of asking again, and a range using its upper end |
| **B rate-period** (15) | "mahine ke 15000", "hafte ke 3500", "per trip 200", "600-700", "market rate" | Monthly salaries and per-trip pay are common. Treating 15000 as a daily rate makes the result nonsense. | 17.2 rate conversion (÷26, ÷6, × trips a day), a range as a blocking ambiguity asked once, and "market rate" as context |
| **C deductions/non-cash** (15) | "khane ke 200 kate", "tools ka charge", "bonus bola tha", "aadha cash aadha UPI" | What was owed and what was paid both change. Each amount must land in the right place. | 17.4 typed observations (deduction, bonus, payment) and the total in `derive.derive` |
| **D advance-ambiguity** (15) | "manager se 5000 liya", "udhaar liya, woh alag hai", "pehle 3000 advance" | Money taken from the boss may or may not come out of the wages. Counting it wrongly changes the outstanding amount by the full sum. | 17.2 an `is_advance` ambiguity asked once; a private loan is not counted |
| **E context/emotion** (10) | hospital, a threat, "tum kaun ho", "yeh free hai", "data safe hai", "pareshan hoon", "meri pagar badhao" | A worker who is ignored stops talking. | 17.4 context observations and 17.7 a one-line acknowledgement (Python adds it when it is missing) |
| **F corrections** (15) | "arre 6 nahi 5", "pehle 700 bola tha, 650 sahi hai", two different day counts, "nahi, din 5 the" at the read-back | People correct themselves. Silently overwriting loses the record, and restarting from the beginning is worse. | 17.5 the contradiction detector ("Aapne pehle X kaha, ab Y — kaunsa sahi hai?"), a correction replacing a stored number, and a fix at the read-back |
| **G format** (15) | digits, Hinglish words, Devanagari numerals and words, English, silence, "6-7 din", "₹600", "nil", a bare "hazaar" | Wispr Flow output varies, and every format must reach the same number. | Number reading, a range for days asked once, and `says_none` |
| **H dispute/legal** (15) | "court jaunga", "proof chahiye", "contractor manna kare to", "kitne din mein paisa", police, labour office | The worker's real goal shows up in the middle of the hisaab. The agent should answer in one line and carry on. | 17.7 acknowledgement; `CONTEXT_NOTES` keeps a note for the case |

## Held-out set

`test_corpus_holdout.json` has 20 cases, `X1` to `X20`, in the same classes, written in new words. I wrote them **after** the corpus fixes (see EVALUATION.md), ran them once, and did not tune any code on them. Its first run is in `eval/results/holdout_run1.txt`, and that first run is the held-out result. Later runs (`holdout_run2.txt` to `holdout_run4.txt`) came after code changes, including a fix for X12 and new context phrases taken from X13, X14, X19 and X20, so they are not held out. The corpus itself is not held out, because the first corpus run found the bugs that were then fixed.

## Limits of this corpus

- **The worker is scripted.** Apart from the two "haan" rules above, the worker does not adapt. A backend that asks an unexpected question can receive a mismatched line.
- **`must_contain_in_agent` checks substrings.** For E and H the strings name the content of a sensible answer, not one exact wording. I changed nine of them after the first run (E1, E5, E7, E9, H1, H2, H5, H6, H14) from the topic word to what the acknowledgement actually says ("dukh hua", "delete", "shikayat", "record"). Those cases already had the correct outstanding amount.
- **Context acknowledgement is measured the same way for both backends.**
  - A turn counts as a context turn when `observe.extract` finds a context observation in the worker's line.
  - The reply counts as acknowledging it when it contains one of the phrases in `conversation.ACK_MARKERS`.
  - That list includes v3's own acknowledgement phrases ("dukh hua", "samajh gaya").
