"""The LLM dialogue policy path, with a fake policy (no network, no keys). The policy chooses the
next move and the line; Python keeps the frame, accepts only numbers the worker said, breaks loops,
forces the read-back and does the maths."""
import agent_llm
import conversation as c
from hinglish_numbers import parse_amounts


def decided(action="ask_slot", text="", target="none", extracted=None, context=None, intent="other"):
    return agent_llm.normalise({"action": action, "target_slot": target, "agent_text": text,
                                "agent_text_hi": text, "extracted": extracted or [],
                                "context_delta": context, "intent": intent})


def x(slot, value, confidence="high"):
    return {"slot": slot, "value": value, "confidence": confidence}


def started():
    s = c.new_session()
    c.opening(s)
    return s


def test_policy_line_is_said_and_frame_moves():
    s = started()
    r = c.step_policy(s, "6 din, 700 roz", decided(text="Achha, chhe din aur saat sau roz. Koi advance mila tha?",
                                                    target="advance", extracted=[x("days", 6), x("rate", 700)]))
    assert r["agent_text"].startswith("Achha, chhe din") and r["state"] == c.ASK_ADVANCE
    assert s["facts"] == {"days": 6, "rate": 700} and s["turn_count"] == 1


def test_hospital_context_is_acknowledged_and_kept():
    s = started()
    s["state"] = c.ASK_DAYS
    r = c.step_policy(s, "main 4 din hospital mein tha", decided(
        "acknowledge_context", "Yeh sunkar dukh hua. Hospital ke 4 din chhod kar, kitne din kaam kiya?",
        target="days", context="Was in hospital for 4 days"))
    assert "dukh" in r["agent_text"] and "days" not in s["facts"]
    assert s["context_notes"] == ["Was in hospital for 4 days"] and r["state"] == c.ASK_DAYS


def test_loan_is_not_advance_until_worker_says_it_was_cut():
    s = started()
    s["state"], s["facts"] = c.ASK_ADVANCE, {"days": 6, "rate": 700}
    r = c.step_policy(s, "manager se 2000 ka loan liya tha", decided(
        "clarify", "Samajh gaya. Kya woh 2000 aapki mazdoori se kaata gaya?", target="advance",
        context="Took a 2000 loan from the manager"))
    assert "advance" not in s["facts"] and "2000" in r["agent_text"]
    r = c.step_policy(s, "haan, 2000 kaat liye", decided(
        "ask_slot", "Theek hai, 2000 advance. Ab tak kitne paise mile?", target="payments",
        extracted=[x("advance", 2000)]))
    assert s["facts"]["advance"] == 2000 and r["state"] == c.ASK_PAYMENTS


def test_loan_amount_from_previous_message_counts_once_confirmed():
    s = started()
    s["state"], s["facts"] = c.ASK_ADVANCE, {"days": 6, "rate": 700}
    c.step_policy(s, "manager se 2000 ka loan liya tha", decided(
        "clarify", "Kya woh 2000 mazdoori se kaata gaya?", target="advance", context="Loan of 2000"))
    r = c.step_policy(s, "haan wo pagar mein se kaat liya", decided(
        "ask_slot", "Theek hai, 2000 advance mein ginenge. Ab tak kitne paise mile?", target="payments",
        extracted=[x("advance", 2000)]))
    assert s["facts"]["advance"] == 2000 and r["state"] == c.ASK_PAYMENTS and not r.get("guarded")


def test_unsure_value_is_kept_when_policy_moves_on_and_read_back_checks_it():
    s = started()
    s["state"], s["facts"] = c.ASK_RATE, {"days": 5}
    r = c.step_policy(s, "shayad 600", decided("ask_slot", "Theek hai, 600 roz. Koi advance mila tha?",
                                               target="advance", extracted=[x("rate", 600, "low")]))
    assert s["facts"]["rate"] == 600 and r["state"] == c.ASK_ADVANCE


def test_line_ending_in_bataiye_gets_no_second_question():
    s = started()
    s["state"], s["facts"] = c.ASK_PAYMENTS, {"days": 6, "rate": 700, "advance": 0}
    r = c.step_policy(s, "hmm", decided("rephrase", "Advance ke alawa kitne paise mile, wo bataiye."))
    assert r["agent_text"] == "Advance ke alawa kitne paise mile, wo bataiye."


