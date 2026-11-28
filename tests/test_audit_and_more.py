"""Phases 10-13: the audit layer (hash, sent_at, follow-up, escalation, share, delete), the three
choices, contradictions, languages and the optional overtime/deductions. No network: the Sarvam
key is removed, and the LLM path uses a fake policy."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest

import agent_llm
import audit
import conversation as c
import language
import sarvam_tts
from wage_math import calculate_wages

DEMO = ["Thekedar ne poore paise nahi diye. Teen saal se unke saath hoon, pichhle hafte bimar bhi tha.",
        "Chhe din kaam kiya, saat sau roz, paanch sau advance mila tha.", "Teen hazaar mile.", "Haan."]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    import database
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "t.db"))
    import app as app_module
    monkeypatch.setattr(app_module, "env_key", lambda name: None)
    monkeypatch.setattr(agent_llm, "enabled", lambda: False)
    database.init_db()
    return app_module.app.test_client(), database


def turn(cl, **kw):
    r = cl.post("/turn", json=kw)
    return r.get_json()


def finished_case(cl, last="Haan."):
    sid = turn(cl, mode="scripted")["session_id"]
    for w in DEMO[:-1] + [last]:
        r = turn(cl, session_id=sid, text=w, mode="scripted")
    return sid, r


# ---------- Phase 10: audit layer ----------

def test_hash_is_stored_and_verifies(client):
    cl, db = client
    sid, r = finished_case(cl)
    assert r["state"] == c.ASK_SEND and r["case_data"]["outstanding"] == 700
    row = db.get_case(sid)
    assert len(row["case_hash"]) == 64 and r["case_hash_short"] == row["case_hash"][:12]
    assert audit.verify(row["case_json"], row["case_hash"])
    record = json.loads(row["case_json"])
    assert set(record) >= {"session_id", "slots", "expected", "received", "outstanding", "transcript", "language",
                           "created_at", "policy_source", "node_path"}
    assert all(t["at"] for t in record["transcript"])
    # any edit is detectable
    tampered = row["case_json"].replace('"outstanding":700', '"outstanding":7000')
    assert tampered != row["case_json"] and not audit.verify(tampered, row["case_hash"])


def test_hash_is_never_overwritten(client):
    cl, db = client
    sid, r = finished_case(cl)
    first = db.get_case(sid)["case_hash"]
    turn(cl, session_id=sid, text="sirf save karo", mode="scripted")
    assert db.get_case(sid)["case_hash"] == first


def test_three_choices_are_offered_and_parsed(client):
    cl, db = client
    sid, r = finished_case(cl)
    assert "message bhejun, escalate karun, ya sirf case save karun" in r["agent_text"]
    assert c.parse_choice("message bhej do") == "send"
    assert c.parse_choice("escalate karo") == "escalate"
    assert c.parse_choice("sirf case save karo") == "save"
    r = turn(cl, session_id=sid, text="sirf save kar do", mode="scripted")
    assert r["choice"] == "save" and r["state"] == c.DONE and "save ho gaya" in r["agent_text"]


def test_voice_escalate_builds_draft_with_hash(client):
    cl, db = client
    sid, _ = finished_case(cl)
    r = turn(cl, session_id=sid, text="escalate karo", mode="scripted")
    row = db.get_case(sid)
    assert r["choice"] == "escalate" and row["case_hash"] in row["escalation_draft"]
    assert "SAMADHAN" in row["escalation_draft"] and "1800 1800 999" in row["escalation_draft"]


def test_mark_sent_stores_time_and_state_shows_it(client):
    cl, db = client
    sid, _ = finished_case(cl)
    r = turn(cl, session_id=sid, text="Haan.", mode="scripted")      # ASK_SEND -> SHOW_PREVIEW
    assert f"Case ID (sha256): {db.get_case(sid)['case_hash'][:12]}" in r["case_data"]["payment_request"]
    r = cl.post("/mark-sent", json={"session_id": sid}).get_json()
    assert r["sent_at"] and r["state"] == c.DONE
    s = cl.get(f"/state?session_id={sid}").get_json()
    assert s["sent_at"] == r["sent_at"] and s["hash_verified"] and s["case"]["outstanding"] == 700
    assert s["node_path"][-2:] == [c.SHOW_PREVIEW, c.DONE]


def test_followup_after_24h_and_commitment(client):
    cl, db = client
    sid, _ = finished_case(cl)
    db.mark_sent(sid, (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds"))
    assert turn(cl, prior_session=sid)["state"] == c.START          # too recent: normal greeting
    db.mark_sent(sid, (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(timespec="seconds"))
    r = turn(cl, prior_session=sid)
    assert r["state"] == c.FOLLOWUP and "Pichhle case ke baare mein" in r["agent_text"]
    r = turn(cl, session_id=r["session_id"], text="Manager ne bola kal dega")
    row = db.get_case(sid)
    assert row["followup_log"][0]["text"] == "Manager ne bola kal dega"
    assert row["commitment_date"] == (date.today() + timedelta(days=1)).isoformat()
    assert r["prior_case"]["commitment_date"] == row["commitment_date"]


def test_escalate_button_and_share_page(client):
    cl, db = client
    sid, _ = finished_case(cl)
    d = cl.post("/escalate", json={"session_id": sid}).get_json()
    assert db.get_case(sid)["case_hash"] in d["escalation_draft"]
    page = cl.get(f"/case/{sid}/share")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert db.get_case(sid)["case_hash"] in body and "BAATCHEET" in body and "tel:18001800999" in body


def test_delete_needs_spoken_yes_and_removes_row(client):
    cl, db = client
    sid, _ = finished_case(cl)
    r = turn(cl, session_id=sid, text="mera case delete karo")
    assert r["state"] == c.CONFIRM_DELETE and db.get_case(sid)
    r = turn(cl, session_id=sid, text="nahi")
    assert db.get_case(sid) and not r["deleted"]
    turn(cl, session_id=sid, text="mera case delete karo")
    r = turn(cl, session_id=sid, text="haan")
    assert r["deleted"] and db.get_case(sid) is None
    assert cl.get(f"/state?session_id={sid}").get_json().get("case_hash") is None


# ---------- Phase 11: contradictions and languages ----------

def decided(text="", extracted=None, action="ask_slot", target="none"):
    return agent_llm.normalise({"action": action, "target_slot": target, "agent_text": text, "agent_text_hi": text,
                                "extracted": extracted or [], "context_delta": None, "intent": "other"})


def x(slot, value):
    return {"slot": slot, "value": value, "confidence": "high"}


def test_contradiction_is_asked_and_both_values_kept():
    s = c.new_session()
    c.opening(s)
    c.step_policy(s, "6 din kaam kiya", decided("Achha. Roz kitna?", [x("days", 6)], target="rate"))
    r = c.step_policy(s, "5 din kaam kiya, 700 roz", decided("Theek hai. Advance?", [x("days", 5), x("rate", 700)]))
    assert r["action"] == "python_conflict" and "pehle chhe din kaha, ab paanch din" in r["agent_text"]
    assert s["pending_conflict"] == {"slot": "days", "old": 6, "new": 5}
    r = c.step_policy(s, "pehla wala sahi hai", decided("Theek hai. Advance mila tha?", [], target="advance"))
    assert s["facts"]["days"] == 6 and s["turns"][-1]["conflict"]["old"] == 6 and s["turns"][-1]["conflict"]["new"] == 5


def test_explicit_correction_is_not_questioned():
    s = c.new_session()
    c.opening(s)
    c.step_policy(s, "6 din", decided("Roz kitna?", [x("days", 6)]))
    r = c.step_policy(s, "nahi nahi, 5 din", decided("Theek, 5 din. Roz kitna?", [x("days", 5)]))
    assert r.get("action") != "python_conflict" and s["facts"]["days"] == 5


@pytest.mark.parametrize("text,code", [
    ("मी सहा दिवस काम केलं, मला पैसे मिळाले नाही", "mr"),
    ("Mala saha divas kaam kela, paise milale nahi", "mr"),
    ("हम छह दिन काम कइनी, पइसा ना मिलल बानी", "bho"),
    ("আমি ছয় দিন কাজ করেছি", "bn"),
    ("நான் ஆறு நாள் வேலை செய்தேன்", "ta"),
    ("నేను ఆరు రోజులు పని చేశాను", "te"),
    ("I worked 6 days and got only 3000 so far", "en-mix"),
    ("Chhe din kaam kiya, paise nahi mile", "hi"),
    ("theek", "hi"),
])
def test_language_detection(text, code):
    assert language.choose(text) == code


def test_marathi_switches_voice_and_lines(client):
    cl, db = client
    sid = turn(cl)["session_id"]
    r = turn(cl, session_id=sid, text="मला पूर्ण पैसे मिळाले नाहीत, मी सहा दिवस काम केलं आहे")
    assert r["language"] == "mr" and r["voice_lang"] == "mr"
    assert "दिवस" in r["agent_text"] or "मजुरी" in r["agent_text"]
    assert sarvam_tts.voice("mr") == ("mr-IN", "nilesh_mr_conversation")
    assert sarvam_tts.audio_name("x", "mr") != sarvam_tts.audio_name("x", "hi")


def test_hindi_stays_hindi(client):
    cl, db = client
    sid = turn(cl)["session_id"]
    r = turn(cl, session_id=sid, text="Thekedar ne paise nahi diye")
    assert r["language"] == "hi" and r["voice_lang"] == "hi" and r["agent_text"] == "Aapne kitne din kaam kiya?"


def test_toggle_language_is_respected(client):
    cl, db = client
    r = turn(cl, language="mr")
    assert r["language"] == "mr" and r["agent_text"].startswith("नमस्कार")


# ---------- Phase 12: optional overtime and deductions ----------

def test_overtime_and_deductions_math():
    case = calculate_wages(6, 700, 500, 3000, overtime_hours=10, overtime_rate=100, deductions=200)
    assert case["expected"] == 6 * 700 + 10 * 100 - 200 and case["outstanding"] == 1500


def test_extras_after_readback_then_readback_again():
    s = c.new_session()
    c.opening(s)
    for w in DEMO[:-1]:
        c.step(s, w, c.local_extract)
    assert s["state"] == c.CONFIRM
    r = c.step(s, "haan, aur 10 ghante overtime tha, 100 rupaye ghanta, 200 katauti", c.local_extract)
    assert r["state"] == c.CONFIRM and "das ghante overtime" in r["agent_text"] and "do sau katauti" in r["agent_text"]
    r = c.step(s, "haan", c.local_extract)
    assert r["case"]["expected"] == 5000 and r["case"]["outstanding"] == 1500


def test_four_slot_path_is_unchanged_by_extras():
    s = c.new_session()
    c.opening(s)
    for w in DEMO:
        r = c.step(s, w, c.local_extract)
    assert r["case"]["outstanding"] == 700 and "overtime" not in r["case"]


def test_commitment_parsing():
    today = date(2026, 11, 28)
    assert audit.commitment_from("manager ne bola kal dega", today) == "2026-11-29"
    assert audit.commitment_from("parson denge", today) == "2026-11-30"
    assert audit.commitment_from("agle hafte dega", today) == "2026-12-05"
    assert audit.commitment_from("kuch nahi bola", today) is None


def test_rules_take_a_tagged_correction_of_a_known_number():
    s = c.new_session()
    c.opening(s)
    for w in ["paise nahi mile", "6 din", "700", "1000 advance"]:
        c.step(s, w, c.local_extract)
    r = c.step(s, "sorry, advance 500 tha", c.local_extract)
    assert s["facts"]["advance"] == 500 and "payments" not in s["facts"] and r["state"] == c.ASK_PAYMENTS
