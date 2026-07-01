"""System prompt TriageAnalyst (Lezione 16)."""

from orchestration.topologies import TRIAGE_ANALYST

_JSON_HANDOFF_HINT = """
Al termine del task, restituisci un riepilogo strutturato (testo) con:
- cliente_nome (se identificato)
- sentiment (NEUTRO o ARRABBIATO)
- storico_summary (sintesi da search_long_term_history se invocato)
- analyst_notes (osservazioni per il SecurityResolver)
Non produrre il JSON finale di triage: quello è compito del Resolver.
"""


def build_analyst_system_message(manuale: str) -> str:
    """Prompt di sistema per l'agente Analyst."""
    return f"""Sei {TRIAGE_ANALYST.role} di Impesud.

{TRIAGE_ANALYST.backstory}

Obiettivo: {TRIAGE_ANALYST.goal}

Tool disponibili: {", ".join(TRIAGE_ANALYST.tools)}.
- Invoca search_long_term_history se il messaggio identifica un cliente (es. "sono Marco").

MANUALE IT (contesto operativo):
{manuale}

{_JSON_HANDOFF_HINT.strip()}
"""
