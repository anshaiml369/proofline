"""Evaluate PagarSaathi's conversation logic on the held-out test set (test_cases.json).

    python3 evaluate.py v1 v2 v3-fallback v3        # v3 needs OPENAI_API_KEY or OPENROUTER_API_KEY
    python3 evaluate.py all
    python3 evaluate.py --corpus test_corpus.json      # Phase 16 corpus: v3-before vs v4 (see below)

Versions:
  v1           legacy/v1_conversation.py  (tag v1-original, 64e9bef), its own rule reader
  v2           legacy/v2_conversation.py  (tag v2-current, 6c0653a), rules path (no key)
  v2-llm       the same v2 commit with its LLM reader (legacy/v2_agent_llm.py); needs a key
  v3-fallback  conversation.py rules path (what runs with no key)
  v3           conversation.py LLM dialogue policy (agent_llm.decide + step_policy); rules if a call fails

Each case is played turn by turn with the worker's scripted lines. When the lines run out and the
agent is at the read-back, the harness answers "haan" (up to twice). Results: eval/results/<version>.json
(full transcripts) and a summary table on stdout.
"""
import concurrent.futures
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

SLOTS = ("days", "rate", "advance", "payments")
OUT_DIR = os.path.join(ROOT, "eval", "results")


# ---------- adapters: (new_session, opening, turn(session, text) -> reply, policy_source) ----------

def adapter(version):
    if version == "v1":
        import legacy.v1_conversation as m
        return m.new_session, m.opening, lambda s, t: (m.step(s, t, m.local_extract), "rules")
    if version == "v2":
        import legacy.v2_conversation as m
        return m.new_session, m.opening, lambda s, t: (m.step(s, t, m.local_extract), "rules")
    if version == "v2-llm":
        import legacy.v2_agent_llm as llm
        import legacy.v2_conversation as m

        def turn(s, t):
            understood = llm.understand(s, s["last_agent_text"], t)
            if understood:
                return m.step_llm(s, t, understood), "llm"
            return m.step(s, t, m.local_extract), "fallback"
        return m.new_session, m.opening, turn
    if version == "v3-fallback":
        import conversation as m
        return m.new_session, m.opening, lambda s, t: (m.step(s, t, m.local_extract), "fallback")
    if version == "v3":
        import agent_llm
        import conversation as m
        if not agent_llm.enabled():
            raise SystemExit("v3 needs OPENAI_API_KEY or OPENROUTER_API_KEY; run v3-fallback instead")

        def turn(s, t):
            decision = agent_llm.decide(s, t)
            if decision:
                return m.step_policy(s, t, decision), "llm"
            return m.step(s, t, m.local_extract), "fallback"
        return m.new_session, m.opening, turn
    raise SystemExit(f"unknown version {version}")


# ---------- one case ----------

def _norm(s):
    return " ".join(re.sub(r"[^\w\s]", " ", s.lower()).split())


