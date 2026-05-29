"""
RAG semantica su data/policy.txt — Lezione 10.

Pipeline: paragraph chunking → embeddings OpenAI → cosine similarity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from client import get_client

EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_THRESHOLD = 0.38


@dataclass(frozen=True)
class PolicyChunk:
    """Frammento di policy con embedding pre-calcolato."""

    text: str
    embedding: tuple[float, ...]


@dataclass(frozen=True)
class SemanticSearchResult:
    """Risultato della ricerca semantica su un chunk."""

    chunk_text: str
    score: float


# Cache in-process: path policy → lista chunk vettorizzati
_policy_index_cache: dict[Path, list[PolicyChunk]] = {}


def chunk_policy(text: str) -> list[str]:
    """Paragraph chunking: split su doppia interruzione di riga."""
    raw_chunks = text.split("\n\n")
    return [chunk.strip() for chunk in raw_chunks if chunk.strip()]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Similarità del coseno tra due vettori densi."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_texts(client: Any, texts: list[str]) -> list[list[float]]:
    """Genera embeddings batched tramite OpenAI."""
    if not texts:
        return []
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def _load_policy_chunks(policy_path: Path) -> list[str]:
    if not policy_path.exists():
        return []
    return chunk_policy(policy_path.read_text(encoding="utf-8"))


def _build_policy_index(policy_path: Path) -> list[PolicyChunk]:
    """Costruisce (e cachea) l'indice vettoriale dei chunk policy."""
    resolved = policy_path.resolve()
    if resolved in _policy_index_cache:
        return _policy_index_cache[resolved]

    chunks = _load_policy_chunks(resolved)
    if not chunks:
        _policy_index_cache[resolved] = []
        return []

    client = get_client()
    embeddings = embed_texts(client, chunks)
    indexed = [
        PolicyChunk(text=text, embedding=tuple(vec))
        for text, vec in zip(chunks, embeddings, strict=True)
    ]
    _policy_index_cache[resolved] = indexed
    return indexed


def clear_policy_index_cache() -> None:
    """Svuota la cache (utile nei test)."""
    _policy_index_cache.clear()


def semantic_policy_search(
    query: str,
    policy_path: Path,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    top_k: int = 1,
) -> SemanticSearchResult | None:
    """
    Cerca il chunk policy più simile alla query.

    Restituisce None se nessun chunk supera la soglia.
    """
    indexed = _build_policy_index(policy_path)
    if not indexed:
        return None

    client = get_client()
    query_vec = embed_texts(client, [query])[0]

    scored: list[tuple[float, PolicyChunk]] = []
    for chunk in indexed:
        score = cosine_similarity(query_vec, list(chunk.embedding))
        scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_chunk = scored[0]

    if best_score < threshold:
        return None

    return SemanticSearchResult(chunk_text=best_chunk.text, score=best_score)


def format_semantic_result(result: SemanticSearchResult) -> str:
    """Formatta chunk + score per l'observation del tool."""
    return (
        f"[RAG semantica | score={result.score:.3f}]\n"
        f"{result.chunk_text}"
    )
