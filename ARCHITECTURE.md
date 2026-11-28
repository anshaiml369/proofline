# PagarSaathi: architecture decision

## 1. Do we need a custom neural network (an RNN or LSTM)?

**No.**

The design we build (an LLM policy plus a frame) already is the recurrent architecture that was proposed. It just doesn't need training.

| RNN idea | PagarSaathi |
|---|---|
| Hidden state | **The frame**: the four numbers (`days`, `rate`, `advance`, `payments`), `context_notes`, `unresolved`, `last_question`, `turn_count` |
| Input at step *t* | The worker's latest Wispr Flow message |
| Cell function | **The LLM policy** (`prompts/policy.txt`): reads the frame, the whole transcript and the input |
| Output and new state | A JSON action (`ask_slot`, `clarify`, `acknowledge_context`, ...), the line to say, and the facts it heard. Python validates those facts and writes the next frame. |

Each turn reads the state and the input, then returns an action and an updated state. That is the loop the RNN proposal describes.

The difference is in where the knowledge comes from:
- A **trained** RNN or LSTM dialogue-state tracker learns that cell function from data. It would need thousands of labelled Hinglish wage-dispute dialogues, and no such dataset exists.
- A **prompted** LLM already reads Hinglish, Devanagari, digits and spelled-out numbers, and it can follow the rules we write.

In two days a small model trained on a few hundred synthetic examples would do worse than the prompted LLM on exactly the inputs that matter: bundled sentences, context, corrections and code-mixing. So we do not build one.

## 2. Three architectures compared

| | What it is | Data needed | Time to build | Expected accuracy | Risk |
|---|---|---|---|---|---|
| **(a) Fine-tuned small classifier + LLM** | A small model (for example IndicBERT or MuRIL) tags each number with a slot; an LLM only writes the reply | A few thousand labelled Hinglish utterances, each number tagged with its slot | 2–4 weeks, including labelling | High on the patterns in its training data; weak on context it has never seen (hospital, a loan) | Needs a labelled dataset we don't have; drifts as real phrasing changes |
| **(b) RNN or LSTM dialogue-state tracker** (the original proposal) | A recurrent network carries the dialogue state across turns and predicts slot values and the next action | Thousands of complete annotated dialogues | 4–8 weeks | Below (a) and (c) until there is a lot of data; it has no knowledge of the world beyond its training dialogues | Not feasible now: there is no data, and it would lose to a prompted LLM |
| **(c) LLM policy + frame** (what we build) | The LLM decides each move from the frame and transcript; Python validates numbers, breaks loops and does the maths | None to start; a prompt, plus a held-out test set to measure it | Days | Measured in [EVALUATION.md](EVALUATION.md) | Cost and latency per turn; needs an API key (rules take over without one) |

**(a) and (b) are optional future work. They are not built in this run.** Real conversations from a pilot, once anonymised and labelled, could later train (a) as a cheaper, faster slot reader underneath (c).

## 3. Honest limitations of (c)

- **Cost per turn.** Every worker message is one LLM call (`gpt-4.1-mini`, about 1–2k tokens in and up to 400 out), plus one Sarvam voice clip.
- **Latency.** The LLM takes about 2 s per turn. Live turns measured 6–16 s, because the Sarvam voice is added on top. The LLM gets at most 8 s per turn (`LLM_TIMEOUT_S`); after that the turn uses the rules.
- **It needs keys.** Without an OpenAI or OpenRouter key, the built-in rules run instead. They handle a few known topics (hospital, loan, years, "ek hafta") but are much less flexible. The evaluation reports them separately as `v3-fallback`.
- **It cannot settle a truly contradictory account.** If the worker's own figures conflict and they cannot resolve them, the agent can ask and read back, but it cannot know which figure is true. After the turn cap it points them to a union or a helpline.
- **No learning.** The policy does not improve from conversations. Every change is a prompt or code change, checked against the test set.
- **One work period at a time.** It works out one stretch of work, such as a week or a month, at one daily rate. Overtime, half days and several rates are not modelled.

## 4. Observations and derivation (Phase 16)

### The old frame and the new frame

**Old (v3).** The frame held four slots: `days`, `rate`, `advance` and `payments`. The agent's job was to fill each one with a number the worker said.
- When the worker said "kuch 5-6 mahine", there was no day count to fill, so v3 asked "kitne din?" again.
- Then "har hafte ke paanch din" arrived, and the 5 was taken as **5 days of work**.
- The proof conversation ended at ₹0 outstanding instead of ₹700. See the A1 row in [EVALUATION.md](EVALUATION.md).

