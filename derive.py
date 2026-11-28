"""Derivation: turn what the worker actually said (observations) into the four canonical numbers.

Pure Python, no LLM, no I/O. The LLM (or the rules reader in observe.py) only tags what was said;
this module does every conversion, and records the formula it used so the agent can say it aloud
and the worker can confirm it. Nothing derived is used until the worker confirms it.

    derive(observations) -> {"canonical": {...}, "derivation": {...}, "ambiguity": [...]}

Observation types (each a dict with "type" plus these fields):
    period         {value: 6 | "5-6", unit: "month" | "week" | "day", range: [5, 6] | None}
    frequency      {days_per_week: 5, explicit_off: ["Sunday"] | None}
    explicit_days  {value: 26}
    rate           {value: 700, per: "day" | "week" | "month" | "trip", range: [600, 700] | None}
    trips          {per_day: 4}                     (answers "ek din mein kitne trip?")
    advance        {value: 5000, ambiguous: bool}
    payment        {value: 3000}
    deduction      {value: 200, reason: "khana"}
    bonus          {value: 1000, promised: bool}
    context        {text: "hospital", category: "health" | "threat" | "question" | "emotion" | ...}
Any observation may carry "confirmed": True (the worker agreed to it) and "turn": n.
"""

WORK_DAYS_PER_MONTH = 26          # stated to the worker whenever it is used
WEEKS_PER_MONTH = 4.33
DEFAULT_DAYS_PER_WEEK = 6
SLOTS = ("days", "rate", "advance", "payments")
TYPES = ("period", "frequency", "explicit_days", "rate", "trips", "advance", "payment", "deduction", "bonus",
         "context")


def _num(v):
    return int(v) if float(v).is_integer() else float(v)


def _fmt(v):
    v = _num(v)
    return str(v) if isinstance(v, int) else f"{v:g}"


def _last(observations, kind):
    found = [o for o in observations if o.get("type") == kind]
    return found[-1] if found else None


def _span(o):
    """(low, high) of an observation's value: a range, or one number twice."""
    rng = o.get("range")
    if isinstance(rng, (list, tuple)) and len(rng) == 2:
        return _num(rng[0]), _num(rng[1])
    v = o.get("value")
    if isinstance(v, str) and "-" in v:
        lo, hi = v.split("-", 1)
        return _num(lo), _num(hi)
    return _num(v), _num(v)


def _period_text(o):
    lo, hi = _span(o)
    n = _fmt(lo) if lo == hi else f"{_fmt(lo)}-{_fmt(hi)}"
    return n, {"month": "mo", "week": "wk", "day": "d"}[o.get("unit", "day")]


def derive_days(observations):
    """(entry, ambiguity list) for days, or (None, ambiguity) when it cannot be derived yet."""
    amb = []
    explicit = _last(observations, "explicit_days")
    if explicit:
        v = round(_num(explicit["value"]))
        return {"value": v, "formula": f"{v} (worker said)", "source": "worker said",
                "confirmed": True, "assumption": None}, amb
    period, freq = _last(observations, "period"), _last(observations, "frequency")
    if not period:
        if freq:
            amb.append({"slot": "days", "kind": "need_period", "blocking": True,
                        "question": ("Hafte mein {d} din. Aise kitne hafte ya mahine kaam kiya?".format(
                            d=_fmt(freq["days_per_week"])),
                                     "हफ़्ते में {d} दिन। ऐसे कितने हफ़्ते या महीने काम किया?".format(
                            d=_fmt(freq["days_per_week"])))})
        return None, amb
    lo, hi = _span(period)
    n, unit = _period_text(period)
    if lo != hi:
        # The first proposal uses the upper end the worker named; the confirmation line names the
        # range, so "nahi, 5 mahine" corrects it. Only a bare "nahi" makes the agent ask which end.
        amb.append({"slot": "days", "kind": "range", "blocking": False, "options": [lo, hi],
                    "question": (f"{_fmt(lo)} ya {_fmt(hi)}, kaunsa?", f"{_fmt(lo)} या {_fmt(hi)}, कौन-सा?")})
    used = hi
    used_note = f" ({_fmt(hi)} used)" if lo != hi else ""
    unit_full = period.get("unit", "day")
    if unit_full == "day":
        v = round(used)
        return {"value": v, "formula": f"{n} d", "source": "worker said", "confirmed": lo == hi,
                "assumption": None}, amb
    if freq:
        dpw = _num(freq["days_per_week"])
        if unit_full == "month":
            v = round(used * WEEKS_PER_MONTH * dpw)
            formula = f"{n} mo{used_note} × {WEEKS_PER_MONTH} wk × {_fmt(dpw)} d/wk ≈ {v}"
        else:
            v = round(used * dpw)
            formula = f"{n} wk{used_note} × {_fmt(dpw)} d/wk = {v}"
        return {"value": v, "formula": formula, "source": "period × frequency", "confirmed": False,
                "assumption": None}, amb
    if unit_full == "month":
        v = round(used * WORK_DAYS_PER_MONTH)
        return {"value": v, "formula": f"{n} mo{used_note} × {WORK_DAYS_PER_MONTH} d/mo ≈ {v}",
                "source": "period only", "confirmed": False,
                "assumption": f"{WORK_DAYS_PER_MONTH} working days/month, confirm with worker"}, amb
    v = round(used * DEFAULT_DAYS_PER_WEEK)
    return {"value": v, "formula": f"{n} wk{used_note} × {DEFAULT_DAYS_PER_WEEK} d/wk = {v}",
            "source": "period only", "confirmed": False,
            "assumption": f"{DEFAULT_DAYS_PER_WEEK} working days/week, confirm with worker"}, amb


