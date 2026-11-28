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
