"""derive.py: observations -> canonical numbers, with the formula and what still needs the worker."""
import derive as d


def obs(*items):
    return list(items)


PERIOD_5_6_MO = {"type": "period", "value": "5-6", "unit": "month", "range": [5, 6]}
FIVE_A_WEEK = {"type": "frequency", "days_per_week": 5}


def test_months_range_times_frequency_is_about_130():
    out = d.derive(obs(PERIOD_5_6_MO, FIVE_A_WEEK))
    assert abs(out["canonical"]["days"] - 130) <= 5
    entry = out["derivation"]["days"]
    assert entry["confirmed"] is False                     # derived: the worker must confirm it
    assert "4.33" in entry["formula"] and "5 d/wk" in entry["formula"] and "130" in entry["formula"]
    assert [a["kind"] for a in out["ambiguity"]] == ["range"]
    assert out["ambiguity"][0]["blocking"] is False        # the confirmation line names the range


def test_weeks_times_frequency():
    out = d.derive(obs({"type": "period", "value": 3, "unit": "week", "range": None},
                       {"type": "frequency", "days_per_week": 6}))
    assert out["canonical"]["days"] == 18
    assert out["derivation"]["days"]["formula"] == "3 wk × 6 d/wk = 18"


def test_monthly_rate_becomes_daily():
    out = d.derive(obs({"type": "rate", "value": 15000, "per": "month"}))
    assert out["canonical"]["rate"] == 577
    assert out["derivation"]["rate"]["confirmed"] is False
    assert "26" in out["derivation"]["rate"]["formula"]


def test_rate_range_is_an_ambiguity_not_a_value():
    out = d.derive(obs({"type": "rate", "value": "600-700", "per": "day", "range": [600, 700]}))
    assert "rate" not in out["canonical"]
    amb = out["ambiguity"][0]
    assert amb["slot"] == "rate" and amb["kind"] == "range" and amb["blocking"] and amb["options"] == [600, 700]


def test_explicit_days_win_and_need_no_confirmation():
    out = d.derive(obs(PERIOD_5_6_MO, FIVE_A_WEEK, {"type": "explicit_days", "value": 26}))
    assert out["canonical"]["days"] == 26
    assert out["derivation"]["days"]["source"] == "worker said"
    assert out["derivation"]["days"]["confirmed"] is True


def test_period_only_states_the_26_day_assumption():
    out = d.derive(obs({"type": "period", "value": 6, "unit": "month", "range": None}))
    assert out["canonical"]["days"] == 156
    assert "26 working days/month" in out["derivation"]["days"]["assumption"]


def test_weeks_only_assumes_six_days():
    out = d.derive(obs({"type": "period", "value": 2, "unit": "week", "range": None}))
    assert out["canonical"]["days"] == 12
    assert "6 working days/week" in out["derivation"]["days"]["assumption"]


def test_frequency_alone_asks_one_thing():
    out = d.derive(obs(FIVE_A_WEEK))
    assert "days" not in out["canonical"]
    assert out["ambiguity"][0]["kind"] == "need_period"


def test_weekly_rate_divides_by_six():
    out = d.derive(obs({"type": "rate", "value": 3500, "per": "week"}))
    assert out["canonical"]["rate"] == 583


def test_trip_rate_needs_trips_per_day():
    out = d.derive(obs({"type": "rate", "value": 200, "per": "trip"}))
    assert "rate" not in out["canonical"] and out["ambiguity"][0]["kind"] == "trips_per_day"
    out = d.derive(obs({"type": "rate", "value": 200, "per": "trip"}, {"type": "trips", "per_day": 4}))
    assert out["canonical"]["rate"] == 800


def test_ambiguous_advance_is_not_counted_until_clear():
    out = d.derive(obs({"type": "advance", "value": 5000, "ambiguous": True}))
    assert "advance" not in out["canonical"]
    assert out["ambiguity"][0]["kind"] == "is_advance"


def test_outstanding_includes_bonus_and_deductions():
    out = d.derive(obs({"type": "explicit_days", "value": 6}, {"type": "rate", "value": 700, "per": "day"},
                       {"type": "advance", "value": 500}, {"type": "payment", "value": 3000},
                       {"type": "deduction", "value": 200, "reason": "khana"},
                       {"type": "bonus", "value": 1000, "promised": True}))
    c = out["canonical"]
    assert c["expected"] == 6 * 700 + 1000 - 200
    assert c["received"] == 3500 and c["outstanding"] == 1500


def test_payments_add_up_and_never_go_negative():
    out = d.derive(obs({"type": "explicit_days", "value": 2}, {"type": "rate", "value": 500},
                       {"type": "advance", "value": 0}, {"type": "payment", "value": 600},
                       {"type": "payment", "value": 900}))
    assert out["canonical"]["payments"] == 1500 and out["canonical"]["outstanding"] == 0


def test_contradiction_does_not_overwrite():
    stored = [{"type": "explicit_days", "value": 6}]
    c = d.contradiction(stored, {"type": "explicit_days", "value": 5})
    assert c["slot"] == "explicit_days" and c["old"]["value"] == 6 and c["new"]["value"] == 5
    assert d.contradiction(stored, {"type": "explicit_days", "value": 5, "correction": True}) is None
    assert d.contradiction(stored, {"type": "explicit_days", "value": 6}) is None


def test_frequency_conflict_is_flagged():
    c = d.contradiction([FIVE_A_WEEK], {"type": "frequency", "days_per_week": 7})
    assert c and c["slot"] == "frequency"


def test_confirmed_observation_confirms_the_derivation():
    out = d.derive(obs({**PERIOD_5_6_MO, "confirmed": True}, FIVE_A_WEEK))
    assert out["derivation"]["days"]["confirmed"] is True


def test_describe_reads_back_in_hinglish():
    assert d.describe(PERIOD_5_6_MO)[0] == "5-6 mahine"
    assert d.describe(FIVE_A_WEEK)[0] == "hafte mein 5 din"
    assert d.describe({"type": "rate", "value": 15000, "per": "month"})[0] == "15000 mahine ke"
