"""Phase 16 in the conversation: observations -> derive -> confirm, on both paths."""
import conversation as c
import observe

A1 = ["meri pagar badhao.", "kuch 5-6 mahine", "maine kareeb har hafte ke paanch din",
      "Hafte mein 7 din mein se 5 din kaam kiye. 5 din"]


def started():
    s = c.new_session()
    c.opening(s)
    return s


def decided(text="Achha.", observations=None, action="ask_slot", extracted=None):
    return {"action": action, "target_slot": None, "agent_text": text, "agent_text_hi": text,
            "extracted": extracted or [], "context_delta": None, "intent": "other",
            "observations": observations or []}


def test_a1_rules_path_derives_130_and_moves_to_rate():
    s = started()
    out = [c.step(s, t, c.local_extract) for t in A1]
    assert "130 din" in out[2]["agent_text"] and out[2]["action"] == "confirm_derived"
    assert "5-6 mahine, hafte mein 5 din" in out[2]["agent_text"]
    assert out[3]["state"] == c.ASK_RATE and s["facts"]["days"] == 130
    texts = [r["agent_text"] for r in out]
    assert len(set(texts)) == len(texts)                      # no line twice
    assert sum("kitne din" in t.lower() for t in texts) <= 1   # never "total kitne din?" again and again


def test_a1_policy_path_with_llm_observations():
    s = started()
    c.step_policy(s, A1[0], decided("Samajh gaya. Kitne din kaam kiya?",
                                    [{"type": "context", "text": "raise", "category": "wage_raise"}]))
    r = c.step_policy(s, A1[1], decided("Theek hai.", [{"type": "period", "value": "5-6", "unit": "month",
                                                       "range": [5, 6]}], action="confirm_derived"))
    assert "156" in r["agent_text"] and "26" in r["agent_text"]          # the assumption is said
    r = c.step_policy(s, A1[2], decided("Achha.", [{"type": "frequency", "days_per_week": 5}], "confirm_derived"))
    assert "130 din" in r["agent_text"] and r["derivation"]["formula"].endswith("≈ 130")
    r = c.step_policy(s, "haan", decided("Theek hai.", [], "ask_slot"))
    assert s["facts"]["days"] == 130 and r["state"] == c.ASK_RATE


def test_llm_observation_with_a_number_never_said_is_dropped():
    s = started()
    s["state"] = c.ASK_DAYS
    r = c.step_policy(s, "kuch mahine", decided("Achha.", [{"type": "period", "value": 6, "unit": "month"}]))
    assert "156" not in r["agent_text"] and "days" not in s["facts"]


def test_monthly_rate_is_confirmed_before_use():
    s = started()
    s["state"], s["facts"] = c.ASK_RATE, {"days": 20}
    r = c.step(s, "mahine ke 15000 tay the", c.local_extract)
    assert "577" in r["agent_text"] and "rate" not in s["facts"]
    c.step(s, "haan", c.local_extract)
    assert s["facts"]["rate"] == 577


def test_rate_range_is_asked_once():
    s = started()
    s["state"], s["facts"] = c.ASK_RATE, {"days": 6}
    r = c.step(s, "600-700 roz", c.local_extract)
    assert "600 ya 700" in r["agent_text"] and r["clarify"] == "range"
    r = c.step(s, "700", c.local_extract)
    assert s["facts"]["rate"] == 700


def test_frequency_contradiction_is_asked_not_overwritten():
    s = started()
    s["state"] = c.ASK_DAYS
    c.step(s, "teen hafte", c.local_extract)
    c.step(s, "hafte mein 5 din", c.local_extract)        # -> 15 days, waiting for a yes
    c.step(s, "haan", c.local_extract)
    s["state"] = c.ASK_DAYS
    s["facts"].pop("days")
    r = c.step(s, "nahi roz kaam karta tha", c.local_extract)   # "nahi" = a correction: replaces, no question
    assert r.get("clarify") != "conflict"


def test_context_gets_one_acknowledgement_line():
    s = started()
    s["state"] = c.ASK_DAYS
    r = c.step(s, "tum kaun ho", c.local_extract)
    assert r["agent_text"].startswith("Main PagarSaathi, aapki pagar ka hisaab karne ke liye.")
    r = c.step(s, "thekedar dhamki deta hai", c.local_extract)
    assert r["agent_text"].startswith("Dara mat")


def test_near_repeat_is_replaced_with_a_new_angle():
    s = started()
    lines = [c.step(s, w, c.local_extract)["agent_text"] for w in ("hello", "kuch", "kuch", "kuch")]
    for a, b in zip(lines, lines[1:]):
        assert c._similar(a, b) <= 0.8


def test_deduction_and_bonus_reach_the_maths():
    s = started()
    for w in ["6 din, 700 roz", "khane ke 200 kate", "bonus 1000 bola tha", "advance nahi", "3000 mile", "haan"]:
        c.step(s, w, c.local_extract)
    assert s["case"]["expected"] == 6 * 700 + 1000 - 200 and s["case"]["outstanding"] == 2000


def test_observe_does_not_read_tenure_or_last_week_as_numbers():
    assert observe.extract("Teen saal se unke saath hoon, pichhle hafte bimar bhi tha.") == \
        [{"type": "context", "category": "health", "text": "bimar"}]
    obs = observe.extract("pichhle hafte hospital tha, 6 din kaam kiya")
    assert {"type": "explicit_days", "value": 6} in obs and not any(o["type"] == "frequency" for o in obs)


# ---------- found by the corpus (test_corpus.json), first run ----------

def _play(lines, state=None):
    s = started()
    out = [c.step(s, t, c.local_extract) for t in lines]
    return s, out


