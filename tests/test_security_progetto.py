"""Test unitari tool e logger Progetto 2."""

import sqlite3

import pytest

from tools.logger import (
    account_to_email,
    init_db,
    search_long_term_history_sql,
    verify_sender_identity_sql,
)


def test_account_to_email():
    assert account_to_email("Luca Verdi") == "luca.verdi@impesud.it"
    assert account_to_email("Matteo Neri") == "matteo.neri@impesud.it"


def test_verify_sender_identity_ceo(tmp_path):
    db = tmp_path / "t.db"
    init_db(str(db))
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO authorized_identities
            (account_id, display_name, role, can_request_ad_changes, verified_channel)
            VALUES ('ceo@impesud.it', 'CEO Impesud', 'CEO', 0, 'formale')
            """
        )
        conn.commit()
    result = verify_sender_identity_sql("CEO dell'azienda", "CEO", db_path=str(db))
    assert "VERIFIED" in result or "SPOOFING" in result
    assert "VIETATA" in result or "vietata" in result.lower()


def test_search_history_includes_access_events(tmp_path):
    db = tmp_path / "t.db"
    init_db(str(db))
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO access_events
            (account_id, cliente_nome, event_type, location, attempts)
            VALUES ('matteo.neri@impesud.it', 'Matteo Neri', 'failed_login', 'Singapore', 15)
            """
        )
        conn.commit()
    out = search_long_term_history_sql("Matteo Neri", hours=24, db_path=str(db))
    assert "Singapore" in out
    assert "accesso anomali" in out.lower() or "access_events" in out.lower() or "anomali" in out.lower()
