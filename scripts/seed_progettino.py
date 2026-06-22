#!/usr/bin/env python3
"""
Seed dati Progetto 2 — prepara SQLite per gli scenari dataset_test.

Popola:
- Luca Verdi: ticket storico SECURITY (scenario 1)
- Matteo Neri: 15 eventi failed_login da Singapore (scenario 4)
- CEO: record authorized_identities (scenario 9)
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from paths import TRIAGE_DB_PATH
from tools.logger import init_db, log_triage_to_sqlite


def _insert_access_events(conn: sqlite3.Connection, cliente: str, account_id: str) -> None:
    """Inserisce 15 tentativi di login falliti da Singapore (ultimi 10 minuti)."""
    cursor = conn.cursor()
    now = datetime.now(UTC)
    for i in range(15):
        ts = (now - timedelta(minutes=9, seconds=i * 30)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT INTO access_events
                (account_id, cliente_nome, event_type, location, attempts, created_at)
            VALUES (?, ?, 'failed_login', 'Singapore', 1, ?)
            """,
            (account_id, cliente, ts),
        )


def _insert_identities(conn: sqlite3.Connection) -> None:
    """Registro identità per verifica whaling CEO (scenario 9)."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO authorized_identities
            (account_id, display_name, role, can_request_ad_changes, verified_channel)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "ceo@impesud.it",
            "Amministratore Delegato Impesud",
            "CEO",
            0,
            "ticket_formale_soc",
        ),
    )


def seed_progettino(db_path: Path | None = None, reset: bool = True) -> Path:
    """
    Inizializza e popola il database per il Progetto 2.

    Args:
        db_path: Percorso SQLite (default data/triage_system.db).
        reset: Se True, elimina il file esistente prima del seed.

    Returns:
        Percorso del database popolato.
    """
    path = db_path or TRIAGE_DB_PATH
    if reset and path.exists():
        path.unlink()

    init_db(str(path))

    log_triage_to_sqlite(
        {
            "cliente_nome": "Luca Verdi",
            "categoria": "SECURITY",
            "priorita": "MEDIUM",
            "sentiment": "NEUTRO",
            "riassunto_breve": "Precedente segnalazione mail HR sospetta",
            "lingua": "Italiano",
            "azione_eseguita": "search_policy",
        },
        db_path=str(path),
    )

    with sqlite3.connect(str(path)) as conn:
        _insert_access_events(conn, "Matteo Neri", "matteo.neri@impesud.it")
        _insert_identities(conn)
        conn.commit()

    print(f"[SEED Progetto 2] Database pronto: {path}")
    return path


def main() -> int:
    seed_progettino()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