def derive_rate(observations):
    amb = []
    rate = _last(observations, "rate")
    if not rate:
        return None, amb
    lo, hi = _span(rate)
    if lo != hi:
        amb.append({"slot": "rate", "kind": "range", "blocking": True, "options": [lo, hi],
                    "question": (f"{_fmt(lo)} ya {_fmt(hi)}: roz ke kitne tay hue the?",
                                 f"{_fmt(lo)} या {_fmt(hi)}: रोज़ के कितने तय हुए थे?")})
        return None, amb
    per = rate.get("per", "day")
    v = _num(lo)
    if per == "day":
        return {"value": round(v), "formula": f"{_fmt(v)}/day (worker said)", "source": "worker said",
                "confirmed": True, "assumption": None}, amb
    if per == "week":
        d = round(v / DEFAULT_DAYS_PER_WEEK)
        return {"value": d, "formula": f"{_fmt(v)}/wk ÷ {DEFAULT_DAYS_PER_WEEK} d ≈ {d}/day", "source": "per week",
                "confirmed": False, "assumption": f"{DEFAULT_DAYS_PER_WEEK} working days/week"}, amb
    if per == "month":
        d = round(v / WORK_DAYS_PER_MONTH)
        return {"value": d, "formula": f"{_fmt(v)}/mo ÷ {WORK_DAYS_PER_MONTH} d ≈ {d}/day", "source": "per month",
                "confirmed": False, "assumption": f"{WORK_DAYS_PER_MONTH} working days/month"}, amb
    if per == "trip":
        trips = _last(observations, "trips")
        if trips:
            t = _num(trips["per_day"])
            d = round(v * t)
            return {"value": d, "formula": f"{_fmt(v)}/trip × {_fmt(t)} trips/day = {d}/day", "source": "per trip",
                    "confirmed": False, "assumption": None}, amb
        amb.append({"slot": "rate", "kind": "trips_per_day", "blocking": True,
                    "question": ("Ek din mein kitne trip hote the?", "एक दिन में कितने ट्रिप होते थे?")})
    return None, amb


def _sum(observations, kind, skip_ambiguous=False):
    vals = [o for o in observations if o.get("type") == kind and not (skip_ambiguous and o.get("ambiguous"))]
    return (sum(round(_num(o["value"])) for o in vals), True) if vals else (0, False)


