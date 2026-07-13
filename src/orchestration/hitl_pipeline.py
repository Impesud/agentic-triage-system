"""Pipeline HITL: pause, resume, reject — Lezione 19."""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable

from errors import HitlApprovalRequired
from orchestration.hitl_breakpoints import BreakpointStage, HitlPauseContext, is_hitl_breakpoint
from orchestration.hitl_store import (
    get_ticket_state,
    save_ticket_state,
    update_ticket_state_status,
)
from orchestration.pipeline_cache import PipelineContextCache
from orchestration.tool_policy_gate import (
    ToolPolicyContext,
    check_isolate_account,
    check_notify_manager,
    invoke_isolate_account,
    invoke_notify_manager,
)
from tools.logger import log_event
from tools.registry import TOOL_MAP

HITL_PAUSED_PREFIX = "[HITL PAUSED]"
HITL_REJECTED_PREFIX = "[HITL REJECTED]"


def serialize_pipeline_context(ctx: ToolPolicyContext) -> dict[str, Any]:
    """Serializza cache e metadati pipeline per resume."""
    payload: dict[str, Any] = {
        "pipeline_categoria": ctx.pipeline_categoria,
    }
    if ctx.cache is not None:
        payload["policy_by_query"] = dict(ctx.cache.policy_by_query)
        payload["ltm_by_cliente"] = dict(ctx.cache.ltm_by_cliente)
    if ctx.handoff is not None:
        payload["handoff"] = ctx.handoff.model_dump()
    return payload


def deserialize_pipeline_context(data: dict[str, Any]) -> ToolPolicyContext:
    """Ricostruisce ToolPolicyContext da JSON persistito."""
    cache = None
    if data.get("policy_by_query") or data.get("ltm_by_cliente"):
        cache = PipelineContextCache(
            policy_by_query=dict(data.get("policy_by_query") or {}),
            ltm_by_cliente=dict(data.get("ltm_by_cliente") or {}),
        )
    handoff = None
    if data.get("handoff"):
        from orchestration.models import SharedHandoffContext

        handoff = SharedHandoffContext.model_validate(data["handoff"])
    return ToolPolicyContext(
        cache=cache,
        handoff=handoff,
        pipeline_categoria=data.get("pipeline_categoria"),
        enable_hitl=False,
    )


def _new_session_id() -> str:
    return f"hitl-{uuid.uuid4().hex[:12]}"


def pause_for_approval(
    tool_name: str,
    tool_args: dict[str, Any],
    *,
    pause_ctx: HitlPauseContext,
    policy_ctx: ToolPolicyContext,
    stage: BreakpointStage = BreakpointStage.PRE_CRITICAL_TOOL,
    db_path: str | None = None,
) -> str:
    """Serializza STM e contesto; persiste PENDING_APPROVAL su SQLite."""
    session_id = pause_ctx.session_id or _new_session_id()
    pipeline_context = serialize_pipeline_context(policy_ctx)
    if pause_ctx.react_session_id is not None:
        pipeline_context["react_resume"] = {
            "react_session_id": pause_ctx.react_session_id,
            "user_input": pause_ctx.user_input or pause_ctx.user_input_excerpt,
            "manuale": pause_ctx.manuale or "",
            "from_step": pause_ctx.react_step or 1,
            "tool_call_id": pause_ctx.tool_call_id,
            "pending_tool": tool_name,
            "max_steps": pause_ctx.max_steps or 4,
            "enable_optimizations": pause_ctx.enable_optimizations,
            "enable_pruning": pause_ctx.enable_pruning,
            "enable_cache": pause_ctx.enable_cache,
            "enable_compact_output": pause_ctx.enable_compact_output,
        }
    save_ticket_state(
        session_id=session_id,
        status="PENDING_APPROVAL",
        breakpoint_stage=stage.value,
        pending_tool=tool_name,
        pending_args=tool_args,
        stm_messages=pause_ctx.stm_messages,
        pipeline_context=pipeline_context,
        user_input_excerpt=pause_ctx.user_input_excerpt,
        db_path=db_path,
    )
    log_event(
        "hitl_breakpoint_reached",
        {
            "session_id": session_id,
            "tool": tool_name,
            "args": tool_args,
            "stage": stage.value,
            "user_input_excerpt": pause_ctx.user_input_excerpt[:200],
        },
    )
    message = (
        f"{HITL_PAUSED_PREFIX} session_id={session_id} "
        f"tool={tool_name} in attesa approvazione operatore"
    )
    raise HitlApprovalRequired(message, session_id=session_id)


def invoke_critical_tool_with_hitl(
    tool_name: str,
    tool_args: dict[str, Any],
    fn: Callable[..., str],
    ctx: ToolPolicyContext,
    *,
    pause_ctx: HitlPauseContext | None = None,
    db_path: str | None = None,
) -> str:
    """
    Gate L18 + breakpoint HITL L19 per notify_manager e isolate_account.
    Se HITL attivo e breakpoint, pausa e solleva HitlApprovalRequired.
    """
    if tool_name == "notify_manager":
        message = str(tool_args.get("message", ""))
        priority = int(tool_args.get("priority", 1))
        verdict = check_notify_manager(message, priority, ctx)
        if not verdict.allowed:
            from orchestration.tool_policy_gate import _log_denial

            return _log_denial("notify_manager", verdict, priority=priority)
        if ctx.enable_hitl and is_hitl_breakpoint(tool_name, tool_args):
            if pause_ctx is None:
                pause_ctx = HitlPauseContext(
                    session_id=_new_session_id(),
                    stm_messages=[],
                    user_input_excerpt=message[:200],
                )
            return _pause_or_raise(tool_name, tool_args, fn=fn, ctx=ctx, pause_ctx=pause_ctx, db_path=db_path)
        return fn(message=message, priority=priority)

    if tool_name == "isolate_account":
        account_name = str(tool_args.get("account_name", ""))
        reason = str(tool_args.get("reason", ""))
        verdict = check_isolate_account(account_name, reason, ctx)
        if not verdict.allowed:
            from orchestration.tool_policy_gate import _log_denial

            return _log_denial("isolate_account", verdict, account=account_name)
        if ctx.enable_hitl and is_hitl_breakpoint(tool_name, tool_args):
            if pause_ctx is None:
                pause_ctx = HitlPauseContext(
                    session_id=_new_session_id(),
                    stm_messages=[],
                    user_input_excerpt=f"{account_name}: {reason}"[:200],
                )
            return _pause_or_raise(tool_name, tool_args, fn=fn, ctx=ctx, pause_ctx=pause_ctx, db_path=db_path)
        return fn(account_name=account_name, reason=reason)

    return fn(**tool_args)


