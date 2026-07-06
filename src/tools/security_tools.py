"""Tool di sicurezza SOC — stub didattico Lezione 18."""

from __future__ import annotations

from tools.logger import log_event


def isolate_account(account_name: str, reason: str) -> str:
    """
    Stub no-op per isolamento account AD (implementazione completa nel progettino SOC).
    Sempre invocato tramite tool_policy_gate in pipeline multi-agent.
    """
    log_event(
        "isolate_account_stub",
        {
            "account_name": account_name,
            "reason": reason[:200],
        },
    )
    return (
        f"[STUB L18] Isolamento account '{account_name}' registrato (no-op). "
        f"Motivo: {reason[:120]}"
    )
