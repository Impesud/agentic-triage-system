"""Test RAG semantica — Lezione 10."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rag.policy_semantic import (
    chunk_policy,
    clear_policy_index_cache,
    cosine_similarity,
    semantic_policy_search,
)
from tools.office_tools import search_policy


def _embedding_for_text(text: str) -> list[float]:
    """Vettori deterministici per bucket semantici (solo test)."""
    lower = text.lower()
    if any(k in lower for k in ("recesso", "rimborso", "14 giorni", "ripensamento")):
        return [1.0, 0.0, 0.0]
    if any(k in lower for k in ("sconto", "budget", "10.000", "enterprise")):
        return [0.0, 1.0, 0.0]
    if any(k in lower for k in ("sentiment", "arrabbiato", "escalation", "notify_manager")):
        return [0.0, 0.0, 1.0]
    if any(k in lower for k in ("annullare", "riavere", "soldi", "contratto")):
        return [0.98, 0.2, 0.0]
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


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_policy_index_cache()
    yield
    clear_policy_index_cache()


def test_chunk_policy_paragraph_split():
    text = "Paragrafo A sui rimborsi.\n\nParagrafo B sugli sconti.\n\n"
    chunks = chunk_policy(text)
    assert len(chunks) == 2
    assert "rimborsi" in chunks[0]
    assert "sconti" in chunks[1]


def test_cosine_similarity_identical_vectors():
    vec = [1.0, 2.0, 3.0]
    assert cosine_similarity(vec, vec) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_semantic_policy_search_synonym_match(tmp_path: Path):
    policy = tmp_path / "policy.txt"
    policy.write_text(
        "1. Sconti: max 5% su progetti Enterprise.\n\n"
        "2. Recesso per ripensamento: valido entro 14 giorni dalla firma del contratto.\n\n"
        "3. Sentiment ARRABBIATO: escalation immediata con notify_manager.\n",
        encoding="utf-8",
    )

    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = _mock_embeddings_create

    with patch("rag.policy_semantic.get_client", return_value=mock_client):
        result = semantic_policy_search(
            "Voglio annullare il contratto e riavere i soldi",
            policy,
            threshold=0.38,
        )

    assert result is not None
    assert "14 giorni" in result.chunk_text or "recesso" in result.chunk_text.lower()
    assert result.score >= 0.38


def test_semantic_policy_search_below_threshold(tmp_path: Path):
    policy = tmp_path / "policy.txt"
    policy.write_text("Solo testo generico senza match.\n\n", encoding="utf-8")

    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = _mock_embeddings_create

    with patch("rag.policy_semantic.get_client", return_value=mock_client):
        result = semantic_policy_search("query irrilevante xyz", policy, threshold=0.99)

    assert result is None


def test_search_policy_uses_semantic_path(tmp_path: Path, monkeypatch):
    policy = tmp_path / "policy.txt"
    policy.write_text(
        "Rimborsi entro 14 giorni.\n\n"
        "Recesso per ripensamento entro 14 giorni dalla firma.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("tools.office_tools.POLICY_PATH", policy)

    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = _mock_embeddings_create

    with patch("rag.policy_semantic.get_client", return_value=mock_client):
        result = search_policy("annullare contratto e riavere i soldi")

    assert "[RAG semantica" in result
    assert "14 giorni" in result or "recesso" in result.lower()


def test_search_policy_fallback_on_api_error(monkeypatch):
    monkeypatch.setattr(
        "tools.office_tools.semantic_policy_search",
        MagicMock(side_effect=ValueError("no api key")),
    )
    result = search_policy("sconto")
    assert "sconto" in result.lower() or "10" in result
