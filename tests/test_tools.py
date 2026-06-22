from unittest.mock import MagicMock, patch

import chromadb
import paths
from rag.chroma_store import reset_policy_store, set_chroma_client
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


def _reset_chroma_for_policy_test() -> None:
    reset_policy_store()
    set_chroma_client(chromadb.EphemeralClient())


def test_search_policy_reads_file():
    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = _mock_embeddings_create

    _reset_chroma_for_policy_test()
    with patch("rag.policy_semantic.get_client", return_value=mock_client):
        result = search_policy("sconto")

    assert (
        "[RAG semantica" in result
        or "sconto" in result.lower()
        or "10.000" in result
        or "10k" in result.lower()
        or "Enterprise" in result
    )


def test_search_policy_sentiment_escalation():
    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = _mock_embeddings_create

    _reset_chroma_for_policy_test()
    with patch("rag.policy_semantic.get_client", return_value=mock_client):
        result = search_policy("sentiment ARRABBIATO escalation")

    assert (
        "ARRABBIATO" in result
        or "notify_manager" in result
        or "escalation" in result.lower()
        or "priorità 4" in result.lower()
    )


def test_notify_manager_and_registry():
    assert set(TOOL_MAP) == {
        "notify_manager",
        "search_policy",
        "search_long_term_history",
        "isolate_account",
        "verify_sender_identity",
    }
    assert "successo" in notify_manager("VIP 15k", 4).lower()


def test_search_long_term_history_empty(tmp_path, monkeypatch):
    db_file = tmp_path / "empty.db"
    monkeypatch.setattr(paths, "TRIAGE_DB_PATH", db_file)
    result = search_long_term_history("Marco", hours=24)
    assert "Nessun ticket" in result or "Nessun record storico" in result