def test_years_is_not_stored_as_days():
    s = started()
    s["state"] = c.ASK_DAYS
    # even if the model wrongly converts 3 saal into days, Python refuses: 1095 was never said
    r = c.step_policy(s, "maine 3 saal kaam kiya", decided("clarify", "Teen saal mein 1095 din hue.",
                                                         extracted=[x("days", 1095)]))
    assert "days" not in s["facts"] and r["guarded"] and "1095" not in r["agent_text"]


def test_number_not_said_by_worker_is_rejected():
    s = started()
    s["state"] = c.ASK_DAYS
    r = c.step_policy(s, "ek hafta", decided(text="Achha, saat din. Roz kitna milta tha?", extracted=[x("days", 7)]))
    assert "days" not in s["facts"] and r["agent_text"].startswith("Maaf kijiye")


def test_model_never_states_a_total():
    s = started()
    s["state"], s["facts"] = c.ASK_PAYMENTS, {"days": 6, "rate": 700, "advance": 500}
    r = c.step_policy(s, "pata nahi", decided(text="Aapke 4200 bante hain. Kitne mile?"))
    assert "4200" not in r["agent_text"] and r["guarded"]


def test_word_for_word_repeat_is_replaced():
    s = started()
    s["state"] = c.ASK_DAYS
    s["last_agent_text"] = "Aapne kitne din kaam kiya?"
    r = c.step_policy(s, "hmm", decided("rephrase", "Aapne kitne din kaam kiya?"))
    assert r["agent_text"] != "Aapne kitne din kaam kiya?"


def test_never_the_same_line_twice_in_a_row_when_stuck():
    s = started()
    s["state"] = c.ASK_DAYS
    said = []
    for _ in range(6):
        said.append(c.step_policy(s, "hmm", decided(text=s["last_agent_text"]))["agent_text"])
    assert all(a != b for a, b in zip(said, said[1:]))


def test_stalled_advance_is_assumed_zero_and_flagged():
    s = started()
    s["state"], s["facts"] = c.ASK_ADVANCE, {"days": 6, "rate": 700}
    for i in range(c.STALL_LIMIT):
        r = c.step_policy(s, "hmm", decided("rephrase", f"Advance ke baare mein bataiye, version {i}?"))
    assert s["facts"]["advance"] == 0 and r["parsed"]["assumed"] and "advance" in s["needs_assistance"]


def test_off_topic_answer_then_back_to_hisaab():
    s = started()
    s["state"] = c.ASK_RATE
    s["facts"] = {"days": 6}
    r = c.step_policy(s, "aap kaun ho?", decided("handle_off_topic", "Main PagarSaathi hoon, aapka hisaab nikalta hoon.",
                                                 target="rate"))
    assert r["agent_text"].endswith(c.STATES[c.ASK_RATE]["question_hi"][0]) and r["state"] == c.ASK_RATE


def test_policy_may_choose_which_open_number_next():
    s = started()
    s["state"] = c.ASK_DAYS
    r = c.step_policy(s, "3000 mile hain bas", decided(text="Achha, teen hazaar mile. Kitne din kaam kiya?",
                                                      target="days", extracted=[x("payments", 3000)]))
    assert s["facts"] == {"payments": 3000} and r["state"] == c.ASK_DAYS


def test_full_conversation_reaches_700_and_preview():
    s = started()
    c.step_policy(s, "paise nahi mile", decided("acknowledge_context", "Chinta mat kijiye. Kitne din kaam kiya?",
                                                target="days", context="Not paid in full"))
    c.step_policy(s, "6 din", decided(text="Achha. Roz kitna?", extracted=[x("days", 6)]))
    c.step_policy(s, "700", decided(text="Theek. Advance mila tha?", extracted=[x("rate", 700)]))
    c.step_policy(s, "500", decided(text="Achha. Ab tak kitne mile?", extracted=[x("advance", 500)]))
    r = c.step_policy(s, "Three thousand so far", decided("conclude", "Theek hai.", extracted=[x("payments", 3000)]))
    assert r["state"] == c.CONFIRM and "Sahi hai?" in r["agent_text"]
    r = c.step_policy(s, "haan", decided(intent="yes", text="Theek hai."))
    assert r["case"]["outstanding"] == 700 and r["state"] == c.ASK_SEND
    r = c.step_policy(s, "bhej do", decided(intent="yes", text="Theek hai."))
    assert r["state"] == c.SHOW_PREVIEW and "Baaki: ₹700" in r["case"]["payment_request"]


