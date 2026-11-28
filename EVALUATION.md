# PagarSaathi: before and after, measured

## Phase 16: observations and derivation

Every number in this section was printed by `evaluate.py` and is pasted from `eval/results/corpus_summary.txt`, `eval/results/holdout_run1.txt` and `eval/results/summary_phase16_testset.txt`. Transcripts are in `eval/results/corpus_*.json` and `eval/results/corpus_holdout_*.json`. To reproduce:

```bash
python3 evaluate.py --corpus test_corpus.json
```

```bash
python3 evaluate.py --corpus test_corpus_holdout.json
```

**What is compared:**
- **v3-before** is `legacy/v3_current.py`, a snapshot of `conversation.py` at tag `v3-before-derivation` (b379e75).
- **v4** is `conversation.py` with `observe.py` and `derive.py`.

**Rules path only.** Both columns ran without an LLM. The OpenAI key in the local `.env` is rejected (`agent_llm.decide` returns `None`), so the `v3-before-llm` and `v4-llm` backends could not be measured on this machine. The live site's key works. To measure the LLM path:

```bash
python3 evaluate.py --corpus test_corpus.json v3-before-llm v4-llm
```

The corpus classes and the simulated worker are described in [TEST_CORPUS.md](TEST_CORPUS.md). It has 115 cases, because the brief's per-class counts add up to 115.

### The proof conversation (A1)

A1 5-6 months → 130 days → ₹700: v3-before FAIL, v4 PASS

| Worker | v3-before | v4 |
|---|---|---|
| (opening) | Namaste, main PagarSaathi hoon. Bataiye, paise ko lekar kya pareshani hai? | Namaste, main PagarSaathi hoon. Bataiye, paise ko lekar kya pareshani hai? |
| meri pagar badhao. | Aapne kitne din kaam kiya? | Pagar badhwane se pehle, jo baaki hai uska hisaab pakka karte hain. Aapne kitne din kaam kiya? |
| kuch 5-6 mahine | Theek hai. Us mahine mein asal mein kitne din kaam kiya? Chhutti ke din chhod kar boliye. | 5-6 mahine, mahine ke 26 kaam ke din — matlab kareeb 156 din. Sahi hai, ya hafte mein kam din jaate the? `5-6 mo (6 used) × 26 d/mo ≈ 156` |
| maine kareeb har hafte ke paanch din | Roz ki mazdoori kitni tay hui thi? | 5-6 mahine, hafte mein 5 din — matlab kareeb 130 din. Sahi hai? `5-6 mo (6 used) × 4.33 wk × 5 d/wk ≈ 130` |
| Hafte mein 7 din mein se 5 din kaam kiye. 5 din | Ek din ke kitne rupaye tay hue the? Jaise saat sau rupaye. | Theek hai, 130 din. Roz ki mazdoori kitni tay hui thi? |
| roz 700 | Koi advance mila tha pehle? | Koi advance mila tha pehle? |
| advance nahi mila | Ab tak kitne paise mile? | Ab tak kitne paise mile? |
| nabbe hazaar teen sau mile | Confirm karta hoon: paanch din, saat sau roz, koi advance nahi, nabbe hazaar teen sau paid. Sahi hai? Overtime ya katauti thi to woh bhi bataiye. | Confirm karta hoon: ek sau tees din, saat sau roz, koi advance nahi, nabbe hazaar teen sau paid. Sahi hai? Overtime ya katauti thi to woh bhi bataiye. |
| haan | Kul kamaai teen hazaar paanch sau. Advance shunya, ab tak mila nabbe hazaar teen sau, kul mila nabbe hazaar teen sau. Hisaab ke hisaab se koi paisa baaki nahi hai. Case save ho gaya. | Kul kamaai ikyaanave hazaar. Advance shunya, ab tak mila nabbe hazaar teen sau, kul mila nabbe hazaar teen sau. Baaki saat sau rupaye. Ab kya karun: message bhejun, escalate karun, ya sirf case save karun? |
| **outstanding** | 0 | 700 |