**New (v4).** The frame stores **observations**: what the worker actually said, tagged by type.

| Type | Example |
|---|---|
| `period` | "5-6 mahine" → `{value: "5-6", unit: "month", range: [5, 6]}` |
| `frequency` | "hafte mein 5 din" |
| `explicit_days` | "26 din" |
| `rate` | per day, per week, per month or per trip, with an optional range |
| `trips` | trips per day |
| `advance` | can be marked `ambiguous` |
| `payment` | an amount received |
| `deduction` | an amount cut |
| `bonus` | an amount promised |
| `context` | something said outside the numbers |

From these, `derive.py`, which is pure Python, computes `canonical` (the four numbers and the outstanding amount), a `derivation` entry for each number, and an `ambiguity` list.
- Each `derivation` entry holds `{value, formula, source, confirmed, assumption}`.
- Each `ambiguity` item holds `{slot, kind, blocking, question}`.

**A derived number is not a fact until the worker agrees.** The agent says the formula in words and waits for a yes:

> "5-6 mahine, hafte mein 5 din — matlab kareeb 130 din. Sahi hai?"

The `?debug=1` view shows the formula itself: `5-6 mo (6 used) × 4.33 wk × 5 d/wk ≈ 130`.

### The rule

**Never ask for a number Python can compute.** Ask only for the one thing it cannot: a range end, a missing period, trips a day, or whether a loan is an advance. Ask that once.

The LLM tags observations. It never converts units or does arithmetic (`prompts/policy.txt`, OBSERVATIONS and DERIVED NUMBERS). Python also drops any LLM observation whose number the worker never said (`_valid_llm_observations`).

### Stated assumptions (said aloud whenever used)

| Constant | Value | Used for |
|---|---|---|
| `WORK_DAYS_PER_MONTH` | 26 | A period in months with no weekly frequency; a monthly rate ÷ 26 |
| `WEEKS_PER_MONTH` | 4.33 | months × weeks × days a week |
| `DEFAULT_DAYS_PER_WEEK` | 6 | A period in weeks with no frequency; a weekly rate ÷ 6 |

For a range like "5-6 mahine", the first proposal uses the upper end, and the confirmation line names the range. If the worker says "nahi, 5 mahine", that corrects it. A bare "nahi" gets one question: "5 ya 6, kaunsa?"

### Where it lives

**There is no `graph.py` in this codebase.** The brief described a `derive` node between `extract` and `validate` in a graph. Here the conversation is one state machine in `conversation.py`, so the node is a function: `derive_turn()`.
- It runs first on every collecting turn, called from `_pre()` before the existing core turn logic (`_step_core` and `_step_policy_core`).
- When derivation has nothing to say (for example plain "6 din" or "700 roz"), it returns `None`, and the core handles the turn exactly as before. That keeps the scripted demo lines byte-identical, so their recorded clips still match.
- `node_path` records `DERIVE` whenever a derived number is proposed.

### Validate: contradictions, rephrasing and acknowledgement (Python)

**Contradiction (17.5).** When a new observation disagrees with a stored one of the same type and is not marked as a correction ("nahi", "arre", "galat"), nothing is overwritten.
- The agent asks: "Aapne pehle 6 din kaha, ab 5 din — kaunsa sahi hai?"
- The worker's answer decides, and both values stay in the turn record.
- "X nahi Y" and "pehle X bola tha, Y sahi hai" are read against the stored numbers, so a correction with no unit still lands on the right slot.

**Rephrase guard (17.6).** In `_post()`, a reply more than 80% similar to the previous agent line is replaced with that question's next rephrasing, in the order `angle`, then `example`, then `simpler`. Similarity is measured with `difflib`. A re-ask of the same question type is replaced the same way.
- `last_question_type` is stored in the session.
- A new derived number ("…52 din" becoming "…26 din") is not treated as a repeat.

**Acknowledgement (17.7).** When the worker's turn holds a `context` observation and the reply has none of the phrases in `ACK_MARKERS`, Python adds one fixed line from `ACKS` in front of the reply. Examples:
- "Dara mat, hum sirf hisaab nikal rahe hain."
- "Main PagarSaathi, aapki pagar ka hisaab karne ke liye."

**Deviation from the brief.** The brief said to reject the reply and re-prompt the LLM once. Python adds a fixed line instead, because a second LLM call adds 2 s or more to the turn and can fail again. A fixed line is always one line and always present.
