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
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS access_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                cliente_nome TEXT NOT NULL,
                event_type TEXT NOT NULL,
                location TEXT,
                attempts INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_access_cliente ON access_events(cliente_nome)"
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS authorized_identities (
                account_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                can_request_ad_changes INTEGER DEFAULT 0,
                verified_channel TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS isolated_accounts (
                account_id TEXT PRIMARY KEY,
                reason TEXT NOT NULL,
                isolated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def account_to_email(full_name: str) -> str:
    """Converte «Nome Cognome» in account_id aziendale standard."""
    parts = full_name.strip().lower().split()
    if len(parts) >= 2:
        local = f"{parts[0]}.{parts[-1]}"
    elif parts:
        local = parts[0]
    else:
        local = "unknown"
    return f"{local}@impesud.it"


def _load_access_events(
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
                SELECT account_id, event_type, location, attempts, created_at
                FROM access_events
                WHERE lower(cliente_nome) = lower(?)
                  AND datetime(created_at) >= datetime(?)
                ORDER BY created_at DESC
                """,
                (cliente_nome, cutoff_str),
            )
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []


def isolate_account_sql(account_id: str, reason: str, db_path: str | None = None) -> str:
    """Registra l'isolamento di un account AD nel database SQLite."""
    path = db_path or str(paths.TRIAGE_DB_PATH)
    init_db(path)
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO isolated_accounts (account_id, reason, isolated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (account_id, reason),
        )
        conn.commit()
    return (
        f"Account {account_id} isolato con successo. "
        f"Motivo: {reason}. Revocare sessioni attive e avviare procedura SOC."
    )


def verify_sender_identity_sql(
    claimed_name: str,
    claimed_role: str,
    db_path: str | None = None,
) -> str:
    """
    Verifica identità dichiarata contro authorized_identities (scenario 9 whaling).

    Returns:
        Esito testuale VERIFIED o SPOOFING_SUSPECTED per l'osservazione ReAct.
    """
    path = db_path or str(paths.TRIAGE_DB_PATH)
    init_db(path)
    role_upper = claimed_role.strip().upper()
    name_lower = claimed_name.strip().lower()

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT account_id, display_name, role, can_request_ad_changes, verified_channel
            FROM authorized_identities
            WHERE upper(role) = ?
            """,
            (role_upper,),
        )
        rows = [dict(row) for row in cursor.fetchall()]

    if not rows:
        return (
            f"SPOOFING_SUSPECTED: nessuna identità autorizzata con ruolo '{claimed_role}' "
            f"nel registro. Non eseguire richieste privilegiate AD via chat."
        )

    for row in rows:
        display = (row.get("display_name") or "").lower()
        if role_upper == "CEO" and "ceo" in name_lower:
            channel = row.get("verified_channel") or "canale formale"
            can_ad = row.get("can_request_ad_changes", 0)
            return (
                f"VERIFIED parziale: ruolo CEO presente in registro ({row['account_id']}), "
                f"canale verificato: {channel}. "
                f"can_request_ad_changes={can_ad}. "
                "POLICY: disattivazione restrizioni AD per consulenti esterni VIETATA via chat. "
                "Rifiutare la richiesta e aprire ticket formale SOC."
            )

    return (
        f"SPOOFING_SUSPECTED: dichiarazione '{claimed_name}' / ruolo '{claimed_role}' "
        "non corrisponde a identità verificate nel registro."
    )


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
    access_events = _load_access_events(cliente_nome, hours, path)

    if not records and not access_events:
        return (
            f"Nessun ticket processato per '{cliente_nome}' nelle ultime {hours} ore."
        )

    if not records and access_events:
        total_attempts = sum(e.get("attempts") or 0 for e in access_events)
        locations = {e.get("location") for e in access_events if e.get("location")}
        return (
            f"Storico Cliente '{cliente_nome}' (ultime {hours}h): nessun ticket, "
            f"ma {len(access_events)} eventi accesso anomali ({total_attempts} tentativi), "
            f"località: {locations}. Dettaglio: {access_events[:5]}"
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
    access_events = _load_access_events(cliente_nome, hours, path)
    lines = [
        f"Storico Cliente Rilevato in DB: '{cliente_nome}' (ultime {hours}h): {len(records)} ticket.",
        f"Per categoria: {by_category}.",
        f"Per sentiment: {by_sentiment}.",
        f"Ticket IT con sentiment ARRABBIATO: {angry_technical}.",
        f"Ultimi {len(recent)} record: {recent}",
    ]
    if access_events:
        total_attempts = sum(e.get("attempts") or 0 for e in access_events)
        locations = {e.get("location") for e in access_events if e.get("location")}
        lines.append(
            f"Eventi accesso anomali: {len(access_events)} record, "
            f"{total_attempts} tentativi totali, località: {locations}. "
            f"Dettaglio: {access_events[:5]}"
        )
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
