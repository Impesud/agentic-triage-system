"""Long-term memory: ricerca storico ticket da SQLite indicizzato (Lezione 13)."""

from pathlib import Path
from typing import Any

from tools.logger import (
    count_angry_technical_tickets,
    search_long_term_history_sql,
    should_escalate_repeat_customer_sql,
)

__all__ = [
    "count_angry_technical_tickets",
    "search_long_term_history",
    "should_escalate_repeat_customer",
]


def search_long_term_history(
    cliente_nome: str,
    hours: int = 24,
    log_path: Path | None = None,
) -> str:
    """
    Cerca lo storico cliente nel database SQLite indicizzato.
    Il parametro log_path è ignorato (compatibilità demo/test L9–L12).
    """
    _ = log_path  # deprecato: LTM su SQLite da Lezione 13
    return search_long_term_history_sql(cliente_nome, hours=hours)


def should_escalate_repeat_customer(
    cliente_nome: str,
    hours: int = 24,
    log_path: Path | None = None,
) -> bool:
    """True se >=4 ticket IT+ARRABBIATO nel database SQLite."""
    _ = log_path  # deprecato: LTM su SQLite da Lezione 13
    return should_escalate_repeat_customer_sql(cliente_nome, hours=hours)
