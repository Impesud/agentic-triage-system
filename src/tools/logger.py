import json
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from paths import LOG_FILE_PATH
import paths

_API_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]+")
_REPEAT_ESCALATION_THRESHOLD = 4


def _ensure_log_dir() -> None:
    LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _redact_sensitive_data(text: str) -> str:
    """Oscura solo pattern sensibili (es. API key), non il testo dei ticket."""
    return _API_KEY_PATTERN.sub("sk-***", text)


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_sensitive_data(value)
    if isinstance(value, dict):
        return {key: _sanitize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def log_event(event_type: str, payload: dict[str, Any]) -> None:
    """Scrive un evento strutturato in logs/activity.jsonl."""
    _ensure_log_dir()

    log_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        "payload": _sanitize_value(payload),
    }

    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def init_db(db_path: str | None = None) -> None:
    """Inizializza il database relazionale SQLite indicizzato sotto data/."""
    path = db_path or str(paths.TRIAGE_DB_PATH)
    paths.TRIAGE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_nome TEXT NOT NULL,
                categoria TEXT NOT NULL,
                priorita TEXT NOT NULL,
                sentiment TEXT NOT NULL,
                riassunto_breve TEXT NOT NULL,
                lingua TEXT NOT NULL,
                azione_eseguita TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_cliente ON tickets(cliente_nome)"
        )
        conn.commit()

    from orchestration.security_store import init_security_tables

    init_security_tables(path)


def log_triage_to_sqlite(ticket_data: dict[str, Any], db_path: str | None = None) -> None:
    """Scrive un record di triage in SQLite (Long-Term Memory indicizzata)."""
    path = db_path or str(paths.TRIAGE_DB_PATH)
    init_db(path)
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tickets (
                cliente_nome, categoria, priorita, sentiment,
                riassunto_breve, lingua, azione_eseguita
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_data.get("cliente_nome", "Anonimo"),
                ticket_data.get("categoria", "GENERAL"),
                ticket_data.get("priorita", "LOW"),
                ticket_data.get("sentiment", "NEUTRALE"),
                ticket_data.get("riassunto_breve", ""),
                ticket_data.get("lingua", "Italiano"),
                ticket_data.get("azione_eseguita", "Nessuna"),
            ),
        )
        conn.commit()
    print("💾 [Database SQLite] Record salvato ed indicizzato con successo.", flush=True)


def _load_sqlite_records(
    cliente_nome: str,
    hours: int,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    from pathlib import Path

    path = db_path or str(paths.TRIAGE_DB_PATH)
    if not Path(path).exists():
        return []

    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT categoria, priorita, sentiment, riassunto_breve, created_at
                FROM tickets
                WHERE lower(cliente_nome) = lower(?)
                  AND datetime(created_at) >= datetime(?)
                ORDER BY created_at DESC
                """,
                (cliente_nome, cutoff_str),
            )
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []


def count_angry_technical_tickets(records: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in records
        if (row.get("categoria") or "").upper() == "IT"
        and (row.get("sentiment") or "").upper() == "ARRABBIATO"
    )


def search_long_term_history_sql(
    cliente_nome: str,
    hours: int = 24,
    db_path: str | None = None,
) -> str:
    """
    TOOL LONG-TERM MEMORY: sfrutta l'indice SQL per estrarre gli ultimi record
    di triage associati a questo specifico mittente.
    """
    path = db_path or str(paths.TRIAGE_DB_PATH)
    if db_path is None and not paths.TRIAGE_DB_PATH.exists():
        return f"Nessun record storico trovato per {cliente_nome}."

    records = _load_sqlite_records(cliente_nome, hours, path)
    if not records:
        return (
            f"Nessun ticket processato per '{cliente_nome}' nelle ultime {hours} ore."
        )

    by_category: dict[str, int] = {}
    by_sentiment: dict[str, int] = {}
    for row in records:
        cat = (row.get("categoria") or "N/D").upper()
        sent = (row.get("sentiment") or "N/D").upper()
        by_category[cat] = by_category.get(cat, 0) + 1
        by_sentiment[sent] = by_sentiment.get(sent, 0) + 1

    angry_technical = count_angry_technical_tickets(records)
    recent = records[:3]
    lines = [
        f"Storico Cliente Rilevato in DB: '{cliente_nome}' (ultime {hours}h): {len(records)} ticket.",
        f"Per categoria: {by_category}.",
        f"Per sentiment: {by_sentiment}.",
        f"Ticket IT con sentiment ARRABBIATO: {angry_technical}.",
        f"Ultimi {len(recent)} record: {recent}",
    ]
    if angry_technical >= _REPEAT_ESCALATION_THRESHOLD:
        lines.append(
            "ATTENZIONE: cliente ad alto rischio — escalation manager consigliata (priority 4)."
        )
    return " ".join(lines)


def should_escalate_repeat_customer_sql(
    cliente_nome: str,
    hours: int = 24,
    db_path: str | None = None,
) -> bool:
    """True se >=4 ticket IT+ARRABBIATO nel database SQLite."""
    records = _load_sqlite_records(cliente_nome, hours, db_path)
    return count_angry_technical_tickets(records) >= _REPEAT_ESCALATION_THRESHOLD