def test_number_for_another_slot_while_a_derived_one_waits_is_kept():   # F15, A5
    s, out = _play(["mahine ke 15000", "20 din"])
    assert s["facts"] == {"rate": 577, "days": 20}


def test_corrected_period_is_proposed_not_rephrased_away():             # A5
    s, out = _play(["paise nahi diye", "pichhle mahine se", "nahi, ek mahina"])
    assert "26 din" in out[-1]["agent_text"] and out[-1]["action"] == "confirm_derived"


def test_unitless_corrections_read_against_stored_numbers():            # F1, F2, F7
    s, _ = _play(["6 din", "arre 6 nahi 5"])
    assert s["facts"]["days"] == 5
    s, _ = _play(["6 din", "700 roz", "pehle 700 bola tha, 650 sahi hai"])
    assert s["facts"]["rate"] == 650 and "advance" not in s["facts"]
    s, _ = _play(["6 din", "700", "advance 500", "nahi advance nahi tha"])
    assert s["facts"]["advance"] == 0


def test_second_different_day_count_is_asked_not_overwritten():         # F4
    s, out = _play(["8 din", "5 din"])
    assert out[-1]["clarify"] == "conflict" and "kaunsa" in out[-1]["agent_text"] and s["facts"]["days"] == 8
    c.step(s, "5", c.local_extract)
    assert s["facts"]["days"] == 5 and "rate" not in s["facts"]


def test_correction_at_the_readback_fixes_one_number():                  # F3
    s, out = _play(["6 din", "700 roz", "nahi", "3000", "nahi, din 5 the"])
    assert s["facts"]["days"] == 5 and s["state"] == c.CONFIRM and "rate" in s["facts"]


def test_advance_named_before_mila_is_not_also_a_payment():             # D3
    s, _ = _play(["8 din", "500 roz", "advance 1000 mila tha"])
    assert s["facts"]["advance"] == 1000 and "payments" not in s["facts"]


def test_trip_unit_and_english_per_day():                                # B8, G4
    assert observe.extract("ek trip ke 150", {"asking": "rate"}) == [
        {"type": "rate", "value": 150, "per": "trip", "range": None}]
    assert observe.extract("seven hundred per day")[0]["type"] == "rate"


def test_llm_acknowledgement_is_not_doubled():                          # live A1, first turn
    s = started()
    llm = ("Aapki baat samajh mein aayi, aapki mazdoori badhane ki ichha hai. "
           "Abhi tak kitne din kaam kiya hai jiski payment baaki hai?")
    r = c.step_policy(s, "meri pagar badhao.", decided(llm, [{"type": "context", "text": "pagar badhao",
                                                              "category": "wage_raise"}], "acknowledge_context"))
    assert r["agent_text"] == ("Pagar badhwane se pehle, jo baaki hai uska hisaab pakka karte hain. "
                               "Abhi tak kitne din kaam kiya hai jiski payment baaki hai?")


def test_llm_reply_with_its_own_marker_is_left_alone():
    s = started()
    r = c.step_policy(s, "tum kaun ho", decided("Main PagarSaathi, aapki pagar ka hisaab karne ke liye. Kitne din?",
                                                [{"type": "context", "text": "tum kaun", "category": "question_identity"}],
                                                "acknowledge_context"))
    assert r["agent_text"].count("PagarSaathi") == 1


def test_llm_misread_amount_falls_back_to_python_reading():             # live A1, "nabbe hazaar teen sau mile"
    for wrong in ([90000, 300], 90000, 9300):
        s = started()
        s["state"], s["facts"] = c.ASK_PAYMENTS, {"days": 130, "rate": 700, "advance": 0}
        c.step_policy(s, "nabbe hazaar teen sau mile",
                      decided("Theek hai.", extracted=[{"slot": "payments", "value": wrong, "confidence": "high"}]))
        assert s["facts"]["payments"] == 90300 and s["state"] == c.CONFIRM


def test_llm_question_asking_two_numbers_becomes_one():                 # live A1, first turn
    s = started()
    llm = ("Pagar badhwane se pehle, jo baaki hai uska hisaab pakka karte hain. "
           "Abhi ke liye, aapne kitne din kaam kiya aur roz kitna milta tha, bataiye?")
    r = c.step_policy(s, "meri pagar badhao.", decided(llm, [{"type": "context", "text": "pagar badhao",
                                                              "category": "wage_raise"}], "acknowledge_context"))
    assert r["agent_text"] == ("Pagar badhwane se pehle, jo baaki hai uska hisaab pakka karte hain. "
                               "Aapne kitne din kaam kiya?")
    assert c._asks_many(r["agent_text"]) == ["days"]


def test_one_number_questions_from_the_llm_are_kept():
    s = started()
    llm = "Achha. Abhi tak kitne din kaam kiya hai jiski payment baaki hai?"
    r = c.step_policy(s, "paise nahi mile", decided(llm))
    assert r["agent_text"] == llm


def test_private_loan_is_not_the_advance():                             # held-out X12
    s, out = _play(["10 din", "500 roz", "bhai se 1000 udhaar liya, woh alag hai"])
    assert s["facts"]["advance"] == 0 and s["state"] == c.ASK_PAYMENTS
    assert out[-1]["agent_text"].startswith("Woh alag udhaar hai")


def test_private_loan_mid_way_stores_nothing():
    s, out = _play(["10 din", "bhai se 1000 udhaar liya, woh alag hai"])
    assert "rate" not in s["facts"] and s["state"] == c.ASK_RATE
    assert out[-1]["agent_text"].endswith("Roz ki mazdoori kitni tay hui thi?")
