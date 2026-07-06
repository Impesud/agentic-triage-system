"""Facade guardrail pre-pipeline — Lezione 18."""

from __future__ import annotations

from errors import SecurityGuardrailError
from orchestration.input_guardrail import GuardrailResult, input_excerpt, scan_ticket_input
from orchestration.security_store import log_security_alert
from tools.logger import log_event


def _alert_type_for_result(result: GuardrailResult) -> str:
    vectors = {m.vector.value for m in result.matches}
    if "tool_hijack" in vectors:
        return "TOOL_HIJACK"
    if "policy_override" in vectors or "direct_injection" in vectors:
        return "INPUT_INJECTION"
    if "log_suppression" in vectors:
        return "LOG_SUPPRESSION"
    if "role_override" in vectors:
        return "ROLE_OVERRIDE"
    return "INPUT_BLOCKED"


def guard_ticket_input(user_input: str, *, stage: str = "pre_pipeline") -> GuardrailResult:
    """
    Scansiona l'input; se bloccato persiste allerta SQLite e solleva SecurityGuardrailError.
    """
    result = scan_ticket_input(user_input)
    if result.allowed:
        return result

    excerpt = input_excerpt(user_input)
    primary_pattern = result.matches[0].pattern if result.matches else None
    alert_type = _alert_type_for_result(result)
    vectors = [m.vector.value for m in result.matches]

    alert_id = log_security_alert(
        alert_type=alert_type,
        severity=result.highest_severity,
        blocked_stage=stage,
        matched_pattern=primary_pattern,
        input_excerpt=excerpt,
        payload={"vectors": vectors, "match_count": len(result.matches)},
    )
    log_event(
        "security_input_blocked",
        {
            "stage": stage,
            "alert_id": alert_id,
            "severity": result.highest_severity,
            "vectors": vectors,
            "input_excerpt": excerpt,
        },
    )
    raise SecurityGuardrailError(
        f"Input bloccato dal guardrail ({alert_type}): {excerpt}"
    )
