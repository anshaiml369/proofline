"""SQLite store for finished wage cases (stdlib sqlite3). Local file only; no third-party analytics."""
import json
import os
import sqlite3
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DATABASE_PATH") or os.path.join(BASE_DIR, "pagarsaathi.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS wage_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    days INTEGER NOT NULL,
    rate INTEGER NOT NULL,
    advance INTEGER NOT NULL,
    payments INTEGER NOT NULL,
    expected INTEGER NOT NULL,
    received INTEGER NOT NULL,
    outstanding INTEGER NOT NULL,
    payment_request TEXT,
    created_at TEXT NOT NULL
)
"""
# Added for the audit layer. Older databases get them through ALTER TABLE in init_db().
EXTRA_COLUMNS = {
    "case_hash": "TEXT", "case_json": "TEXT", "sent_at": "TEXT", "followup_log": "TEXT",
    "commitment_date": "TEXT", "escalation_draft": "TEXT", "language": "TEXT",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute(SCHEMA)
        have = {r["name"] for r in conn.execute("PRAGMA table_info(wage_cases)")}
        for name, kind in EXTRA_COLUMNS.items():
            if name not in have:
                conn.execute(f"ALTER TABLE wage_cases ADD COLUMN {name} {kind}")


def save_case(session_id, case, case_json=None, case_hash=None, language=None):
    """Insert the case, or update it (e.g. when the payment request is added). The hash and the
    canonical JSON are written once and never overwritten. Returns the row id."""
    with connect() as conn:
        conn.execute(
            """INSERT INTO wage_cases (session_id, days, rate, advance, payments, expected, received,
                                       outstanding, payment_request, created_at, case_json, case_hash,
                                       language, escalation_draft)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                   payment_request = excluded.payment_request,
                   escalation_draft = COALESCE(excluded.escalation_draft, escalation_draft),
                   case_json = COALESCE(case_json, excluded.case_json),
                   case_hash = COALESCE(case_hash, excluded.case_hash)""",
            (session_id, case["days"], case["rate"], case["advance"], case["payments"], case["expected"],
             case["received"], case["outstanding"], case.get("payment_request"), now_iso(), case_json,
             case_hash, language, case.get("escalation_draft")),
        )
        return conn.execute("SELECT id FROM wage_cases WHERE session_id = ?", (session_id,)).fetchone()["id"]


def mark_sent(session_id, at=None):
    """The worker tapped Send: store when. Returns the stored time, or None if there is no case."""
    at = at or now_iso()
    with connect() as conn:
        cur = conn.execute("UPDATE wage_cases SET sent_at = ? WHERE session_id = ?", (at, session_id))
    return at if cur.rowcount else None


def add_followup(session_id, entry, commitment_date=None):
    case = get_case(session_id)
    if not case:
        return None
    log = case["followup_log"] + [entry]
    with connect() as conn:
        conn.execute("UPDATE wage_cases SET followup_log = ?, commitment_date = COALESCE(?, commitment_date) "
                     "WHERE session_id = ?", (json.dumps(log, ensure_ascii=False), commitment_date, session_id))
    return get_case(session_id)


def delete_case(session_id):
    """Hard delete: the row is gone. Returns True if a row was deleted."""
    with connect() as conn:
        cur = conn.execute("DELETE FROM wage_cases WHERE session_id = ?", (session_id,))
    return cur.rowcount > 0


def get_case(session_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM wage_cases WHERE session_id = ?", (session_id,)).fetchone()
    if not row:
        return None
    out = dict(row)
    out["followup_log"] = json.loads(out.get("followup_log") or "[]")
    return out
