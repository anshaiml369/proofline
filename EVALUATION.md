# PagarSaathi: before and after, measured

Every number on this page was printed by `evaluate.py` on the 32-case test set ([TEST_SET.md](TEST_SET.md)). Full transcripts are in `eval/results/`.

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

**What the one round of fixes changed** (after reading the first-run failures):
- **H1:** the model checked the worker's sum itself and got it wrong ("4000 nahi hota", though 5 × 800 = 4,000). The prompt now forbids checking whether numbers add up.
- **I2:** "advance nahi mila" was lost because a private loan was in the same sentence. Python now has a backstop for an explicit "advance nahi".
- **L1:** "rate 700" in an English bundle wasn't extracted. Python now keeps a number the worker clearly tagged ("rate 700") if the model missed it.
- **C1/C2:** a bundle that completed all four numbers jumped straight to Python's read-back and dropped the model's acknowledgement. The acknowledgement is now kept in front of the read-back.

These are general rules, not answers to specific cases. They were still chosen after seeing this test set, so **the first-run numbers are the honest held-out score. Runs 2–4 show the variance after tuning.**

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
