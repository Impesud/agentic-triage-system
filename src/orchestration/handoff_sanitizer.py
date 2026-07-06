"""Sanitizzazione SharedHandoffContext — Lezione 18 (injection indiretta)."""

from __future__ import annotations

from dataclasses import dataclass, field

from errors import SecurityGuardrailError
from orchestration.input_guardrail import input_excerpt, scan_ticket_input
from orchestration.models import SharedHandoffContext
from orchestration.security_store import log_security_alert
from tools.logger import log_event

CRITICAL_HANDOFF_FIELDS = ("policy_excerpt", "ltm_digest", "analyst_notes")
SOFT_HANDOFF_FIELDS = ("storico_summary", "ticket_message")


@dataclass
class SanitizeResult:
    context: SharedHandoffContext
    blocked: bool = False
    redacted_fields: list[str] = field(default_factory=list)
    matches: list[str] = field(default_factory=list)


def _field_text(ctx: SharedHandoffContext, field_name: str) -> str | None:
    value = getattr(ctx, field_name, None)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def strip_injection_markers(text: str) -> str:
    """Rimuove frasi di injection note (modalità soft su campi non critici)."""
    from orchestration.input_guardrail import ATTACK_PATTERNS

    cleaned = text
    for pattern, _, _ in ATTACK_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


def sanitize_handoff(ctx: SharedHandoffContext) -> SanitizeResult:
    """
    Scansiona i campi del Blackboard.
    Campi critici contaminati → blocked=True.
    Campi soft → redazione marker con log handoff_field_redacted.
    """
    updates: dict[str, str | None] = {}
    redacted: list[str] = []
    all_matches: list[str] = []
    blocked = False

    for field_name in CRITICAL_HANDOFF_FIELDS:
        text = _field_text(ctx, field_name)
        if not text:
            continue
        scan = scan_ticket_input(text)
        if not scan.allowed:
            blocked = True
            all_matches.extend(m.pattern for m in scan.matches)

    if blocked:
        return SanitizeResult(
            context=ctx,
            blocked=True,
            matches=all_matches,
        )

    for field_name in SOFT_HANDOFF_FIELDS:
        text = _field_text(ctx, field_name)
        if not text:
            continue
        scan = scan_ticket_input(text)
        if not scan.allowed:
            cleaned = strip_injection_markers(text)
            if cleaned != text:
                updates[field_name] = cleaned
                redacted.append(field_name)
                log_event(
                    "handoff_field_redacted",
                    {
                        "field": field_name,
                        "vectors": [m.vector.value for m in scan.matches],
                    },
                )

    if updates:
        ctx = ctx.model_copy(update=updates)
    return SanitizeResult(context=ctx, redacted_fields=redacted)


def enforce_handoff_safety(
    ctx: SharedHandoffContext,
    *,
    stage: str = "handoff_resolver",
) -> SharedHandoffContext:
    """Blocca pipeline se campi critici del hand-off sono contaminati."""
    result = sanitize_handoff(ctx)
    if not result.blocked:
        return result.context

    excerpt = input_excerpt(
        _field_text(ctx, "analyst_notes")
        or _field_text(ctx, "policy_excerpt")
        or ctx.ticket_message
    )
    alert_id = log_security_alert(
        alert_type="HANDOFF_INJECTION",
        severity="CRITICAL",
        blocked_stage=stage,
        matched_pattern=result.matches[0] if result.matches else None,
        input_excerpt=excerpt,
        payload={"redacted_fields": result.redacted_fields, "patterns": result.matches},
    )
    log_event(
        "security_handoff_blocked",
        {
            "stage": stage,
            "alert_id": alert_id,
            "patterns": result.matches,
            "input_excerpt": excerpt,
        },
    )
    raise SecurityGuardrailError(
        f"Hand-off bloccato: injection indiretta rilevata ({excerpt})"
    )