def test_conclude_too_early_still_asks_for_missing():
    s = started()
    s["state"], s["facts"] = c.ASK_RATE, {"days": 6}
    r = c.step_policy(s, "700", decided("conclude", "Bas, ho gaya.", extracted=[x("rate", 700)]))
    assert r["state"] == c.ASK_ADVANCE and s["case"] is None


def test_python_adds_multiple_payments():
    s = started()
    s["state"], s["facts"] = c.ASK_PAYMENTS, {"days": 6, "rate": 700, "advance": 0}
    r = c.step_policy(s, "do hazaar aur ek hazaar", decided("conclude", "Achha.", extracted=[x("payments", [2000, 1000])]))
    assert s["facts"]["payments"] == 3000 and r["state"] == c.CONFIRM


def test_correction_at_confirm_reads_back_again_and_haan_does_not_loop():
    s = started()
    s["state"], s["facts"] = c.CONFIRM, {"days": 6, "rate": 700, "advance": 0, "payments": 3000}
    r = c.step_policy(s, "nahi, rate 800 tha", decided(intent="no", text="Achha, 800.", extracted=[x("rate", 800)]))
    assert r["state"] == c.CONFIRM and "aath sau roz" in r["agent_text"]
    r = c.step_policy(s, "haan", decided(intent="yes", text="Theek."))
    assert r["state"] == c.ASK_SEND and r["case"]["outstanding"] == 1800


def test_bare_nahi_at_read_back_asks_what_is_wrong_without_guessing():
    s = started()
    s["state"], s["facts"] = c.CONFIRM, {"days": 6, "rate": 700, "advance": 0, "payments": 3000}
    r = c.step_policy(s, "nahi", decided(intent="no", text="To ab tak kitne paise mile?"))
    assert r["agent_text"] == c.WHAT_WRONG[0]


def test_slow_llm_is_cut_off_at_the_deadline(monkeypatch):
    import time
    monkeypatch.setattr(agent_llm, "TIMEOUT_S", 0.8)
    monkeypatch.setattr(agent_llm, "providers", lambda: [("https://a.example/x", "k", "m"), ("https://b.example/x", "k", "m")])
    monkeypatch.setattr(agent_llm, "_call", lambda *a: time.sleep(3))
    t0 = time.monotonic()
    assert agent_llm.decide(started(), "6 din") is None and time.monotonic() - t0 < 1.5


def test_confirm_is_still_mandatory():
    s = started()
    s["state"], s["facts"] = c.CONFIRM, {"days": 6, "rate": 700, "advance": 500, "payments": 3000}
    r = c.step_policy(s, "hmm", decided(text="Theek hai."))
    assert r["state"] == c.CONFIRM and s["case"] is None
    # the model says "yes" but the worker said "nahi": no maths
    r = c.step_policy(s, "nahi", decided(intent="yes", text="Theek hai."))
    assert s["case"] is None


def test_bare_haan_is_not_zero():
    s = started()
    s["state"], s["facts"] = c.ASK_ADVANCE, {"days": 6, "rate": 700}
    c.step_policy(s, "haan", decided(text="Kitna advance?", extracted=[x("advance", 0)]))
    assert "advance" not in s["facts"]


def test_low_confidence_is_unresolved_not_stored():
    s = started()
    s["state"] = c.ASK_DAYS
    c.step_policy(s, "teen", decided("clarify", "Teen din ya teen hafte?", extracted=[x("days", 3, "low")]))
    assert "days" not in s["facts"] and s["unresolved"] == ["days"]


def test_out_of_range_values_are_ignored():
    s = started()
    s["state"] = c.ASK_DAYS
    r = c.step_policy(s, "500 din", decided(extracted=[x("days", 500)], text="Achha."))
    assert "days" not in s["facts"] and r["state"] == c.ASK_DAYS


