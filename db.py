"""SQLite storage: users, delivery evidence, and customer confirmations (stdlib sqlite3 only)."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

DB_PATH = os.getenv("DATABASE_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence.db")

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo1234"

DELIVERY_COLUMNS = [
    "order_id", "rider_id", "customer_phone_masked", "otp_confirmed", "gps_matched",
    "photo_captured", "photo_id", "spoken_context", "handover_location", "obstacle",
    "customer_instruction", "confidence", "evidence_strength", "recommendation",
    "stt_engine", "extraction_engine", "audio_hash", "recording_session_id", "received_at",
    # Additions beyond the base schema:
    "customer_confirmed", "session_verified", "recorded_at_client", "client_id", "card_json",
]


def now_iso():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


@contextmanager
def connect():
    """One short-lived connection per call (safe with gunicorn threads): commit on success, always close."""
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()


def init_db():
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS deliveries (
                id INTEGER PRIMARY KEY,
                order_id TEXT,
                rider_id TEXT,
                customer_phone_masked TEXT,
                otp_confirmed INTEGER,
                gps_matched INTEGER,
                photo_captured INTEGER,
                photo_id TEXT,
                spoken_context TEXT,
                handover_location TEXT,
                obstacle TEXT,
                customer_instruction TEXT,
                confidence TEXT,
                evidence_strength INTEGER,
                recommendation TEXT,
                stt_engine TEXT,
                extraction_engine TEXT,
                audio_hash TEXT,
                recording_session_id TEXT,
                received_at TEXT,
                customer_confirmed INTEGER,
                session_verified INTEGER,
                recorded_at_client TEXT,
                client_id TEXT UNIQUE,
                card_json TEXT
            );
            CREATE INDEX IF NOT EXISTS deliveries_received ON deliveries(received_at DESC);
            CREATE TABLE IF NOT EXISTS confirmations (
                order_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                confirmed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS qr_nonces (
                order_id TEXT PRIMARY KEY,
                nonce TEXT NOT NULL
            );
            """
        )
        has_users = con.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    if not has_users:
        create_user(DEMO_EMAIL, DEMO_PASSWORD)
        print(f" * Demo login created: {DEMO_EMAIL} / {DEMO_PASSWORD} (change it before sharing the link widely)")


# ---- deliveries ----

def insert_delivery(rec):
    """Insert one evidence record. A repeated client_id (offline retry) returns the existing row's id."""
    values = [rec.get(c) for c in DELIVERY_COLUMNS]
    with connect() as con:
        cur = con.execute(
            f"INSERT INTO deliveries ({', '.join(DELIVERY_COLUMNS)}) VALUES ({', '.join('?' * len(DELIVERY_COLUMNS))}) "
            "ON CONFLICT(client_id) DO NOTHING",
            values,
        )
        if cur.rowcount:
            return cur.lastrowid
        row = con.execute("SELECT id FROM deliveries WHERE client_id = ?", (rec.get("client_id"),)).fetchone()
        return row["id"] if row else None


def list_deliveries(limit=200):
    with connect() as con:
        rows = con.execute("SELECT * FROM deliveries ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["card_json"] = json.loads(d["card_json"]) if d["card_json"] else {}
        except ValueError:
            d["card_json"] = {}
        out.append(d)
    return out


# ---- users ----

def create_user(email, password):
    """Returns the new user id, or None if the email is already taken."""
    email = (email or "").strip().lower()
    try:
        with connect() as con:
            cur = con.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, generate_password_hash(password), now_iso()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def verify_user(email, password):
    """Returns the user id if the email and password match, else None."""
    email = (email or "").strip().lower()
    with connect() as con:
        row = con.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    if row and check_password_hash(row["password_hash"], password or ""):
        return row["id"]
    return None


# ---- customer confirmations (survive restarts) ----

def get_confirmation(order_id):
    with connect() as con:
        row = con.execute("SELECT session_id, confirmed_at FROM confirmations WHERE order_id = ?", (order_id,)).fetchone()
    return dict(row) if row else None


def add_confirmation(order_id, session_id):
    """First tap wins; a repeat tap keeps the original session."""
    with connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO confirmations (order_id, session_id, confirmed_at) VALUES (?, ?, ?)",
            (order_id, session_id, now_iso()),
        )


def get_nonce(order_id):
    with connect() as con:
        row = con.execute("SELECT nonce FROM qr_nonces WHERE order_id = ?", (order_id,)).fetchone()
    return row["nonce"] if row else None


def set_nonce(order_id, nonce):
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO qr_nonces (order_id, nonce) VALUES (?, ?)", (order_id, nonce))


def reset_confirmation(order_id):
    with connect() as con:
        con.execute("DELETE FROM confirmations WHERE order_id = ?", (order_id,))
        con.execute("DELETE FROM qr_nonces WHERE order_id = ?", (order_id,))
