"""Evaluate PagarSaathi's conversation logic on the held-out test set (test_cases.json).

    python3 evaluate.py v1 v2 v3-fallback v3        # v3 needs OPENAI_API_KEY or OPENROUTER_API_KEY
    python3 evaluate.py all

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