def test_normalise_rejects_junk():
    assert agent_llm.normalise("nope") is None
    out = agent_llm.normalise({"action": "dance", "extracted": [{"slot": "days", "value": "six"},
                                                                 {"slot": "rate", "value": True},
                                                                 {"slot": "payments", "value": 3000.0, "confidence": "high"}],
                               "context_delta": "null", "agent_text": "Achha."})
    assert out["action"] == "ask_slot" and out["context_delta"] is None
    assert out["extracted"] == [{"slot": "payments", "value": 3000, "confidence": "high"}]


def test_frame_sent_to_policy_has_notes_and_last_question():
    s = started()
    s["context_notes"] = ["Took a loan"]
    msg = agent_llm.build_user_message(s, "6 din")
    assert '"context_notes": ["Took a loan"]' in msg and "Namaste" in msg and '"missing": ["days"' in msg


def test_app_falls_back_to_rules_when_llm_fails(monkeypatch):
    import app as A
    monkeypatch.setattr(agent_llm, "enabled", lambda: True)
    monkeypatch.setattr(agent_llm, "decide", lambda *a, **k: None)
    monkeypatch.setattr(A, "agent_audio", lambda *a: (None, None))
    client = A.app.test_client()
    sid = client.post("/turn", json={}).get_json()["session_id"]
    client.post("/turn", json={"session_id": sid, "text": "paise nahi mile"})
    r = client.post("/turn", json={"session_id": sid, "text": "chhe din"}).get_json()
    assert r["state"] == c.ASK_RATE and r["facts"] == {"days": 6} and r["text_source"] == "rules"


def test_so_far_is_not_sau():
    assert parse_amounts("Three thousand so far") == [3000]
    assert parse_amounts("700 so far") == [700]
    assert parse_amounts("saat so") == [700]


def test_errors_are_hinglish_never_a_traceback(monkeypatch):
    import app as A
    client = A.app.test_client()
    assert "nahi mila" in client.get("/no-such-page").get_data(as_text=True)
    monkeypatch.setattr(agent_llm, "enabled", lambda: False)
    monkeypatch.setattr(c, "step", lambda *a, **k: 1 / 0)
    sid = client.post("/turn", json={}).get_json()["session_id"]
    r = client.post("/turn", json={"session_id": sid, "text": "6 din"})
    assert r.status_code == 500 and r.get_json() == {"error": A.ERRORS[500]}


def test_health_reports_pipeline():
    import app as A
    h = A.app.test_client().get("/health").get_json()
    assert h["status"] == "ok" and h["stt"] is False and h["mode"] in ("live", "keyless")
    assert set(h) >= {"llm", "voice", "stt", "mode", "missing", "key_set"}


# ---------- rules path (no key): off-script sentences get a real answer, never a loop ----------

def test_rules_years_and_week_are_clarified_not_stored():
    s = started()
    c.step(s, "paise nahi mile", c.local_extract)
    r = c.step(s, "maine 3 saal kaam kiya", c.local_extract)
    assert "days" not in s["facts"] and "Lamba saath" in r["agent_text"]
    r = c.step(s, "ek hafta", c.local_extract)
    assert "days" not in s["facts"] and "chhe ya saat" in r["agent_text"]
    r = c.step(s, "hafte mein 6 din", c.local_extract)
    assert s["facts"]["days"] == 6


def test_rules_hospital_and_loan_are_acknowledged():
    s = started()
    c.step(s, "paise nahi mile", c.local_extract)
    r = c.step(s, "4 din hospital mein tha", c.local_extract)
    assert "dukh" in r["agent_text"] and "days" not in s["facts"]
    s["state"], s["facts"] = c.ASK_ADVANCE, {"days": 6, "rate": 700}
    r = c.step(s, "manager se loan liya tha", c.local_extract)
    assert "advance mein ginenge" in r["agent_text"] and "Took a loan" in s["context_notes"]


def test_rules_never_repeat_the_same_line_twice_in_a_row():
    s = started()
    c.step(s, "hello", c.local_extract)
    said = [c.step(s, "kuch", c.local_extract)["agent_text"] for _ in range(6)]
    assert all(a != b for a, b in zip(said, said[1:]))
