"""SQLite persistence for content records and the structured audit log."""

import json
import sqlite3
from contextlib import contextmanager

DB_PATH = "provenance.db"


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they do not exist. Safe to call on every startup."""
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS content (
                content_id        TEXT PRIMARY KEY,
                creator_id        TEXT NOT NULL,
                text              TEXT NOT NULL,
                attribution       TEXT NOT NULL,
                confidence        REAL NOT NULL,
                ai_score          REAL NOT NULL,
                llm_score         REAL NOT NULL,
                stylometric_score REAL NOT NULL,
                status            TEXT NOT NULL,
                creator_reasoning TEXT,
                created_at        TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp  TEXT NOT NULL,
                details    TEXT NOT NULL
            )
            """
        )


def save_content(record: dict):
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO content (content_id, creator_id, text, attribution,
                confidence, ai_score, llm_score, stylometric_score, status,
                creator_reasoning, created_at)
            VALUES (:content_id, :creator_id, :text, :attribution, :confidence,
                :ai_score, :llm_score, :stylometric_score, :status,
                :creator_reasoning, :created_at)
            """,
            record,
        )


def get_content(content_id: str):
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM content WHERE content_id = ?", (content_id,)
        ).fetchone()
        return dict(row) if row else None


def update_status(content_id: str, status: str, creator_reasoning: str):
    with _conn() as conn:
        conn.execute(
            "UPDATE content SET status = ?, creator_reasoning = ? WHERE content_id = ?",
            (status, creator_reasoning, content_id),
        )


def add_log_entry(content_id: str, event_type: str, timestamp: str, details: dict):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (content_id, event_type, timestamp, details) "
            "VALUES (?, ?, ?, ?)",
            (content_id, event_type, timestamp, json.dumps(details)),
        )


def get_log(limit: int = 50):
    """Return the most recent audit-log entries, newest first, with details
    flattened into each entry for readability."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    entries = []
    for row in rows:
        entry = {
            "log_id": row["id"],
            "content_id": row["content_id"],
            "event_type": row["event_type"],
            "timestamp": row["timestamp"],
        }
        entry.update(json.loads(row["details"]))
        entries.append(entry)
    return entries
