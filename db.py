import json
import sqlite3
from datetime import datetime

DB_FILE = "proposals.db"


def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS proposals (
            key         TEXT PRIMARY KEY,
            type        TEXT,
            payload     TEXT,
            status      TEXT DEFAULT 'pending',
            first_seen  TEXT,
            decided_at  TEXT,
            result      TEXT
        )
    """)
    return conn


def save_new_proposals(proposals):
    """Add new proposals. Anything already in the database is NOT re-added."""
    conn = connect()
    added = refreshed = skipped = 0
    for p in proposals:
        row = conn.execute("SELECT status FROM proposals WHERE key = ?", (p["key"],)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO proposals (key, type, payload, first_seen) VALUES (?, ?, ?, ?)",
                (p["key"], p["type"], json.dumps(p), datetime.now().isoformat()))
            added += 1
        elif row["status"] == "pending":
            # still waiting for a decision: refresh the evidence, keep it pending
            conn.execute("UPDATE proposals SET payload = ? WHERE key = ?", (json.dumps(p), p["key"]))
            refreshed += 1
        else:
            skipped += 1  # already approved or rejected: leave it alone
    conn.commit()
    conn.close()
    return added, refreshed, skipped


def list_proposals(status=None):
    conn = connect()
    if status:
        rows = conn.execute("SELECT * FROM proposals WHERE status = ? ORDER BY type, key", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM proposals ORDER BY status, type, key").fetchall()
    conn.close()
    return rows


def get_proposal(key):
    conn = connect()
    row = conn.execute("SELECT * FROM proposals WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row


def set_decision(key, status, result=""):
    conn = connect()
    conn.execute("UPDATE proposals SET status = ?, decided_at = ?, result = ? WHERE key = ?",
                 (status, datetime.now().isoformat(), result, key))
    conn.commit()
    conn.close()