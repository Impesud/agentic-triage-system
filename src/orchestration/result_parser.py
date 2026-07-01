"""Parsing e fallback output multi-agent (Lezione 16)."""

from __future__ import annotations

from typing import Any

from parsing.parser import parse_llm_output
from schemas.ticket import TriageResult
from tools.logger import log_event


def finalize_multi_agent_output(raw_output: str, user_input: str) -> TriageResult:
    """Valida l'output del Resolver; fallback strutturato se JSON invalido."""
    try:
        result = parse_llm_output(raw_output)
        if not result.messaggio_originale.strip():
            result = result.model_copy(update={"messaggio_originale": user_input})
        return result
    except ValueError as exc:
        log_event(
            "multi_agent_fallback",
            {
                "reason": str(exc),
                "input_preview": user_input[:200],
                "output_preview": raw_output[:400],
            },
        )
        from logic import _emergency_triage_result

        fallback = _emergency_triage_result(user_input)
        return fallback.model_copy(
            update={
                "azione_eseguita": "Fallback orchestrazione multi-agent (JSON invalido)",
                "analisi_problema": (
                    f"1. Problema: output Resolver non valido. "
                    f"2. Contesto: {exc}. "
                    "3. Categoria: GENERAL. 4. Priorità: CRITICAL."
                ),
            }
        )


def extract_json_candidate_from_messages(messages: list[Any]) -> str:
    """Estrae l'ultimo contenuto testuale utile da messaggi AutoGen."""
    for message in reversed(messages):
        content = getattr(message, "content", None)
        if isinstance(content, str) and "{" in content:
            return content
        if content is not None and not isinstance(content, str):
            text = str(content)
            if "{" in text:
                return text
    raise ValueError("Nessun JSON trovato nei messaggi del team AutoGen")
