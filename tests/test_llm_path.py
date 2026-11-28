"""The LLM conversation path, with a fake LLM (no network, no keys). The LLM only hears facts and
writes a short reply; Python still validates, adds, reads back and calculates."""
import agent_llm
import conversation as c
from hinglish_numbers import parse_amounts


def heard(facts=None, parts=None, intent="other", say="", ask=""):
    return agent_llm.normalise({"facts": facts or {}, "parts": parts or {}, "intent": intent,
                                "say": say, "say_hi": say, "ask": ask, "ask_hi": ask})


def started():
    s = c.new_session()
    c.opening(s)
    return s


def test_side_question_gets_an_answer_then_the_question():
    s = started()
    r = c.step_llm(s, "Kya aap meri madad karoge?", heard(say="Haan, main madad karunga."))
    assert r["state"] == c.ASK_DAYS
    assert r["agent_text"].startswith("Haan, main madad karunga. ")
    assert "kitne din" in r["agent_text"]


def test_several_facts_in_one_sentence():
    s = started()
    c.step_llm(s, "hello", heard())
    r = c.step_llm(s, "6 din, 700 roz, 500 advance", heard({"days": 6, "rate": 700, "advance": 500}))
    assert r["state"] == c.ASK_PAYMENTS
    assert r["facts"] == {"days": 6, "rate": 700, "advance": 500}


def test_full_conversation_reaches_700_and_preview():
    s = started()
    c.step_llm(s, "paise nahi mile", heard(say="Chinta mat kijiye."))
    c.step_llm(s, "6 din", heard({"days": 6}))
    c.step_llm(s, "700", heard({"rate": 700}))
    c.step_llm(s, "500", heard({"advance": 500}))
    r = c.step_llm(s, "Three thousand so far", heard({"payments": 3000}))
    assert r["state"] == c.CONFIRM and "Sahi hai?" in r["agent_text"]
    r = c.step_llm(s, "haan", heard(intent="yes"))
    assert r["case"]["outstanding"] == 700 and r["state"] == c.ASK_SEND
    r = c.step_llm(s, "bhej do", heard(intent="yes"))
    assert r["state"] == c.SHOW_PREVIEW and "Baaki: ₹700" in r["case"]["payment_request"]


def test_python_adds_multiple_payments():
    s = started()
    s["state"], s["facts"] = c.ASK_PAYMENTS, {"days": 6, "rate": 700, "advance": 0}
    r = c.step_llm(s, "do hazaar aur ek hazaar", heard(parts={"payments": [2000, 1000]}))
    assert s["facts"]["payments"] == 3000 and r["state"] == c.CONFIRM


def test_correction_at_confirm_reads_back_again_and_haan_does_not_loop():
    s = started()
    s["state"], s["facts"] = c.CONFIRM, {"days": 6, "rate": 700, "advance": 0, "payments": 3000}
    r = c.step_llm(s, "nahi, rate 800 tha", heard({"rate": 800}, intent="no"))
    assert r["state"] == c.CONFIRM and "aath sau roz" in r["agent_text"]
    # the LLM repeats the known rate with a plain "haan": that is a yes, not another correction
    r = c.step_llm(s, "haan", heard({"rate": 800}, intent="yes"))
    assert r["state"] == c.ASK_SEND and r["case"]["outstanding"] == 1800


def test_confirm_is_still_mandatory():
    s = started()
    s["state"], s["facts"] = c.CONFIRM, {"days": 6, "rate": 700, "advance": 500, "payments": 3000}
    r = c.step_llm(s, "hmm", heard())
    assert r["state"] == c.CONFIRM and s["case"] is None


def test_bare_haan_is_not_zero():
    s = started()
    s["state"], s["facts"] = c.ASK_ADVANCE, {"days": 6, "rate": 700}
    r = c.step_llm(s, "haan", heard({"advance": 0}))
    assert "advance" not in s["facts"] and r["reasked"]


def test_clarifying_question_replaces_the_stock_one():
    s = started()
    c.step_llm(s, "hello", heard())
    r = c.step_llm(s, "poora hafta", heard(ask="Poore hafte mein kitne din, chhe ya saat?"))
    assert r["agent_text"].endswith("chhe ya saat?") and r["state"] == c.ASK_DAYS


def test_reply_never_asks_its_own_question():
    out = heard(say="Achha. Aapne kitne din kaam kiya? Chinta mat kijiye.")
    assert out["say"] == "Achha. Chinta mat kijiye."


def test_out_of_range_values_are_ignored():
    s = started()
    s["state"] = c.ASK_DAYS
    r = c.step_llm(s, "500 din", heard({"days": 500}))
    assert "days" not in s["facts"] and r["state"] == c.ASK_DAYS


def test_normalise_rejects_junk():
    assert agent_llm.normalise("nope") is None
    out = agent_llm.normalise({"facts": {"days": "six", "rate": True, "advance": -5, "payments": 3000.0}})
    assert out["facts"] == {"days": None, "rate": None, "advance": None, "payments": 3000}


def test_app_falls_back_to_rules_when_llm_fails(monkeypatch):
    import app as A
    monkeypatch.setattr(agent_llm, "enabled", lambda: True)
    monkeypatch.setattr(agent_llm, "understand", lambda *a, **k: None)
    monkeypatch.setattr(A, "agent_audio_url", lambda *a: None)
    client = A.app.test_client()
    sid = client.post("/turn", json={}).get_json()["session_id"]
    client.post("/turn", json={"session_id": sid, "text": "paise nahi mile"})
    r = client.post("/turn", json={"session_id": sid, "text": "chhe din"}).get_json()
    assert r["state"] == c.ASK_RATE and r["facts"] == {"days": 6}


def test_so_far_is_not_sau():
    assert parse_amounts("Three thousand so far") == [3000]
    assert parse_amounts("700 so far") == [700]
    assert parse_amounts("saat so") == [700]
