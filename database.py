"""SQLite store for finished wage cases (stdlib sqlite3)."""
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


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute(SCHEMA)


def save_case(session_id, case):
    """Insert the case, or update it (e.g. when the payment request is added). Returns the row id."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """INSERT INTO wage_cases (session_id, days, rate, advance, payments, expected, received,
                                       outstanding, payment_request, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET payment_request = excluded.payment_request""",
            (session_id, case["days"], case["rate"], case["advance"], case["payments"], case["expected"],
             case["received"], case["outstanding"], case.get("payment_request"), now),
        )
        return conn.execute("SELECT id FROM wage_cases WHERE session_id = ?", (session_id,)).fetchone()["id"]


def get_case(session_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM wage_cases WHERE session_id = ?", (session_id,)).fetchone()
    return dict(row) if row else None