### A1 on the live site (LLM path)

The corpus above ran on the rules path only. A1 was also played against https://pagarsaathi.up.railway.app, where the OpenAI key works and every turn ran on the LLM path (`text_source: llm`). These were HTTP runs of the same seven worker lines, plus the final "haan", sent to `/turn`.

| After commit | Runs | Outstanding | What the runs showed |
|---|---|---|---|
| 16116ae (Phase 16) | 1 | ₹700 | Passed, but turn 1 had two acknowledgements: Python's fixed line, then the LLM's own ("Aapki baat samajh mein aayi…"). |
| 9d2766b (one acknowledgement) | 3 | none | Turn 1 fixed. All three runs stalled at "nabbe hazaar teen sau mile": the agent re-asked instead of storing 90300. Locally, every misread value tried (90000 + 300, 90000, 9300) was rejected, and nothing recovered it. This bug was there before Phase 16. |
| 522ddd6 (misread amount falls back to Python's reading) | 3 | ₹700, ₹700, ₹700 | All passed. In two runs turn 1 asked for days and the daily rate in one question ("…kitne din kaam kiya aur roz kitna milta tha, bataiye?"). |
| 5673e1d (one number per question) | 3 | ₹700, ₹700, ₹700 | All passed, with one question and one acknowledgement per turn. In all three the LLM asked a single question on its own, so the one-number check had nothing to fix live. A local test (`test_llm_question_asking_two_numbers_becomes_one`) replays the two-number reply from the previous row. |

The first run after 5673e1d, verbatim:

| Worker | Agent (live, LLM path) |
|---|---|
| (opening) | Namaste, main PagarSaathi hoon. Bataiye, paise ko lekar kya pareshani hai? |
| meri pagar badhao. | Aapki baat samajh gaya, aapki mazdoori badhane ki ichha hai. Aapne kitne din kaam kiya? |
| kuch 5-6 mahine | 5-6 mahine, mahine ke 26 kaam ke din — matlab kareeb 156 din. Sahi hai, ya hafte mein kam din jaate the? `5-6 mo (6 used) × 26 d/mo ≈ 156` |
| maine kareeb har hafte ke paanch din | 5-6 mahine, hafte mein 5 din — matlab kareeb 130 din. Sahi hai? `5-6 mo (6 used) × 4.33 wk × 5 d/wk ≈ 130` |
| Hafte mein 7 din mein se 5 din kaam kiye. 5 din | Theek hai, 130 din. Roz ki mazdoori kitni tay hui thi? |
| roz 700 | Achha, roz 700 rupaye tay hue. Ab bataiye, aapko kitna advance mila tha? |
| advance nahi mila | Theek hai, aapko koi advance nahi mila. Ab tak aapko kitna payment mila hai? |
| nabbe hazaar teen sau mile | Confirm karta hoon: ek sau tees din, saat sau roz, koi advance nahi, nabbe hazaar teen sau paid. Sahi hai? Overtime ya katauti thi to woh bhi bataiye. |
| haan | Kul kamaai ikyaanave hazaar. Advance shunya, ab tak mila nabbe hazaar teen sau, kul mila nabbe hazaar teen sau. Baaki saat sau rupaye. Ab kya karun: message bhejun, escalate karun, ya sirf case save karun? |

The derived-number lines and the read-back are Python's in every run, and they were identical across runs. Only the LLM's own wording varied: the acknowledgement and the advance and payment questions.

What these runs do and don't show:
- **Three passing runs show the path works, not how often it fails.** The LLM is not deterministic.
- **There is no LLM-path number for the whole corpus.** The local key is rejected, so `v3-before-llm` and `v4-llm` have not been measured.

### Corpus: 115 cases

| Metric | v3-before | v4 |
|---|---|---|
| Passed (all checks) (%) | 40.9 | 100.0 |
| Task completion (%) | 82.6 | 100.0 |
| Correct outstanding (%) | 53.9 | 100.0 |
| Verbatim repetition rate (% of agent lines) | 0.2 | 0.0 |
| Avg worker turns (completed cases) | 5.78 | 6.02 |
| Re-asks per slot | 0.17 | 0.085 |
| Context acknowledged (% of context turns) | 12.5 | 95.8 |
| Irritation proxy (re-asks + unresolved conflicts per completed case) | 0.24 | 0.34 |
| Same, over all cases (unfinished ones included) | 0.68 | 0.34 |
| Context turns measured | 24 | 24 |
| Turns: LLM / fallback / rules | 0 / 0 / 652 | 0 / 0 / 692 |

| Class | v3-before | v4 |
|---|---|---|
| A | 0/15 | 15/15 |
| B | 2/15 | 15/15 |
| C | 5/15 | 15/15 |
| D | 9/15 | 15/15 |
| E | 5/10 | 10/10 |
| F | 4/15 | 15/15 |
| G | 12/15 | 15/15 |
| H | 10/15 | 15/15 |

**How to read this table:**
- **Re-asks per slot** counts turns where the agent is still on the same number question after the worker spoke.
- **The irritation proxy** is (re-asks + unresolved contradictions) per **completed** case, as the brief defines it. v3-before's re-asks sit mostly in the 20 cases it never finished, so they drop out of that average. The row below it counts every case.
- **Average worker turns** rose by about 0.2. That is the cost of the confirmation turn ("…130 din. Sahi hai?") that every derived number now gets.

**This corpus is not held out.** The first run of v4 on it, before any fixes, printed:
- 78.3% passed, 93.9% completed, 87.8% correct outstanding.
- v3-before printed 38.3% passed.

The failures in that run were real bugs, fixed in this phase. Each now has a regression test in `tests/test_observations.py`:
- A number for another slot said while a derived number waited for a yes was lost.
- A corrected period was rephrased away instead of being proposed.
- "6 nahi 5" and "pehle 700 bola tha, 650 sahi hai" were ignored, or summed into the advance.
- A second, different day count silently overwrote the first.
- "nahi, din 5 the" at the read-back restarted the whole case.
- "advance 1000 mila tha" was counted as both advance and payment.
- "ek trip ke 150" was read as 1 trip a day.
- "seven hundred per day" was read as 700 days.

v3-before went from 38.3% to 40.9% passed between the two runs, because nine `must_contain_in_agent` strings in classes E and H were corrected (see TEST_CORPUS.md).

### Held-out: 20 cases, first and only tuned-free run

These cases were written after the fixes above, run once, and not tuned on.

| Metric | v3-before | v4 |
|---|---|---|
| Passed (all checks) (%) | 50.0 | 95.0 |
| Task completion (%) | 90.0 | 100.0 |
| Correct outstanding (%) | 50.0 | 95.0 |
| Verbatim repetition rate (% of agent lines) | 0.0 | 0.0 |
| Avg worker turns (completed cases) | 5.78 | 6.1 |
| Re-asks per slot | 0.138 | 0.075 |
| Context acknowledged (% of context turns) | 0.0 | 0.0 |
| Irritation proxy (re-asks + unresolved conflicts per completed case) | 0.17 | 0.3 |
| Same, over all cases (unfinished ones included) | 0.55 | 0.3 |
| Context turns measured | 0 | 0 |
| Turns: LLM / fallback / rules | 0 / 0 / 114 | 0 / 0 / 122 |

| Class | v3-before | v4 |
|---|---|---|
| A | 0/4 | 4/4 |
| B | 0/3 | 3/3 |
| C | 1/3 | 3/3 |
| D | 1/2 | 1/2 |
| E | 2/2 | 2/2 |
| F | 2/2 | 2/2 |
| G | 2/2 | 2/2 |
| H | 2/2 | 2/2 |

**What the held-out run shows:**
- **X12 fails on v4.** The worker said "bhai se 1000 udhaar liya, woh alag hai". `observe.py` sees the loan is private, but on the rules path the core still stores 1000 as the advance. This is a known bug and is left unfixed.
- **0 context turns were detected** in the held-out lines. `observe.py`'s context words miss "darr lag raha hai", "sarkari app", "shikayat karni hai" and "thekedar bhaag gaya". This is a gap in the context detector, not an acknowledgement result.
- **A second run was made after a later change.** A private-loan acknowledgement was added after the original test set's I2 case. In that run (`eval/results/holdout_run2.txt`), X12 still fails, and its loan line now counts as one acknowledged context turn for both backends.

### The original 32-case test set after Phase 16

`python3 evaluate.py v3-fallback` is the rules path of `conversation.py`, which is now v4:

v3-fallback: 32 cases in 0.0s; wrong or no result: none

| Metric | v3-fallback |
|---|---|
| Slot accuracy (%) | 100.0 |
| Math correctness (%) | 100.0 |
| Completed to a result (%) | 100.0 |
| Verbatim repetition rate (% of agent lines) | 0.0 |
| Cases with any repeat | 0 |
| Avg worker turns to result | 5.75 |
| Bundled-input success (%) | 100.0 |
| Context acknowledgement (%) | 83.3 |
| Turns: LLM / fallback / rules | 0 / 184 / 0 |

Before this phase, the same command printed:
- slots 93.0%, maths 84.4%, completed 90.6%;
- bundled 85.7%, context 66.7%;
- failures: C2, G1, I2, N1, N2.

That run used the committed code at b379e75, in a clean `git worktree`. During this phase, this set also exposed problems in the new code: C2, I2, M1 and N1 regressed at first and were then fixed. So it is not held-out evidence for v4 either. The v3-fallback column further down this page is older still. It comes from run 2, before later phases.

**One wording fix during this phase.** The health acknowledgement changed from "Tabiyat kharab thi" (you were ill) to "Yeh sunkar dukh hua, samajh sakta hoon". The old line was wrong when the person who was ill was the worker's wife (case C2).

---

## Earlier phases (32-case test set)

Every number in this part was printed by `evaluate.py` on the 32-case test set ([TEST_SET.md](TEST_SET.md)). Full transcripts are in `eval/results/`.

To reproduce (v2-llm and v3 need `OPENAI_API_KEY` or `OPENROUTER_API_KEY`):

```bash
python3 evaluate.py all
```

| Version | Code | Tag |
|---|---|---|
| v1 (fixed loop) | `legacy/v1_conversation.py` with its own rule reader | `v1-original` = 64e9bef |
| v2 (current, before this run) | `legacy/v2_conversation.py`, rules path | `v2-current` = 6c0653a |
| v2-llm | The same v2 commit with its LLM reader (`legacy/v2_agent_llm.py`). v2 already had this optional LLM layer, so it is measured too. | 6c0653a |
| v3-fallback | `conversation.py`, rules path (what runs with no key) | this run |
| v3 (autonomous) | `conversation.py` LLM dialogue policy, `gpt-4.1-mini` | this run |

## Results

Same run for all five versions (`eval/results/summary_run2.txt`):

| Metric | v1 (fixed loop) | v2 (current) | v2-llm | v3-fallback | v3 (autonomous) |
|---|---|---|---|---|---|
| Slot accuracy | 64.1% | 86.7% | 94.5% | 86.7% | **100.0%** |
| Math correctness | 53.1% | 75.0% | 90.6% | 75.0% | **100.0%** |
| Completed to a result | 68.8% | 90.6% | 90.6% | 90.6% | **100.0%** |
| Verbatim repetition rate | 0.6% | 0.0% | 0.0% | 0.0% | **0.0%** |
| Avg worker turns to result | 6.64 | 5.83 | 6.14 | 5.83 | **5.75** |
| Bundled-input success | 0.0% | 85.7% | 57.1% | 85.7% | **100.0%** |
| Context acknowledgement | 0.0% | 0.0% | 50.0% | 66.7% | **83.3%** |
| Turns: LLM / fallback / rules | 0 / 0 / 174 | 0 / 0 / 181 | 182 / 0 / 0 | 0 / 181 / 0 | 184 / 0 / 0 |

Wrong or no result, per version:
- v1: B1, B2, C1, C2, G1, G2, I2, L1, L2, M1, M2, N1, N2, O1, O2
- v2: C2, G1, G2, I2, N1, N2, O1, O2
- v2-llm: C2, M1, M2
- v3-fallback: C2, G1, G2, I2, N1, N2, O1, O2
- v3: none

The last row shows every v3 turn came from the LLM: no outages, no silent fallback.

### v3 is not deterministic, and it was tuned once

| v3 run | Code | Slot accuracy | Math | Completed | Repetition | Bundled | Context ack | Failed cases |
|---|---|---|---|---|---|---|---|---|
| First held-out run | 665c7ba, before any changes from this test set | 97.7% | 90.6% | 90.6% | 0.0% | 85.7% | 66.7% | H1, I2, L1 |
| Run 2 (table above) | after one round of fixes | 100.0% | 100.0% | 100.0% | 0.0% | 100.0% | 83.3% | none |
| Run 3 | same code | 99.2% | 96.9% | 100.0% | 0.0% | 100.0% | 66.7% | G2 |
| Run 4 | same code | 100.0% | 100.0% | 100.0% | 0.0% | 100.0% | 83.3% | none |
| Run 5 | after the audit layer, languages and the contradiction question | 97.7% | 96.9% | 100.0% | 0.0% | 100.0% | 83.3% | O2 |
| Run 6 | run 5 code + the rules-path correction fix below | 100.0% | 100.0% | 100.0% | 0.0% | 100.0% | 83.3% | none |
| Run 7 | final code (+ Marathi numbers, yes/no and script guard) | 100.0% | 100.0% | 100.0% | 0.0% | 100.0% | 83.3% | none |

**What the one round of fixes changed** (after reading the first-run failures):
- **H1:** the model checked the worker's sum itself and got it wrong ("4000 nahi hota", though 5 × 800 = 4,000). The prompt now forbids checking whether numbers add up.
- **I2:** "advance nahi mila" was lost because a private loan was in the same sentence. Python now has a backstop for an explicit "advance nahi".
- **L1:** "rate 700" in an English bundle wasn't extracted. Python now keeps a number the worker clearly tagged ("rate 700") if the model missed it.
- **C1/C2:** a bundle that completed all four numbers jumped straight to Python's read-back and dropped the model's acknowledgement. The acknowledgement is now kept in front of the read-back.

These are general rules, not answers to specific cases. They were still chosen after seeing this test set, so **the first-run numbers are the honest held-out score. Runs 2–4 show the variance after tuning.**

### Runs 5 and 6: after the audit-layer phase

**Run 5 (O2):** the LLM timed out on one turn ("sorry, advance 500 tha"), so that turn used the rules, which stored 500 as the payments being asked about. The worker's later "3000 mile" replaced it, and the read-back kept the wrong ₹1,000 advance; the harness's automatic "haan" confirmed it. The new contradiction question was not involved.

**The fix (rules path):** if the worker tags a number that is already known ("advance 500") while a different question is open, the rules now treat it as a correction of that number and ask the open question again. It is general, not specific to O2, and it also changed the no-key path:

| v3-fallback | Slot accuracy | Math | Failed cases |
|---|---|---|---|
| Before (run 2 table above) | 86.7% | 75.0% | C2, G1, G2, I2, N1, N2, O1, O2 |
| After the correction fix | 93.0% | 84.4% | C2, G1, I2, N1, N2 |

**Runs 6 and 7** are on the committed code (run 7 after the Marathi fixes, which do not change Hindi behaviour; 184 of 184 turns came from the LLM). Transcripts: `eval/results/v3-run5.json`, `eval/results/v3-run6.json`, `eval/results/v3-run7.json`, `eval/results/v3-fallback.json`. As before, this fix was made after seeing a failure on this test set, so it is tuning, not a held-out result.

## How the logic evolved

**v1 (the first state machine) could not:**
- read more than one fact from a message. Bundled success was **0%**. A message such as "6 din, 700 roz…" became one number, or a re-ask.
- take an answer out of order (N1, N2), or take a correction (G, O).
- acknowledge anything said outside the numbers. Context acknowledgement was **0%**.

After two misses it said "Mujhe theek se samajh nahi aaya. Neeche likh kar bataiye. Kitne din kaam kiya? Sirf number boliye, jaise chhe din." on every following miss. That is the verbatim repetition measured in L1, the one case with a repeat: "I worked 6 days, rate 700" was two numbers, so v1 rejected it, then got stuck on the days question while the worker moved on to the advance and payments. Most cases end before a third miss, so this metric understates v1's looping on a longer exchange.

**v2 fixed:**
- **Bundled facts.** Several facts in one message, by tagging each number with the word next to it ("din", "roz", "advance", "mile"). Bundled success rose to **85.7%**.
- **Repetition.** Re-asks change wording, so the measured repetition rate is **0%**.
- **Wrong totals in v1's failed cases.** Slot accuracy rose from 64.1% to **86.7%** and math from 53.1% to **75.0%**.

**v2 still could not:**
- **follow the conversation.** It runs the fixed order ASK_DAYS → … → CONFIRM. So it failed every case where the worker answers out of order (N1, N2), corrects mid-flow (O1, O2, G2), or says "nahi" at the read-back (G1, where it restarts from zero).
- **acknowledge context** (0%). "mera beta bimar hai" got the same next question.
- **tell a cut loan from a private loan** (I2).

Its optional LLM reader (v2-llm) fixed many of these, but it still followed the fixed order, and its bundled success was 57.1%.

**v3 adds:**
- **An LLM policy that chooses every move.** The moves are ask, follow up, clarify, acknowledge context, handle off-topic, rephrase and conclude. It reads a frame: the four numbers, `context_notes`, `unresolved`, `last_question` and `turn_count`.
- **Python guards.** A number is stored only if the worker said it. Python adds amounts. A line is blocked if it states an amount the worker didn't say. Neither the same line nor the same question is allowed twice in a row without progress. After 1 ask and 2 rephrases, Python moves on and marks the number unresolved. At 12 turns it stops and points to a union or India Labourline (1800 1800 999). The read-back always comes before the maths.
- **A better no-key path.** v3-fallback now acknowledges hospital, loan and years topics (66.7% context acknowledgement against v2's 0%), with the same accuracy as v2.

**What v3 still cannot do:**
- **Every contradiction.** In run 3, case G2 got "5 din ya 6 din?" instead of taking "nahi nahi, 5 din" as a correction. The scripted worker had moved on, so the read-back said 6 days and the harness's automatic "haan" confirmed it. A real worker would have the read-back to catch it, but the policy does not always take a correction.
- **Every context acknowledgement.** It reached 66.7–83.3% across runs. C2 (a wife's illness inside a bundle) is not always acknowledged.
- **Cost and latency.** One LLM call per turn: about 2 s locally, and 6–16 s per turn on the live site, mostly the Sarvam voice.
- **Learning.** It does not learn from conversations. Every improvement is a prompt or code change, measured against this set.
- **Work without keys.** v3-fallback is exactly as accurate as v2 (86.7% slots, 75.0% math). Only its context handling improved.

## Caveats about the measurement

- **The worker is scripted.** The worker's lines don't adapt to what the agent asks. A version that asks something unexpected can get a mismatched answer, which penalises every version equally.
- **Context acknowledgement is a keyword check** on the reply to the context message (see [TEST_SET.md](TEST_SET.md)).
- **32 cases is a small set.** One case is 3.1 percentage points of math correctness.
