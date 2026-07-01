#!/usr/bin/env python3
"""Inizializza data/triage_system.db (Lezione 13). Eseguire dopo checkout su branch L13/L14/L15."""

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
        if cursor.fetchone():
            print("[SQLite] Indice idx_cliente su tickets(cliente_nome): OK")
        else:
            print("[SQLite] ATTENZIONE: indice idx_cliente non trovato", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
