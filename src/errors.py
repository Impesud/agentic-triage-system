"""Eccezioni di dominio — Lezione 18 (base per Moduli 2–4 GESTIONE_ERRORI)."""


class TriageError(Exception):
    """Errore di dominio nel sistema di triage."""


class SecurityGuardrailError(TriageError):
    """Input o hand-off bloccato dal guardrail di sicurezza (Lezione 18)."""