def derive(observations):
    """canonical numbers, how each was derived, and what still needs the worker's word."""
    observations = [o for o in observations or [] if isinstance(o, dict) and o.get("type") in TYPES]
    canonical, derivation, ambiguity = {}, {}, []
    for slot, fn in (("days", derive_days), ("rate", derive_rate)):
        entry, amb = fn(observations)
        ambiguity += amb
        if entry:
            confirmed_obs = any(o.get("confirmed") for o in observations
                                if o.get("type") in ({"days": ("explicit_days", "period", "frequency"),
                                                      "rate": ("rate", "trips")}[slot]))
            entry["confirmed"] = entry["confirmed"] or confirmed_obs
            derivation[slot] = entry
            canonical[slot] = entry["value"]
    advance, has_adv = _sum(observations, "advance", skip_ambiguous=True)
    for o in observations:
        if o.get("type") == "advance" and o.get("ambiguous"):
            v = _fmt(o["value"])
            ambiguity.append({"slot": "advance", "kind": "is_advance", "blocking": True, "value": o["value"],
                              "question": (f"Kya woh {v} rupaye aapki mazdoori mein se kaate gaye ya katenge?",
                                           f"क्या वह {v} रुपये आपकी मज़दूरी में से काटे गए या कटेंगे?")})
    if has_adv:
        canonical["advance"] = advance
        derivation["advance"] = {"value": advance, "formula": f"{advance} (worker said)", "source": "worker said",
                                 "confirmed": True, "assumption": None}
    payments, has_pay = _sum(observations, "payment")
    if has_pay:
        canonical["payments"] = payments
        derivation["payments"] = {"value": payments, "formula": f"{payments} (worker said)",
                                  "source": "worker said", "confirmed": True, "assumption": None}
    deductions, has_ded = _sum(observations, "deduction")
    bonus, has_bonus = _sum(observations, "bonus")
    if has_ded:
        canonical["deductions"] = deductions
    if has_bonus:
        canonical["bonus"] = bonus
    if all(s in canonical for s in SLOTS):
        expected = canonical["days"] * canonical["rate"] + bonus - deductions
        received = canonical["advance"] + canonical["payments"]
        canonical.update(expected=expected, received=received, outstanding=max(0, expected - received))
    return {"canonical": canonical, "derivation": derivation, "ambiguity": ambiguity}


# ---------- contradictions: a new observation that disagrees with a stored one ----------

_COMPARE = {"explicit_days": lambda o: _span(o), "rate": lambda o: (_span(o), o.get("per", "day")),
            "frequency": lambda o: _num(o["days_per_week"]), "period": lambda o: (_span(o), o.get("unit"))}


def contradiction(stored, new):
    """{"slot", "old", "new"} when `new` disagrees with the latest stored observation of its type
    (and is not marked as a correction), else None. Nothing is overwritten here."""
    kind = new.get("type")
    if kind not in _COMPARE or new.get("correction"):
        return None
    old = _last(stored, kind)
    if not old or _COMPARE[kind](old) == _COMPARE[kind](new):
        return None
    return {"slot": kind, "old": old, "new": new}


def describe(o):
    """Short Hinglish words for an observation, for "Aapne pehle X kaha, ab Y"."""
    kind = o.get("type")
    if kind == "explicit_days":
        return (f"{_fmt(o['value'])} din", f"{_fmt(o['value'])} दिन")
    if kind == "frequency":
        d = _fmt(o["days_per_week"])
        return (f"hafte mein {d} din", f"हफ़्ते में {d} दिन")
    if kind == "rate":
        lo, hi = _span(o)
        n = _fmt(lo) if lo == hi else f"{_fmt(lo)}-{_fmt(hi)}"
        per = {"day": ("roz", "रोज़"), "week": ("hafte ke", "हफ़्ते के"), "month": ("mahine ke", "महीने के"),
               "trip": ("trip ke", "ट्रिप के")}[o.get("per", "day")]
        return (f"{n} {per[0]}", f"{n} {per[1]}")
    if kind == "period":
        n, _ = _period_text(o)
        one = n == "1"
        unit = {"month": ("mahina" if one else "mahine", "महीना" if one else "महीने"),
                "week": ("hafta" if one else "hafte", "हफ़्ता" if one else "हफ़्ते"),
                "day": ("din", "दिन")}[o.get("unit", "day")]
        return (f"{n} {unit[0]}", f"{n} {unit[1]}")
    v = _fmt(o.get("value", 0))
    return (v, v)