def run_case(version, case):
    new_session, opening, turn = adapter(version)
    s = new_session()
    agent = [opening(s)["agent_text"]]
    log, sources = [], []
    bundled_ok = None
    worker_turns = 0
    lines = list(case["turns"])
    confirms = 0
    i = 0
    while True:
        if s.get("case") is not None:
            break
        if i < len(lines):
            text = lines[i]
        elif s["state"] == "CONFIRM" and confirms < 2:
            text, confirms = "haan", confirms + 1
        else:
            break
        reply, source = turn(s, text)
        worker_turns += 1
        sources.append(source)
        agent.append(reply["agent_text"])
        log.append({"worker": text, "agent": reply["agent_text"], "state": s["state"],
                    "facts": dict(s["facts"]), "source": source, "action": reply.get("action")})
        if case["bundled_turn"] == i:
            bundled_ok = all(s["facts"].get(k) == case["expected"][k] for k in case["bundled_slots"])
        i += 1

    final = s["case"] or s["facts"]
    slots = {k: final.get(k) == case["expected"][k] for k in SLOTS}
    math_ok = bool(s["case"]) and s["case"]["outstanding"] == case["expected"]["outstanding"]
    # a verbatim repeat: an agent line identical to one of the two agent lines before it
    repeats = sum(1 for j in range(1, len(agent)) if _norm(agent[j]) in {_norm(a) for a in agent[max(0, j - 2):j]})
    ctx_ack = None
    if case["expect_context_ack"]:
        reply = log[case["context_turn"]]["agent"].lower() if case["context_turn"] < len(log) else ""
        ctx_ack = any(k in reply for k in case["context_keywords"])
    return {"id": case["id"], "category": case["category"], "slots": slots, "math_ok": math_ok,
            "completed": bool(s["case"]), "outstanding": (s["case"] or {}).get("outstanding"),
            "expected": case["expected"], "final_facts": {k: final.get(k) for k in SLOTS},
            "agent_lines": len(agent) - 1, "repeats": repeats, "worker_turns": worker_turns,
            "context_ack": ctx_ack, "bundled_ok": bundled_ok, "sources": sources,
            "context_notes": s.get("context_notes"), "transcript": [{"agent": agent[0]}] + log}


def summarise(version, results):
    n = len(results)
    slot_hits = sum(sum(r["slots"].values()) for r in results)
    completed = [r for r in results if r["completed"]]
    ctx = [r for r in results if r["context_ack"] is not None]
    bundled = [r for r in results if r["bundled_ok"] is not None]
    lines = sum(r["agent_lines"] for r in results)
    src = [x for r in results for x in r["sources"]]
    return {
        "version": version, "cases": n,
        "slot_accuracy": round(100 * slot_hits / (4 * n), 1),
        "math_correct": round(100 * sum(r["math_ok"] for r in results) / n, 1),
        "completed": round(100 * len(completed) / n, 1),
        "repetition_rate": round(100 * sum(r["repeats"] for r in results) / max(lines, 1), 1),
        "cases_with_repeat": sum(1 for r in results if r["repeats"]),
        "avg_turns_completed": round(sum(r["worker_turns"] for r in completed) / max(len(completed), 1), 2),
        "bundled_success": round(100 * sum(r["bundled_ok"] for r in bundled) / max(len(bundled), 1), 1),
        "bundled_cases": len(bundled),
        "context_ack": round(100 * sum(r["context_ack"] for r in ctx) / max(len(ctx), 1), 1),
        "context_cases": len(ctx),
        "llm_turns": src.count("llm"), "fallback_turns": src.count("fallback"), "rules_turns": src.count("rules"),
    }


def evaluate(version, cases, workers=6):
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers if version in ("v3", "v2-llm") else 1) as ex:
        results = list(ex.map(lambda c: run_case(version, c), cases))
    summary = summarise(version, results)
    summary["seconds"] = round(time.time() - t0, 1)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f"{version}.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=1)
    return summary, results


ROWS = [("Slot accuracy (%)", "slot_accuracy"), ("Math correctness (%)", "math_correct"),
        ("Completed to a result (%)", "completed"), ("Verbatim repetition rate (% of agent lines)", "repetition_rate"),
        ("Cases with any repeat", "cases_with_repeat"), ("Avg worker turns to result", "avg_turns_completed"),
        ("Bundled-input success (%)", "bundled_success"), ("Context acknowledgement (%)", "context_ack"),
        ("Turns: LLM / fallback / rules", None)]


def table(summaries):
    head = "| Metric | " + " | ".join(s["version"] for s in summaries) + " |"
    out = [head, "|---" * (len(summaries) + 1) + "|"]
    for label, key in ROWS:
        if key:
            cells = [str(s[key]) for s in summaries]
        else:
            cells = [f"{s['llm_turns']} / {s['fallback_turns']} / {s['rules_turns']}" for s in summaries]
        out.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(out)


