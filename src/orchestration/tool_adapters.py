"""Adapter tool verso CrewAI e AutoGen (Lezione 16–18)."""

from __future__ import annotations

import os

from autogen_core.tools import FunctionTool
from crewai.tools import tool

from orchestration.hitl_pipeline import invoke_critical_tool_with_hitl
from orchestration.message_pruning import compact_tool_output
from orchestration.pipeline_cache import PipelineContextCache
from orchestration.tool_policy_gate import ToolPolicyContext
from tools.registry import TOOL_MAP, TOOLS_DEFINITION

_TOOL_DESCRIPTIONS: dict[str, str] = {
    entry["function"]["name"]: entry["function"]["description"]
    for entry in TOOLS_DEFINITION
}

DEFAULT_TOOL_OUTPUT_MAX_CHARS = 400


def _max_output_chars() -> int:
    raw = os.environ.get("IMPESUD_TOOL_OUTPUT_MAX_CHARS", "")
    if raw.isdigit():
        return max(50, int(raw))
    return DEFAULT_TOOL_OUTPUT_MAX_CHARS


def _tool_names_for_agent(names: tuple[str, ...]) -> None:
    unknown = set(names) - set(TOOL_MAP)
    if unknown:
        raise ValueError(f"Tool sconosciuti: {sorted(unknown)}")


def _finalize_tool_output(content: str, *, compact: bool) -> str:
    if not compact:
        return content
    return compact_tool_output(content, max_chars=_max_output_chars())


def _invoke_policy(query: str, cache: PipelineContextCache | None, *, compact: bool) -> str:
    fn = TOOL_MAP["search_policy"]

    def call(q: str) -> str:
        return _finalize_tool_output(fn(query=q), compact=compact)

    if cache is None:
        return call(query)
    return cache.get_or_call_policy(query, call)


def _invoke_ltm(
    cliente_nome: str,
    hours: int,
    cache: PipelineContextCache | None,
    *,
    compact: bool,
) -> str:
    fn = TOOL_MAP["search_long_term_history"]

    def call(cliente: str, h: int) -> str:
        return _finalize_tool_output(
            fn(cliente_nome=cliente, hours=h),
            compact=compact,
        )

    if cache is None:
        return call(cliente_nome, hours)
    return cache.get_or_call_ltm(cliente_nome, hours, call)


def _crew_search_long_term_history(cache: PipelineContextCache | None, *, compact: bool) -> object:
    description = _TOOL_DESCRIPTIONS["search_long_term_history"]

    @tool("search_long_term_history")
    def search_long_term_history(cliente_nome: str, hours: int = 24) -> str:
        """Cerca nello storico SQLite i ticket passati del cliente."""
        return _invoke_ltm(cliente_nome, hours, cache, compact=compact)

    search_long_term_history.description = description  # type: ignore[attr-defined]
    return search_long_term_history


def _crew_search_policy(cache: PipelineContextCache | None, *, compact: bool) -> object:
    description = _TOOL_DESCRIPTIONS["search_policy"]

    @tool("search_policy")
    def search_policy(query: str) -> str:
        """Cerca in policy.txt tramite RAG semantica."""
        return _invoke_policy(query, cache, compact=compact)

    search_policy.description = description  # type: ignore[attr-defined]
    return search_policy


def _crew_notify_manager(policy_ctx: ToolPolicyContext) -> object:
    description = _TOOL_DESCRIPTIONS["notify_manager"]
    base_fn = TOOL_MAP["notify_manager"]

    @tool("notify_manager")
    def notify_manager(message: str, priority: int) -> str:
        """Invia escalation al manager di turno."""
        return invoke_critical_tool_with_hitl(
            "notify_manager",
            {"message": message, "priority": priority},
            base_fn,
            policy_ctx,
            pause_ctx=policy_ctx.hitl_pause_context,
        )

    notify_manager.description = description  # type: ignore[attr-defined]
    return notify_manager


