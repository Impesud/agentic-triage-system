"""Compattazione prompt e stima token (Lezione 17)."""

from __future__ import annotations

_MANUALE_POINTER = (
    "MANUALE IT: già analizzato dall'Analyst nella fase precedente. "
    "Usa policy_excerpt, ltm_digest e il report Analyst nel hand-off. "
    "Richiama search_policy solo se mancano dati critici."
)


def compact_manuale_for_resolver(manuale: str, *, max_excerpt_chars: int = 0) -> str:
    """
    Riduce il manuale nel prompt Resolver quando il Blackboard è già arricchito.

    max_excerpt_chars=0 → solo puntatore (massimo risparmio token).
    """
    if max_excerpt_chars <= 0:
        return _MANUALE_POINTER
    excerpt = manuale[:max_excerpt_chars].strip()
    if len(manuale) > max_excerpt_chars:
        excerpt += f"\n[... manuale troncato, {len(manuale) - max_excerpt_chars} chars omessi]"
    return excerpt


def estimate_tokens(text: str) -> int:
    """Re-export stima token centralizzata."""
    from orchestration.message_pruning import estimate_tokens as _est

    return _est(text)
