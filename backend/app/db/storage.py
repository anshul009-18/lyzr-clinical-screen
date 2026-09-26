"""
Lightweight SQLite persistence for ingested protocols and patients.
No ORM — this is intentionally simple for MVP speed. Swap for
Postgres + SQLAlchemy later if the project needs concurrent writes
or multi-instance deployment.
"""

import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "pipeline.db"


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS protocols (
                protocol_id TEXT PRIMARY KEY,
                raw_text TEXT,
                criteria_json TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                record_json TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hitl_reviews (
                dossier_id TEXT PRIMARY KEY,
                patient_id TEXT,
                protocol_id TEXT,
                decision TEXT,
                confidence REAL,
                reason TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                resolved_at TEXT,
                resolved_by TEXT
            )
        """)


def save_hitl_review(dossier_id: str, patient_id: str, protocol_id: str,
                      decision: str, confidence: float, reason: str):
    from datetime import datetime, timezone
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO hitl_reviews
               (dossier_id, patient_id, protocol_id, decision, confidence, reason, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (dossier_id, patient_id, protocol_id, decision, confidence, reason,
             datetime.now(timezone.utc).isoformat()),
        )


def list_pending_hitl_reviews() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT dossier_id, patient_id, protocol_id, decision, confidence, reason, created_at "
            "FROM hitl_reviews WHERE status = 'pending' ORDER BY created_at DESC"
        ).fetchall()
    return [
        {"dossier_id": r[0], "patient_id": r[1], "protocol_id": r[2],
         "decision": r[3], "confidence": r[4], "reason": r[5], "created_at": r[6]}
        for r in rows
    ]


def resolve_hitl_review(dossier_id: str, status: str, resolved_by: str) -> bool:
    from datetime import datetime, timezone
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE hitl_reviews SET status = ?, resolved_at = ?, resolved_by = ? WHERE dossier_id = ?",
            (status, datetime.now(timezone.utc).isoformat(), resolved_by, dossier_id),
        )
    return cur.rowcount > 0


def get_hitl_review(dossier_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT dossier_id, patient_id, protocol_id, decision, confidence, reason, "
            "status, created_at, resolved_at, resolved_by FROM hitl_reviews WHERE dossier_id = ?",
            (dossier_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "dossier_id": row[0], "patient_id": row[1], "protocol_id": row[2],
        "decision": row[3], "confidence": row[4], "reason": row[5],
        "status": row[6], "created_at": row[7], "resolved_at": row[8], "resolved_by": row[9],
    }


@contextmanager


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_protocol(protocol_id: str, raw_text: str, criteria: dict | None = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO protocols (protocol_id, raw_text, criteria_json) VALUES (?, ?, ?)",
            (protocol_id, raw_text, json.dumps(criteria) if criteria else None),
        )


def update_protocol_criteria(protocol_id: str, criteria: dict):
    with get_conn() as conn:
        conn.execute(
            "UPDATE protocols SET criteria_json = ? WHERE protocol_id = ?",
            (json.dumps(criteria), protocol_id),
        )


def get_protocol(protocol_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT protocol_id, raw_text, criteria_json FROM protocols WHERE protocol_id = ?",
            (protocol_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "protocol_id": row[0],
        "raw_text": row[1],
        "criteria": json.loads(row[2]) if row[2] else None,
    }


def save_patient(patient_id: str, record: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO patients (patient_id, record_json) VALUES (?, ?)",
            (patient_id, json.dumps(record)),
        )


def get_patient(patient_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT record_json FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
    return json.loads(row[0]) if row else None


def list_patients() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT patient_id FROM patients").fetchall()
    return [r[0] for r in rows]


def list_protocols() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT protocol_id FROM protocols").fetchall()
    return [r[0] for r in rows]