def _pause_or_raise(
    tool_name: str,
    tool_args: dict[str, Any],
    *,
    fn: Callable[..., str],
    ctx: ToolPolicyContext,
    pause_ctx: HitlPauseContext,
    db_path: str | None,
) -> str:
    try:
        pause_for_approval(
            tool_name,
            tool_args,
            pause_ctx=pause_ctx,
            policy_ctx=ctx,
            db_path=db_path,
        )
    except HitlApprovalRequired:
        raise
    return fn(**tool_args)


def _execute_pending_tool(record_tool: str, args: dict[str, Any], ctx: ToolPolicyContext) -> str:
    """Esegue il tool pendente dopo approvazione (senza nuova pausa HITL)."""
    ctx = ToolPolicyContext(
        cache=ctx.cache,
        handoff=ctx.handoff,
        pipeline_categoria=ctx.pipeline_categoria,
        enable_hitl=False,
        hitl_pause_context=None,
    )
    if record_tool == "notify_manager":
        return invoke_notify_manager(
            str(args.get("message", "")),
            int(args.get("priority", 1)),
            lambda **kw: TOOL_MAP["notify_manager"](**kw),
            ctx,
        )
    if record_tool == "isolate_account":
        return invoke_isolate_account(
            str(args.get("account_name", "")),
            str(args.get("reason", "")),
            lambda **kw: TOOL_MAP["isolate_account"](**kw),
            ctx,
        )
    return TOOL_MAP[record_tool](**args)


def approve_session(
    session_id: str,
    operator: str,
    *,
    db_path: str | None = None,
    resume_react: bool = True,
) -> str:
    """Approva, esegue il tool pendente e opzionalmente riprende ReAct."""
    record = get_ticket_state(session_id, status="PENDING_APPROVAL", db_path=db_path)
    if record is None:
        raise ValueError(f"Sessione HITL non trovata o non in PENDING_APPROVAL: {session_id}")

    log_event(
        "hitl_session_approved",
        {"session_id": session_id, "operator": operator, "tool": record.pending_tool},
    )

    pipeline_data = json.loads(record.pipeline_context_json or "{}")
    ctx = deserialize_pipeline_context(pipeline_data)
    args = json.loads(record.pending_args_json)
    tool_output = _execute_pending_tool(record.pending_tool, args, ctx)

    conversation = json.loads(record.stm_json)
    tool_call_id = args.get("_tool_call_id") or pipeline_data.get("react_resume", {}).get(
        "tool_call_id"
    )
    if tool_call_id:
        conversation.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": record.pending_tool,
                "content": tool_output,
            }
        )

    react_meta = pipeline_data.get("react_resume")
    if resume_react and react_meta:
        from logic import react_triage_resume

        react_triage_resume(
            conversation,
            user_input=str(react_meta.get("user_input", record.user_input_excerpt)),
            manuale=str(react_meta.get("manuale", "")),
            session_id=str(react_meta["react_session_id"]),
            from_step=int(react_meta.get("from_step", 1)),
            max_steps=int(react_meta.get("max_steps", 4)),
            enable_optimizations=bool(react_meta.get("enable_optimizations", True)),
            enable_pruning=react_meta.get("enable_pruning"),
            enable_cache=react_meta.get("enable_cache"),
            enable_compact_output=react_meta.get("enable_compact_output"),
            cache=ctx.cache,
        )

    update_ticket_state_status(
        session_id,
        status="RESUMED",
        resolved_by=operator,
        db_path=db_path,
    )
    log_event(
        "hitl_session_resumed",
        {
            "session_id": session_id,
            "operator": operator,
            "tool": record.pending_tool,
            "tool_output_preview": tool_output[:200],
        },
    )
    return tool_output


# Alias didattico (piano L19)
resume_session = approve_session


def reject_session(
    session_id: str,
    operator: str,
    *,
    reason: str = "",
    db_path: str | None = None,
) -> str:
    """Rifiuta la sessione HITL pendente."""
    record = get_ticket_state(session_id, status="PENDING_APPROVAL", db_path=db_path)
    if record is None:
        raise ValueError(f"Sessione HITL non trovata o non in PENDING_APPROVAL: {session_id}")

    update_ticket_state_status(
        session_id,
        status="REJECTED",
        resolved_by=operator,
        db_path=db_path,
    )
    log_event(
        "hitl_session_rejected",
        {
            "session_id": session_id,
            "operator": operator,
            "reason": reason,
            "tool": record.pending_tool,
        },
    )
    detail = f" reason={reason}" if reason else ""
    return f"{HITL_REJECTED_PREFIX} session_id={session_id}{detail}"