# ---------- Phase 16: the corpus (test_corpus.json), v3 before derivation vs v4 ----------
#
#   python3 evaluate.py --corpus test_corpus.json                 # v3-before vs v4, rules path
#   python3 evaluate.py --corpus test_corpus.json v3-before-llm v4-llm   # needs a working key
#
# v3-before      legacy/v3_current.py (tag v3-before-derivation), rules path
# v3-before-llm  the same snapshot with its LLM policy (legacy/v3_agent_llm.py)
# v4             conversation.py rules path (observations -> derive.py -> confirm)
# v4-llm         conversation.py LLM policy (agent_llm.decide + step_policy)
#
# The simulated worker says the case's lines in order. Two adaptive replies, the same for every
# backend: when the agent proposes a derived number (action confirm_derived) and the case is not
# scripted_confirm, the worker says "haan" before the next line; at the read-back (CONFIRM) with no
# lines left, "haan" (up to twice). Every such "haan" counts as a worker turn.

ASK_STATES = {"ASK_DAYS": "days", "ASK_RATE": "rate", "ASK_ADVANCE": "advance", "ASK_PAYMENTS": "payments"}
CORPUS_TURN_LIMIT = 20


def corpus_adapter(backend):
    if backend == "v3-before":
        import legacy.v3_current as m
        return m.new_session, m.opening, lambda s, t: (m.step(s, t, m.local_extract), "rules")
    if backend == "v3-before-llm":
        import legacy.v3_agent_llm as llm
        import legacy.v3_current as m
        if not llm.enabled():
            raise SystemExit("v3-before-llm needs OPENAI_API_KEY or OPENROUTER_API_KEY")

        def turn(s, t):
            decision = llm.decide(s, t)
            return (m.step_policy(s, t, decision), "llm") if decision else (m.step(s, t, m.local_extract), "fallback")
        return m.new_session, m.opening, turn
    if backend == "v4":
        import conversation as m
        return m.new_session, m.opening, lambda s, t: (m.step(s, t, m.local_extract), "rules")
    if backend == "v4-llm":
        import agent_llm
        import conversation as m
        if not agent_llm.enabled():
            raise SystemExit("v4-llm needs OPENAI_API_KEY or OPENROUTER_API_KEY")

        def turn(s, t):
            decision = agent_llm.decide(s, t)
            return (m.step_policy(s, t, decision), "llm") if decision else (m.step(s, t, m.local_extract), "fallback")
        return m.new_session, m.opening, turn
    raise SystemExit(f"unknown corpus backend {backend}")


def _acked(reply):
    import conversation
    return any(m in reply.lower() for m in conversation.ACK_MARKERS)


def run_corpus_case(backend, case):
    import observe
    new_session, opening, turn = corpus_adapter(backend)
    s = new_session()
    first = opening(s)
    agent, log, sources = [first["agent_text"]], [], []
    queue, confirms, auto_yes = list(case["turns"]), 0, 0
    reasks = ctx_turns = ctx_acked = 0
    last_action = None
    while s.get("case") is None and len(log) < CORPUS_TURN_LIMIT:
        if last_action == "confirm_derived" and not case["scripted_confirm"]:
            text, auto_yes = "haan", auto_yes + 1
        elif queue:
            text = queue.pop(0)
        elif s["state"] == "CONFIRM" and confirms < 2:
            text, confirms = "haan", confirms + 1
        elif last_action == "confirm_derived":
            text, auto_yes = "haan", auto_yes + 1
        else:
            break
        before = s["state"]
        reply, source = turn(s, text)
        sources.append(source)
        agent.append(reply["agent_text"])
        last_action = reply.get("action")
        # a re-ask: the agent is still on the same number question after the worker answered it
        if before in ASK_STATES and s["state"] == before and ASK_STATES[before] not in s["facts"] \
                and last_action != "confirm_derived" and text.strip():
            reasks += 1
        if any(o["type"] == "context" for o in observe.extract(text)):
            ctx_turns += 1
            ctx_acked += _acked(reply["agent_text"])
        log.append({"worker": text, "agent": reply["agent_text"], "state": s["state"], "action": last_action,
                    "formula": (reply.get("derivation") or {}).get("formula"), "clarify": reply.get("clarify"),
                    "facts": {k: s["facts"].get(k) for k in SLOTS}, "source": source})
    result = s.get("case")
    outstanding = (result or {}).get("outstanding")
    correct = result is not None and outstanding == case["expected_outstanding"]
    joined = " ".join(agent).lower()
    missing = [m for m in case["must_contain_in_agent"] if m.lower() not in joined]
    repeats = sum(1 for j in range(1, len(agent)) if _norm(agent[j]) in {_norm(a) for a in agent[max(0, j - 2):j]})
    unresolved = 1 if s.get("pending_obs_conflict") else 0
    passed = correct and not missing and not (case["must_not_repeat"] and repeats)
    return {"id": case["id"], "class": case["class"][0], "hard": case["must_pass_hard"], "passed": passed,
            "completed": result is not None, "correct": correct, "outstanding": outstanding,
            "expected_outstanding": case["expected_outstanding"], "missing": missing, "repeats": repeats,
            "agent_lines": len(agent) - 1, "worker_turns": len(log), "auto_yes": auto_yes, "reasks": reasks,
            "unresolved": unresolved, "ctx_turns": ctx_turns, "ctx_acked": ctx_acked, "sources": sources,
            "transcript": [{"agent": agent[0]}] + log}


