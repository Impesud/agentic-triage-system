"""Gate su tool critici — Lezione 18."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from orchestration.hitl_breakpoints import HitlPauseContext
from orchestration.models import SharedHandoffContext
from orchestration.pipeline_cache import PipelineContextCache
from tools.logger import log_event

CRITICAL_NOTIFY_PRIORITY = 3

_ADMIN_TARGET_PATTERN = re.compile(
    r"\b(amministratore|admin(?:istrator)?|root)\b",
    re.I,
)


@dataclass
class ToolPolicyContext:
    """Contesto runtime per valutare se un tool critico è consentito."""

    cache: PipelineContextCache | None = None
    handoff: SharedHandoffContext | None = None
    pipeline_categoria: str | None = None
    enable_hitl: bool = True
    hitl_pause_context: HitlPauseContext | None = None


@dataclass(frozen=True)
class GateVerdict:
    allowed: bool
    reason: str = ""


def _has_policy_evidence(ctx: ToolPolicyContext) -> bool:
    if ctx.cache is not None and ctx.cache.policy_by_query:
        return True
    if ctx.handoff is not None and ctx.handoff.policy_excerpt:
        return True
    return False


def _targets_admin_without_security(message: str, ctx: ToolPolicyContext) -> bool:
    if not _ADMIN_TARGET_PATTERN.search(message):
        return False
    if (ctx.pipeline_categoria or "").upper() == "SECURITY":
        return False
    if re.search(r"isol", message, re.I):
        return True
    return False


def check_notify_manager(message: str, priority: int, ctx: ToolPolicyContext) -> GateVerdict:
    if priority < CRITICAL_NOTIFY_PRIORITY:
        return GateVerdict(allowed=True)
    if not _has_policy_evidence(ctx):
        return GateVerdict(
            allowed=False,
            reason="notify_manager con priority>=3 richiede evidenza policy (search_policy o policy_excerpt)",
        )
    if _targets_admin_without_security(message, ctx):
        return GateVerdict(
            allowed=False,
            reason="escalation su account amministratore bloccata senza categoria SECURITY",
        )
    return GateVerdict(allowed=True)


def check_isolate_account(account_name: str, reason: str, ctx: ToolPolicyContext) -> GateVerdict:
    combined = f"{account_name} {reason}"
    if _targets_admin_without_security(combined, ctx):
        return GateVerdict(
            allowed=False,
            reason="isolate_account su target admin bloccato senza categoria SECURITY",
        )
    if not _has_policy_evidence(ctx):
        return GateVerdict(
            allowed=False,
            reason="isolate_account richiede evidenza policy precedente nella pipeline",
        )
    if (ctx.pipeline_categoria or "").upper() not in ("SECURITY", ""):
        return GateVerdict(
            allowed=False,
            reason="isolate_account consentito solo in contesto SECURITY",
        )
    return GateVerdict(allowed=True)


def _log_denial(tool: str, verdict: GateVerdict, **extra: Any) -> str:
    log_event(
        "security_tool_denied",
        {
            "tool": tool,
            "reason": verdict.reason,
            **extra,
        },
    )
    return f"[SECURITY DENIED] {tool}: {verdict.reason}"


def invoke_notify_manager(
    message: str,
    priority: int,
    fn: Callable[..., str],
    ctx: ToolPolicyContext,
) -> str:
    verdict = check_notify_manager(message, priority, ctx)
    if not verdict.allowed:
        return _log_denial("notify_manager", verdict, priority=priority)
    return fn(message=message, priority=priority)


def invoke_isolate_account(
    account_name: str,
    reason: str,
    fn: Callable[..., str],
    ctx: ToolPolicyContext,
) -> str:
    verdict = check_isolate_account(account_name, reason, ctx)
    if not verdict.allowed:
        return _log_denial("isolate_account", verdict, account=account_name)
    return fn(account_name=account_name, reason=reason)
