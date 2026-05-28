import json
from datetime import UTC, datetime, timedelta

from tools.history_tools import (
    count_angry_technical_tickets,
    search_long_term_history,
    should_escalate_repeat_customer,
)


def _write_processed(path, cliente, categoria, sentiment, hours_ago=1):
    ts = (datetime.now(UTC) - timedelta(hours=hours_ago)).isoformat()
    entry = {
        "timestamp": ts,
        "event_type": "ticket_processed",
        "payload": {
            "cliente_nome": cliente,
            "sentiment": sentiment,
            "ticket": {
                "categoria": categoria,
                "priorita": "HIGH",
                "riassunto_breve": "test",
            },
        },
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def test_search_long_term_history_counts(tmp_path):
    log_file = tmp_path / "activity.jsonl"
    for i in range(4):
        _write_processed(log_file, "Marco", "IT", "ARRABBIATO", hours_ago=0.5 + i * 0.1)

    result = search_long_term_history("Marco", hours=24, log_path=log_file)
    assert "Marco" in result
    assert "4" in result
    assert "ARRABBIATO" in result


def test_should_escalate_repeat_customer(tmp_path, monkeypatch):
    log_file = tmp_path / "activity.jsonl"
    monkeypatch.setattr("tools.history_tools.LOG_FILE_PATH", log_file)
    for i in range(4):
        _write_processed(log_file, "Marco", "IT", "ARRABBIATO")

    assert should_escalate_repeat_customer("Marco", hours=24) is True
    assert should_escalate_repeat_customer("Altro", hours=24) is False


def test_count_angry_technical():
    records = [
        {"categoria": "IT", "sentiment": "ARRABBIATO"},
        {"categoria": "IT", "sentiment": "NEUTRO"},
        {"categoria": "SALES", "sentiment": "ARRABBIATO"},
    ]
    assert count_angry_technical_tickets(records) == 1
