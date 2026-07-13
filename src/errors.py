"""Eccezioni di dominio — Lezione 18 (base per Moduli 2–4 GESTIONE_ERRORI)."""


class TriageError(Exception):
    """Errore di dominio nel sistema di triage."""


class SecurityGuardrailError(TriageError):
    """Input o hand-off bloccato dal guardrail di sicurezza (Lezione 18)."""


class HitlApprovalRequired(TriageError):
    """Azione critica in pausa: richiesta approvazione operatore (Lezione 19)."""

    def __init__(self, message: str, *, session_id: str) -> None:
        super().__init__(message)
        self.session_id = session_id
