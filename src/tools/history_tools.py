"""Long-term memory: ricerca storico ticket da logs/activity.jsonl."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from paths import LOG_FILE_PATH

_REPEAT_ESCALATION_THRESHOLD = 4


def _parse_timestamp(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_ticket_processed_records(
    log_path: Path,
    cliente_nome: str,
    hours: int,
) -> list[dict[str, Any]]:
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    target = cliente_nome.strip().lower()
    records: list[dict[str, Any]] = []

    if not log_path.exists():
        return records

    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("event_type") != "ticket_processed":
                continue
            payload = entry.get("payload") or {}
            name = (payload.get("cliente_nome") or "").strip().lower()
            if not name or name != target:
                continue
            ts = _parse_timestamp(entry.get("timestamp", ""))
            if ts is None or ts < cutoff:
                continue
            ticket = payload.get("ticket") or {}
            records.append(
                {
                    "timestamp": entry.get("timestamp"),
                    "categoria": ticket.get("categoria") or payload.get("categoria"),
                    "priorita": ticket.get("priorita") or payload.get("priorita"),
                    "sentiment": payload.get("sentiment"),
                    "riassunto_breve": ticket.get("riassunto_breve"),
                }
            )
    return records


def count_angry_technical_tickets(records: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in records
        if (row.get("categoria") or "").upper() == "IT"
        and (row.get("sentiment") or "").upper() == "ARRABBIATO"
    )


def search_long_term_history(
    cliente_nome: str,
    hours: int = 24,
    log_path: Path | None = None,
) -> str:
    path = log_path or LOG_FILE_PATH
    records = _load_ticket_processed_records(path, cliente_nome, hours)
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
    lines = [
        f"Storico cliente '{cliente_nome}' (ultime {hours}h): {len(records)} ticket.",
        f"Per categoria: {by_category}.",
        f"Per sentiment: {by_sentiment}.",
        f"Ticket IT con sentiment ARRABBIATO: {angry_technical}.",
    ]
    if angry_technical >= _REPEAT_ESCALATION_THRESHOLD:
        lines.append(
            "ATTENZIONE: cliente ad alto rischio — escalation manager consigliata (priority 4)."
        )
    summaries = [r.get("riassunto_breve") for r in records[-3:] if r.get("riassunto_breve")]
    if summaries:
        lines.append("Ultimi riassunti: " + "; ".join(summaries))
    return " ".join(lines)


def should_escalate_repeat_customer(
    cliente_nome: str,
    hours: int = 24,
    log_path: Path | None = None,
) -> bool:
    """True se >=4 ticket IT+ARRABBIATO nel log indicato (default: LOG_FILE_PATH del modulo)."""
    path = log_path or LOG_FILE_PATH
    records = _load_ticket_processed_records(path, cliente_nome, hours)
    return count_angry_technical_tickets(records) >= _REPEAT_ESCALATION_THRESHOLD