def summarise_corpus(backend, results):
    n = len(results)
    done = [r for r in results if r["completed"]]
    lines = sum(r["agent_lines"] for r in results)
    ctx = sum(r["ctx_turns"] for r in results)
    src = [x for r in results for x in r["sources"]]
    per_class = {}
    for r in results:
        c = per_class.setdefault(r["class"], [0, 0])
        c[0] += r["passed"]
        c[1] += 1
    return {
        "backend": backend, "cases": n,
        "passed": round(100 * sum(r["passed"] for r in results) / n, 1),
        "completed": round(100 * len(done) / n, 1),
        "correct_outstanding": round(100 * sum(r["correct"] for r in results) / n, 1),
        "repetition_rate": round(100 * sum(r["repeats"] for r in results) / max(lines, 1), 1),
        "avg_turns": round(sum(r["worker_turns"] for r in done) / max(len(done), 1), 2),
        "reasks_per_slot": round(sum(r["reasks"] for r in results) / (4 * n), 3),
        "context_ack": round(100 * sum(r["ctx_acked"] for r in results) / max(ctx, 1), 1),
        "context_turns": ctx,
        "irritation": round(sum(r["reasks"] + r["unresolved"] for r in done) / max(len(done), 1), 2),
        "irritation_all": round(sum(r["reasks"] + r["unresolved"] for r in results) / n, 2),
        "per_class": {k: f"{v[0]}/{v[1]}" for k, v in sorted(per_class.items())},
        "llm_turns": src.count("llm"), "fallback_turns": src.count("fallback"), "rules_turns": src.count("rules"),
    }


CORPUS_ROWS = [("Passed (all checks) (%)", "passed"), ("Task completion (%)", "completed"),
               ("Correct outstanding (%)", "correct_outstanding"),
               ("Verbatim repetition rate (% of agent lines)", "repetition_rate"),
               ("Avg worker turns (completed cases)", "avg_turns"), ("Re-asks per slot", "reasks_per_slot"),
               ("Context acknowledged (% of context turns)", "context_ack"),
               ("Irritation proxy (re-asks + unresolved conflicts per completed case)", "irritation"),
               ("Same, over all cases (unfinished ones included)", "irritation_all")]


def corpus_table(summaries):
    out = ["| Metric | " + " | ".join(s["backend"] for s in summaries) + " |", "|---" * (len(summaries) + 1) + "|"]
    for label, key in CORPUS_ROWS:
        out.append(f"| {label} | " + " | ".join(str(s[key]) for s in summaries) + " |")
    out.append("| Context turns measured | " + " | ".join(str(s["context_turns"]) for s in summaries) + " |")
    out.append("| Turns: LLM / fallback / rules | " + " | ".join(
        f"{s['llm_turns']} / {s['fallback_turns']} / {s['rules_turns']}" for s in summaries) + " |")
    out += ["", "| Class | " + " | ".join(s["backend"] for s in summaries) + " |",
            "|---" * (len(summaries) + 1) + "|"]
    for k in summaries[0]["per_class"]:
        out.append(f"| {k} | " + " | ".join(s["per_class"][k] for s in summaries) + " |")
    return "\n".join(out)


