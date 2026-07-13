#!/usr/bin/env python3
"""Inizializza data/triage_system.db (Lezione 13+). Eseguire dopo checkout su branch L13–L19."""

from __future__ import annotations

import sqlite3
import sys

from paths import TRIAGE_DB_PATH
from tools.logger import init_db


def main() -> int:
    init_db()
    print(f"[SQLite] Database pronto: {TRIAGE_DB_PATH}")

    with sqlite3.connect(str(TRIAGE_DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_cliente'"
        )
        if not cursor.fetchone():
            print("[SQLite] ATTENZIONE: indice idx_cliente non trovato", file=sys.stderr)
            return 1
        print("[SQLite] Indice idx_cliente su tickets(cliente_nome): OK")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='security_alerts'"
        )
        if not cursor.fetchone():
            print("[SQLite] ATTENZIONE: tabella security_alerts non trovata", file=sys.stderr)
            return 1
        print("[SQLite] Tabella security_alerts (L18): OK")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_security_alerts_type'"
        )
        if not cursor.fetchone():
            print(
                "[SQLite] ATTENZIONE: indice idx_security_alerts_type non trovato",
                file=sys.stderr,
            )
            return 1
        print("[SQLite] Indice idx_security_alerts_type: OK")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ticket_states'"
        )
        if not cursor.fetchone():
            print("[SQLite] ATTENZIONE: tabella ticket_states non trovata", file=sys.stderr)
            return 1
        print("[SQLite] Tabella ticket_states (L19): OK")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_ticket_states_status'"
        )
        if not cursor.fetchone():
            print(
                "[SQLite] ATTENZIONE: indice idx_ticket_states_status non trovato",
                file=sys.stderr,
            )
            return 1
        print("[SQLite] Indice idx_ticket_states_status: OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
