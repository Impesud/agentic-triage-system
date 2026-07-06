"""Persistenza allerte di sicurezza su SQLite — Lezione 18."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import paths

_SECURITY_ALERTS_DDL = """
CREATE TABLE IF NOT EXISTS security_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    blocked_stage TEXT NOT NULL,
    matched_pattern TEXT,
    input_excerpt TEXT NOT NULL,
    payload_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_security_alerts_type ON security_alerts(alert_type);
"""


@dataclass(frozen=True)
class SecurityAlertRecord:
    id: int
    alert_type: str
    severity: str
    blocked_stage: str
    matched_pattern: str | None
    input_excerpt: str
    payload_json: str | None
    created_at: str


def init_security_tables(db_path: str | None = None) -> None:
    """Crea la tabella security_alerts se assente."""
    path = db_path or str(paths.TRIAGE_DB_PATH)
    paths.TRIAGE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(_SECURITY_ALERTS_DDL)
        conn.commit()


def log_security_alert(
    *,
    alert_type: str,
    severity: str,
    blocked_stage: str,
    input_excerpt: str,
    matched_pattern: str | None = None,
    payload: dict[str, Any] | None = None,
    db_path: str | None = None,
) -> int:
    """Inserisce un record di allerta e ritorna l'id generato."""
    path = db_path or str(paths.TRIAGE_DB_PATH)
    init_security_tables(path)
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO security_alerts (
                alert_type, severity, blocked_stage,
                matched_pattern, input_excerpt, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                alert_type,
                severity,
                blocked_stage,
                matched_pattern,
                input_excerpt,
                payload_json,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_recent_alerts(limit: int = 10, db_path: str | None = None) -> list[SecurityAlertRecord]:
    """Elenco allerte recenti per demo e test."""
    path = db_path or str(paths.TRIAGE_DB_PATH)
    if not paths.TRIAGE_DB_PATH.exists() and db_path is None:
        return []

    init_security_tables(path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, alert_type, severity, blocked_stage,
                   matched_pattern, input_excerpt, payload_json, created_at
            FROM security_alerts
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()

    return [
        SecurityAlertRecord(
            id=row["id"],
            alert_type=row["alert_type"],
            severity=row["severity"],
            blocked_stage=row["blocked_stage"],
            matched_pattern=row["matched_pattern"],
            input_excerpt=row["input_excerpt"],
            payload_json=row["payload_json"],
            created_at=row["created_at"] or datetime.now(UTC).isoformat(),
        )
        for row in rows
    ]
