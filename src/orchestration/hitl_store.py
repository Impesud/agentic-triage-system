"""Persistenza sessioni HITL su SQLite — Lezione 19."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import paths

TicketStateStatus = Literal["PENDING_APPROVAL", "APPROVED", "REJECTED", "RESUMED"]

_TICKET_STATES_DDL = """
CREATE TABLE IF NOT EXISTS ticket_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    breakpoint_stage TEXT NOT NULL,
    pending_tool TEXT NOT NULL,
    pending_args_json TEXT NOT NULL,
    stm_json TEXT NOT NULL,
    pipeline_context_json TEXT,
    user_input_excerpt TEXT NOT NULL,
    resolved_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ticket_states_status ON ticket_states(status);
"""


@dataclass(frozen=True)
class TicketStateRecord:
    id: int
    session_id: str
    status: str
    breakpoint_stage: str
    pending_tool: str
    pending_args_json: str
    stm_json: str
    pipeline_context_json: str | None
    user_input_excerpt: str
    resolved_by: str | None
    created_at: str
    resolved_at: str | None


def init_hitl_tables(db_path: str | None = None) -> None:
    """Crea la tabella ticket_states se assente."""
    path = db_path or str(paths.TRIAGE_DB_PATH)
    paths.TRIAGE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(_TICKET_STATES_DDL)
        conn.commit()


def save_ticket_state(
    *,
    session_id: str,
    status: TicketStateStatus,
    breakpoint_stage: str,
    pending_tool: str,
    pending_args: dict[str, Any],
    stm_messages: list[Any],
    pipeline_context: dict[str, Any] | None = None,
    user_input_excerpt: str,
    db_path: str | None = None,
) -> int:
    """Inserisce una sessione HITL e ritorna l'id generato."""
    path = db_path or str(paths.TRIAGE_DB_PATH)
    init_hitl_tables(path)
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO ticket_states (
                session_id, status, breakpoint_stage,
                pending_tool, pending_args_json, stm_json,
                pipeline_context_json, user_input_excerpt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                status,
                breakpoint_stage,
                pending_tool,
                json.dumps(pending_args, ensure_ascii=False),
                json.dumps(stm_messages, ensure_ascii=False, default=str),
                json.dumps(pipeline_context or {}, ensure_ascii=False),
                user_input_excerpt[:500],
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_ticket_state(
    session_id: str,
    *,
    status: TicketStateStatus | None = None,
    db_path: str | None = None,
) -> TicketStateRecord | None:
    """Carica una sessione per session_id, opzionalmente filtrata per status."""
    path = db_path or str(paths.TRIAGE_DB_PATH)
    if not paths.TRIAGE_DB_PATH.exists() and db_path is None:
        return None
    init_hitl_tables(path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if status:
            cursor.execute(
                """
                SELECT id, session_id, status, breakpoint_stage,
                       pending_tool, pending_args_json, stm_json,
                       pipeline_context_json, user_input_excerpt,
                       resolved_by, created_at, resolved_at
                FROM ticket_states
                WHERE session_id = ? AND status = ?
                """,
                (session_id, status),
            )
        else:
            cursor.execute(
                """
                SELECT id, session_id, status, breakpoint_stage,
                       pending_tool, pending_args_json, stm_json,
                       pipeline_context_json, user_input_excerpt,
                       resolved_by, created_at, resolved_at
                FROM ticket_states
                WHERE session_id = ?
                """,
                (session_id,),
            )
        row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_record(row)


def list_pending_states(
    limit: int = 20,
    db_path: str | None = None,
) -> list[TicketStateRecord]:
    """Elenco sessioni in attesa di approvazione."""
    path = db_path or str(paths.TRIAGE_DB_PATH)
    if not paths.TRIAGE_DB_PATH.exists() and db_path is None:
        return []
    init_hitl_tables(path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, session_id, status, breakpoint_stage,
                   pending_tool, pending_args_json, stm_json,
                   pipeline_context_json, user_input_excerpt,
                   resolved_by, created_at, resolved_at
            FROM ticket_states
            WHERE status = 'PENDING_APPROVAL'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
    return [_row_to_record(row) for row in rows]


def update_ticket_state_status(
    session_id: str,
    *,
    status: TicketStateStatus,
    resolved_by: str | None = None,
    db_path: str | None = None,
) -> bool:
    """Aggiorna lo status di una sessione HITL."""
    path = db_path or str(paths.TRIAGE_DB_PATH)
    init_hitl_tables(path)
    resolved_at = datetime.now(UTC).isoformat()
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE ticket_states
            SET status = ?, resolved_by = ?, resolved_at = ?
            WHERE session_id = ?
            """,
            (status, resolved_by, resolved_at, session_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_ticket_state(session_id: str, db_path: str | None = None) -> bool:
    """Rimuove una sessione HITL (idempotente per re-run demo)."""
    path = db_path or str(paths.TRIAGE_DB_PATH)
    if not paths.TRIAGE_DB_PATH.exists() and db_path is None:
        return False
    init_hitl_tables(path)
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ticket_states WHERE session_id = ?", (session_id,))
        conn.commit()
        return cursor.rowcount > 0


def _row_to_record(row: sqlite3.Row) -> TicketStateRecord:
    return TicketStateRecord(
        id=row["id"],
        session_id=row["session_id"],
        status=row["status"],
        breakpoint_stage=row["breakpoint_stage"],
        pending_tool=row["pending_tool"],
        pending_args_json=row["pending_args_json"],
        stm_json=row["stm_json"],
        pipeline_context_json=row["pipeline_context_json"],
        user_input_excerpt=row["user_input_excerpt"],
        resolved_by=row["resolved_by"],
        created_at=row["created_at"] or datetime.now(UTC).isoformat(),
        resolved_at=row["resolved_at"],
    )
