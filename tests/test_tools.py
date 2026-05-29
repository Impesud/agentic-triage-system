from unittest.mock import MagicMock, patch

from tools.history_tools import search_long_term_history
from tools.office_tools import notify_manager, search_policy
from tools.registry import TOOL_MAP


def _embedding_for_text(text: str) -> list[float]:
    lower = text.lower()
    if any(k in lower for k in ("sconto", "budget", "10.000", "enterprise")):
        return [0.0, 1.0, 0.0]
    if any(k in lower for k in ("sentiment", "arrabbiato", "escalation", "notify_manager")):
        return [0.0, 0.0, 1.0]
    return [0.0, 0.0, 0.0]


def _mock_embeddings_create(*_args, input: list[str], **_kwargs):
    data = []
    for i, text in enumerate(input):
        item = MagicMock()
        item.embedding = _embedding_for_text(text)
        item.index = i
        data.append(item)
    response = MagicMock()
    response.data = data
    return response


def test_search_policy_reads_file():
    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = _mock_embeddings_create

    from rag.policy_semantic import clear_policy_index_cache

    with patch("rag.policy_semantic.get_client", return_value=mock_client):
        clear_policy_index_cache()
        result = search_policy("sconto")

    assert (
        "sconto" in result.lower()
        or "10.000" in result
        or "10k" in result.lower()
        or "Enterprise" in result
    )


def test_search_policy_sentiment_escalation():
    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = _mock_embeddings_create

    with patch("rag.policy_semantic.get_client", return_value=mock_client):
        from rag.policy_semantic import clear_policy_index_cache

        clear_policy_index_cache()
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
