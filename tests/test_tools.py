from tools.history_tools import search_long_term_history
from tools.office_tools import notify_manager, search_policy
from tools.registry import TOOL_MAP


def test_search_policy_reads_file():
    result = search_policy("sconto")
    assert "sconto" in result.lower() or "10.000" in result or "10k" in result.lower()


def test_search_policy_sentiment_escalation():
    result = search_policy("sentiment ARRABBIATO escalation")
    assert "ARRABBIATO" in result or "notify_manager" in result


def test_notify_manager_and_registry():
    assert set(TOOL_MAP) == {
        "notify_manager",
        "search_policy",
        "search_long_term_history",
    }
    assert "successo" in notify_manager("VIP 15k", 4).lower()


def test_search_long_term_history_empty(tmp_path):
    log_file = tmp_path / "empty.jsonl"
    log_file.write_text("", encoding="utf-8")
    result = search_long_term_history("Marco", hours=24, log_path=log_file)
    assert "Nessun ticket" in result