def _crew_isolate_account(policy_ctx: ToolPolicyContext) -> object:
    description = _TOOL_DESCRIPTIONS["isolate_account"]
    base_fn = TOOL_MAP["isolate_account"]

    @tool("isolate_account")
    def isolate_account(account_name: str, reason: str) -> str:
        """Isola account AD compromesso (stub SOC L18)."""
        return invoke_critical_tool_with_hitl(
            "isolate_account",
            {"account_name": account_name, "reason": reason},
            base_fn,
            policy_ctx,
            pause_ctx=policy_ctx.hitl_pause_context,
        )

    isolate_account.description = description  # type: ignore[attr-defined]
    return isolate_account


def make_crewai_tools(
    tool_names: tuple[str, ...],
    *,
    cache: PipelineContextCache | None = None,
    compact_output: bool = True,
    policy_ctx: ToolPolicyContext | None = None,
) -> list[object]:
    """Crea tool CrewAI che delegano a TOOL_MAP con cache, gate e compattazione."""
    _tool_names_for_agent(tool_names)
    ctx = policy_ctx or ToolPolicyContext(cache=cache)
    if ctx.cache is None and cache is not None:
        ctx = ToolPolicyContext(
            cache=cache,
            handoff=ctx.handoff,
            pipeline_categoria=ctx.pipeline_categoria,
            enable_hitl=ctx.enable_hitl,
            hitl_pause_context=ctx.hitl_pause_context,
        )
    tools: list[object] = []
    for name in tool_names:
        if name == "search_long_term_history":
            tools.append(_crew_search_long_term_history(cache, compact=compact_output))
        elif name == "search_policy":
            tools.append(_crew_search_policy(cache, compact=compact_output))
        elif name == "notify_manager":
            tools.append(_crew_notify_manager(ctx))
        elif name == "isolate_account":
            tools.append(_crew_isolate_account(ctx))
        else:
            raise ValueError(f"Tool CrewAI non supportato: {name}")
    return tools


def make_autogen_tools(
    tool_names: tuple[str, ...],
    *,
    cache: PipelineContextCache | None = None,
    compact_output: bool = True,
    policy_ctx: ToolPolicyContext | None = None,
) -> list[FunctionTool]:
    """Crea FunctionTool AutoGen con cache, gate e compattazione."""
    ctx = policy_ctx or ToolPolicyContext(cache=cache)
    if ctx.cache is None and cache is not None:
        ctx = ToolPolicyContext(
            cache=cache,
            handoff=ctx.handoff,
            pipeline_categoria=ctx.pipeline_categoria,
            enable_hitl=ctx.enable_hitl,
            hitl_pause_context=ctx.hitl_pause_context,
        )
    base_notify = TOOL_MAP["notify_manager"]
    base_isolate = TOOL_MAP["isolate_account"]

    def policy_fn(query: str) -> str:
        return _invoke_policy(query, cache, compact=compact_output)

    def ltm_fn(cliente_nome: str, hours: int = 24) -> str:
        return _invoke_ltm(cliente_nome, hours, cache, compact=compact_output)

    def notify_fn(message: str, priority: int) -> str:
        return invoke_critical_tool_with_hitl(
            "notify_manager",
            {"message": message, "priority": priority},
            base_notify,
            ctx,
            pause_ctx=ctx.hitl_pause_context,
        )

    def isolate_fn(account_name: str, reason: str) -> str:
        return invoke_critical_tool_with_hitl(
            "isolate_account",
            {"account_name": account_name, "reason": reason},
            base_isolate,
            ctx,
            pause_ctx=ctx.hitl_pause_context,
        )

    _autogen_fns = {
        "search_policy": policy_fn,
        "search_long_term_history": ltm_fn,
        "notify_manager": notify_fn,
        "isolate_account": isolate_fn,
    }

    _tool_names_for_agent(tool_names)
    return [
        FunctionTool(
            _autogen_fns[name],
            description=_TOOL_DESCRIPTIONS.get(name, name),
            name=name,
        )
        for name in tool_names
    ]
