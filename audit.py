"""Audit layer: every finished case becomes a canonical JSON record with a sha256 hash.

The hash does not stop anyone editing the database. It makes any edit detectable: recompute the
hash of the stored JSON (verify()) and compare it with the one shown to the worker and written in
the shared case. Also builds the escalation draft and the share-with-union text. No outside calls.
"""
import hashlib
import json
from datetime import date, datetime, timedelta, timezone

from wage_math import format_inr

SAMADHAN_URL = "https://samadhan.labour.gov.in"     # Ministry of Labour portal for wage claims (sourced in README)
LABOURLINE = "1800 1800 999"                        # India Labourline (sourced in README); 1916 is NOT a labour line
SLOT_KEYS = ("days", "rate", "advance", "payments", "overtime_hours", "overtime_rate", "deductions")


def canonical_json(record):
    """One exact byte string for a record: sorted keys, no extra spaces, UTF-8."""
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def case_record(session, policy_source):
    case = session["case"]
    return {
        "session_id": session["id"],
        "slots": {k: case.get(k, 0) for k in SLOT_KEYS},
        "expected": case["expected"], "received": case["received"], "outstanding": case["outstanding"],
        "transcript": [{k: t.get(k) for k in ("at", "state", "agent", "worker")} for t in session["turns"]],
        "context_notes": list(session.get("context_notes", [])),
        "language": session.get("language", "hi"),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "policy_source": policy_source,
        "node_path": list(session.get("node_path", [])),
    }


def seal(session, policy_source):
    """(canonical_json, sha256 hex) for the session's finished case."""
    text = canonical_json(case_record(session, policy_source))
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify(case_json, case_hash):
    return hashlib.sha256(case_json.encode("utf-8")).hexdigest() == case_hash


# ---------- follow-up ----------

_GIVE = {"dega", "denge", "dunga", "dengi", "degi", "dene", "de", "pay", "karega", "karenge", "will", "bola", "kaha"}
_WHEN = {"kal": 1, "parson": 2, "parso": 2, "tomorrow": 1, "aaj": 0, "today": 0}


def commitment_from(text, today=None):
    """"kal dega" -> tomorrow's date (ISO); "agle hafte" -> in 7 days; otherwise None."""
    words = set(text.lower().replace(",", " ").replace(".", " ").split())
    if not words & _GIVE:
        return None
    today = today or date.today()
    if {"agle", "hafte"} <= words or "week" in words:
        return (today + timedelta(days=7)).isoformat()
    for w, d in _WHEN.items():
        if w in words:
            return (today + timedelta(days=d)).isoformat()
    return None


# ---------- escalation and share ----------

def escalation_draft(case, case_hash, followup_log=(), sent_at=None):
    """A Hinglish complaint the worker can copy to the SAMADHAN portal or the labour office.
    Nothing is submitted for them."""
    lines = [
        "Seva mein: Shram Ayukt (Labour Commissioner) / SAMADHAN portal",
        "Vishay: Mazdoori ka baaki bhugtan",
        "",
        "Mahoday,",
        f"Maine {case['days']} din kaam kiya. Roz ki mazdoori {format_inr(case['rate'])} tay hui thi.",
    ]
    if case.get("overtime_hours"):
        lines.append(f"Overtime: {case['overtime_hours']} ghante × {format_inr(case['overtime_rate'])}.")
    if case.get("deductions"):
        lines.append(f"Katauti: {format_inr(case['deductions'])}.")
    lines += [
        f"Kul kamaai: {format_inr(case['expected'])}. Advance: {format_inr(case['advance'])}. "
        f"Ab tak mila: {format_inr(case['payments'])}.",
        f"Baaki: {format_inr(case['outstanding'])}.",
    ]
    if sent_at:
        lines.append(f"Thekedar ko {sent_at[:10]} ko WhatsApp par hisaab bheja gaya.")
    for f in followup_log:
        lines.append(f"Follow-up {str(f.get('at', ''))[:10]}: {f.get('text', '')}")
    lines += [
        "",
        "Kripya baaki mazdoori dilwane ki kripa karein.",
        f"Case hash (sha256): {case_hash}",
        "(PagarSaathi se banaya gaya hisaab. Hash se pata chalta hai ki case badla gaya ya nahi.)",
        "",
        f"SAMADHAN portal: {SAMADHAN_URL}",
        f"India Labourline: {LABOURLINE}",
    ]
    return "\n".join(lines)


def case_from_row(row):
    """A database row with the sealed slots merged in (overtime and deductions live only in the JSON)."""
    record = json.loads(row["case_json"]) if row.get("case_json") else {}
    return {**row, **record.get("slots", {})}


def share_text(row):
    """One page for a union or legal-aid volunteer: case, hash, calculation, transcript, follow-ups,
    escalation draft. `row` is database.get_case() output."""
    record = json.loads(row["case_json"]) if row.get("case_json") else {}
    out = [f"PagarSaathi case #{row['id']}", f"Case hash (sha256): {row.get('case_hash') or '-'}",
           f"Bana: {row['created_at']}", f"Bheja gaya: {row.get('sent_at') or 'abhi nahi'}", "",
           "HISAAB",
           f"{row['days']} din × {format_inr(row['rate'])}; advance {format_inr(row['advance'])}; "
           f"ab tak mila {format_inr(row['payments'])}"
           + (f"; overtime {record['slots']['overtime_hours']} ghante × {format_inr(record['slots']['overtime_rate'])}"
              if record.get("slots", {}).get("overtime_hours") else "")
           + (f"; katauti {format_inr(record['slots']['deductions'])}" if record.get("slots", {}).get("deductions") else ""),
           f"Kul kamaai {format_inr(row['expected'])} · Kul mila {format_inr(row['received'])} · "
           f"BAAKI {format_inr(row['outstanding'])}", ""]
    if record.get("context_notes"):
        out += ["MAZDOOR NE BATAYA", *[f"- {n}" for n in record["context_notes"]], ""]
    out.append("BAATCHEET")
    for t in record.get("transcript", []):
        if t.get("agent"):
            out.append(f"[{(t.get('at') or '')[11:19]}] PagarSaathi: {t['agent']}")
        if t.get("worker"):
            out.append(f"[{(t.get('at') or '')[11:19]}] Mazdoor: {t['worker']}")
    if row["followup_log"]:
        out += ["", "FOLLOW-UP", *[f"- {f.get('at', '')[:16]}: {f.get('text', '')}" for f in row["followup_log"]]]
    if row.get("commitment_date"):
        out.append(f"Thekedar ka vaada: {row['commitment_date']}")
    out += ["", "SHIKAYAT KA DRAFT",
            escalation_draft(case_from_row(row), row.get("case_hash") or "-", row["followup_log"], row.get("sent_at"))]
    return "\n".join(out)
