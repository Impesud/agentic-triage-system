import sqlite3

import paths
from tools.logger import (
    init_db,
    log_triage_to_sqlite,
    search_long_term_history_sql,
    should_escalate_repeat_customer_sql,
)


def test_init_db_creates_table_and_index(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(paths, "TRIAGE_DB_PATH", db_file)

    init_db()

    with sqlite3.connect(str(db_file)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_cliente'"
        )
        assert cursor.fetchone() is not None


def test_log_and_search_case_insensitive(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(paths, "TRIAGE_DB_PATH", db_file)

    log_triage_to_sqlite(
        {
            "cliente_nome": "Marco Rossi",
            "categoria": "SALES",
            "priorita": "HIGH",
            "sentiment": "NEUTRALE",
            "riassunto_breve": "Budget AI 15k",
            "lingua": "Italiano",
            "azione_eseguita": "notify_manager",
        }
    )

    result = search_long_term_history_sql("marco rossi", hours=24)
    assert "Marco Rossi" in result or "marco rossi" in result.lower()
    assert "SALES" in result
    assert "Budget AI 15k" in result


def test_should_escalate_repeat_customer_sql(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(paths, "TRIAGE_DB_PATH", db_file)

    for i in range(4):
        log_triage_to_sqlite(
            {
                "cliente_nome": "Marco",
                "categoria": "IT",
                "priorita": "HIGH",
                "sentiment": "ARRABBIATO",
                "riassunto_breve": f"Incidente #{i + 1}",
                "lingua": "Italiano",
                "azione_eseguita": "Nessuna",
            }
        )

    assert should_escalate_repeat_customer_sql("Marco", hours=24) is True
    assert should_escalate_repeat_customer_sql("Altro", hours=24) is False