def a1_row(by_backend):
    """The named proof row and both transcripts side by side."""
    names = list(by_backend)
    verdict = ", ".join(f"{b} {'PASS' if by_backend[b]['passed'] else 'FAIL'}" for b in names)
    out = [f"A1 5-6 months → 130 days → ₹700: {verdict}", "",
           "| Worker | " + " | ".join(names) + " |", "|---" * (len(names) + 1) + "|"]
    trs = [by_backend[b]["transcript"] for b in names]
    out.append("| (opening) | " + " | ".join(t[0]["agent"] for t in trs) + " |")
    for i in range(1, max(len(t) for t in trs)):
        worker = next((t[i]["worker"] for t in trs if i < len(t)), "")
        cells = []
        for t in trs:
            if i < len(t):
                cell = f"[{t[i]['worker']}] " if t[i]["worker"] != worker else ""
                cell += t[i]["agent"] + (f" `{t[i]['formula']}`" if t[i].get("formula") else "")
            else:
                cell = ""
            cells.append(cell.replace("|", "/"))
        out.append(f"| {worker} | " + " | ".join(cells) + " |")
    out.append("| **outstanding** | " + " | ".join(str(by_backend[b]["outstanding"]) for b in names) + " |")
    return "\n".join(out)


def evaluate_corpus(path, backends):
    cases = json.load(open(path, encoding="utf-8"))
    summaries, a1 = [], {}
    for b in backends:
        t0 = time.time()
        workers = 6 if b.endswith("-llm") else 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(lambda c: run_corpus_case(b, c), cases))
        summary = summarise_corpus(b, results)
        summary["seconds"] = round(time.time() - t0, 1)
        summaries.append(summary)
        os.makedirs(OUT_DIR, exist_ok=True)
        stem = os.path.splitext(os.path.basename(path))[0].replace("test_corpus", "corpus")
        with open(os.path.join(OUT_DIR, f"{stem}_{b}.json"), "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=1)
        fails = [r["id"] for r in results if not r["passed"]]
        hard = [r["id"] for r in results if r["hard"] and not r["passed"]]
        print(f"{b}: {len(cases)} cases in {summary['seconds']}s; failed {len(fails)}: {', '.join(fails) or 'none'}"
              + (f"; HARD FAIL: {', '.join(hard)}" if hard else ""))
        a1[b] = next((r for r in results if r["id"] == "A1"), None)
    print()
    print(corpus_table(summaries))
    if all(a1.values()):
        print()
        print(a1_row(a1))
    return summaries


if __name__ == "__main__" and "--corpus" in sys.argv:
    args = sys.argv[1:]
    i = args.index("--corpus")
    path = args[i + 1]
    backends = [a for j, a in enumerate(args) if j not in (i, i + 1)] or ["v3-before", "v4"]
    evaluate_corpus(os.path.join(ROOT, path) if not os.path.isabs(path) else path, backends)
    sys.exit(0)


if __name__ == "__main__":
    versions = sys.argv[1:] or ["v1", "v2", "v3-fallback"]
    if versions == ["all"]:
        versions = ["v1", "v2", "v2-llm", "v3-fallback", "v3"]
    cases = json.load(open(os.path.join(ROOT, "test_cases.json"), encoding="utf-8"))
    summaries = []
    for v in versions:
        summary, results = evaluate(v, cases)
        summaries.append(summary)
        fails = [r["id"] for r in results if not r["math_ok"]]
        print(f"{v}: {len(cases)} cases in {summary['seconds']}s; wrong or no result: {', '.join(fails) or 'none'}")
    print()
    print(table(summaries))
