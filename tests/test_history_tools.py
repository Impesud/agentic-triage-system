import paths
from tools.history_tools import (
    count_angry_technical_tickets,
    search_long_term_history,
    should_escalate_repeat_customer,
)
from tools.logger import log_triage_to_sqlite


def _seed_marco_it_angry(db_file, n: int = 4) -> None:
    for i in range(n):
        log_triage_to_sqlite(
            {
                "cliente_nome": "Marco",
                "categoria": "IT",
                "priorita": "HIGH",
                "sentiment": "ARRABBIATO",
                "riassunto_breve": f"Incidente #{i + 1}",
                "lingua": "Italiano",
                "azione_eseguita": "Nessuna",
            },
            db_path=str(db_file),
        )


def test_search_long_term_history_counts(tmp_path, monkeypatch):
    db_file = tmp_path / "history.db"
    monkeypatch.setattr(paths, "TRIAGE_DB_PATH", db_file)
    _seed_marco_it_angry(db_file, 4)

    result = search_long_term_history("Marco", hours=24)
    assert "Marco" in result
    assert "4" in result
    assert "ARRABBIATO" in result


def test_should_escalate_repeat_customer(tmp_path, monkeypatch):
    db_file = tmp_path / "history.db"
    monkeypatch.setattr(paths, "TRIAGE_DB_PATH", db_file)
    _seed_marco_it_angry(db_file, 4)

    assert should_escalate_repeat_customer("Marco", hours=24) is True
    assert should_escalate_repeat_customer("Altro", hours=24) is False


def test_should_escalate_isolated_db(tmp_path, monkeypatch):
    seeded = tmp_path / "seeded.db"
    empty = tmp_path / "empty.db"
    _seed_marco_it_angry(seeded, 4)

    monkeypatch.setattr(paths, "TRIAGE_DB_PATH", seeded)
    assert should_escalate_repeat_customer("Marco", hours=24) is True

    monkeypatch.setattr(paths, "TRIAGE_DB_PATH", empty)
    assert should_escalate_repeat_customer("Marco", hours=24) is False


def test_count_angry_technical():
    records = [
        {"categoria": "IT", "sentiment": "ARRABBIATO"},
        {"categoria": "IT", "sentiment": "NEUTRO"},
        {"categoria": "SALES", "sentiment": "ARRABBIATO"},
    ]
    assert count_angry_technical_tickets(records) == 1
