"""Team AutoGen conversazionale Analyst + Resolver (Lezione 16–18)."""

from __future__ import annotations

import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient

from client import MODEL
from orchestration.crew_pipeline import estimate_crew_pipeline_tokens
from orchestration.framework_env import ensure_framework_env
from orchestration.handoff_enrichment import enrich_handoff_from_cache
from orchestration.handoff_sanitizer import enforce_handoff_safety
from orchestration.models import CommunicationTopology, MultiAgentRunMetrics
from orchestration.pipeline_cache import PipelineContextCache
from orchestration.security_pipeline import guard_ticket_input
from orchestration.tool_policy_gate import ToolPolicyContext
from orchestration.prompt_compression import compact_manuale_for_resolver
from orchestration.result_parser import extract_json_candidate_from_messages, finalize_multi_agent_output
from orchestration.tool_adapters import make_autogen_tools
from orchestration.topologies import SECURITY_RESOLVER, TRIAGE_ANALYST, simulate_analyst_handoff
from prompts.agents.triage_analyst import build_analyst_system_message
from prompts.agents.security_resolver import build_resolver_system_message
from schemas.ticket import TriageResult
from tools.logger import log_event


def _build_analyst_task(user_input: str) -> str:
    return (
        f"Analizza il ticket: {user_input}\n"
        "Identifica cliente e sentiment, invoca search_long_term_history se applicabile. "
        "Restituisci un report strutturato per il Resolver (non il JSON finale)."
    )


def _build_group_task(
    user_input: str,
    manuale: str,
    handoff_json: str,
    analyst_summary: str,
    *,
    compact_manuale: bool,
) -> str:
    manual_block = compact_manuale_for_resolver(manuale) if compact_manuale else manuale
    return (
        f"TICKET DA TRIAGEARE:\n{user_input}\n\n"
        f"MANUALE IT:\n{manual_block}\n\n"
        f"HAND-OFF ARRICCHITO (SharedHandoffContext):\n{handoff_json}\n\n"
        f"REPORT ANALYST (fase 1):\n{analyst_summary}\n\n"
        "Collaborate: il Resolver conclude con il JSON TriageResult finale completo."
    )


def _extract_last_text(result: object) -> str:
    messages = getattr(result, "messages", None) or []
    for message in reversed(list(messages)):
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content
    return str(result)


async def _run_autogen_team(
    user_input: str,
    manuale: str,
    *,
    enable_optimizations: bool,
    enable_security_guard: bool,
) -> tuple[str, MultiAgentRunMetrics]:
    api_key = ensure_framework_env()
    cache = PipelineContextCache() if enable_optimizations else None
    compact = enable_optimizations
    seed_handoff = simulate_analyst_handoff(
        user_input,
        topology=CommunicationTopology.COLLABORATIVE,
    )

    model_client = OpenAIChatCompletionClient(model=MODEL, api_key=api_key)

    analyst = AssistantAgent(
        name=TRIAGE_ANALYST.name,
        description=TRIAGE_ANALYST.role,
        system_message=build_analyst_system_message(manuale),
        model_client=model_client,
        tools=make_autogen_tools(TRIAGE_ANALYST.tools, cache=cache, compact_output=compact),
    )

    print("\n🎬 [AutoGen] Fase 1 — TriageAnalyst...", flush=True)
    analyst_result = await analyst.run(task=_build_analyst_task(user_input))
    analyst_summary = _extract_last_text(analyst_result)

    enriched_handoff = (
        enrich_handoff_from_cache(seed_handoff, cache) if cache else seed_handoff
    )
    if enable_security_guard:
        enriched_handoff = enforce_handoff_safety(enriched_handoff)
    resolver_handoff_json = enriched_handoff.model_dump_json()
    handoff_enriched = bool(
        enriched_handoff.policy_excerpt or enriched_handoff.ltm_digest
    )
    compact_manuale = enable_optimizations and handoff_enriched
    policy_ctx = ToolPolicyContext(cache=cache, handoff=enriched_handoff)

    if handoff_enriched:
        log_event(
            "handoff_enriched_from_cache",
            {
                "orchestrator": "autogen",
                "has_policy_excerpt": bool(enriched_handoff.policy_excerpt),
                "has_ltm_digest": bool(enriched_handoff.ltm_digest),
                "cache_policy_hits": cache.policy_hits if cache else 0,
                "cache_ltm_hits": cache.ltm_hits if cache else 0,
                "compact_manuale_resolver": compact_manuale,
            },
        )

    resolver = AssistantAgent(
        name=SECURITY_RESOLVER.name,
        description=SECURITY_RESOLVER.role,
        system_message=build_resolver_system_message(
            manuale, resolver_handoff_json, compact_manuale=compact_manuale
        ),
        model_client=model_client,
        tools=make_autogen_tools(SECURITY_RESOLVER.tools, cache=cache, compact_output=compact, policy_ctx=policy_ctx),
    )

    termination = MaxMessageTermination(8) | TextMentionTermination("TRIAGE_COMPLETE")
    team = RoundRobinGroupChat(
        participants=[analyst, resolver],
        termination_condition=termination,
        max_turns=8,
    )

    task = _build_group_task(
        user_input,
        manuale,
        resolver_handoff_json,
        analyst_summary,
        compact_manuale=compact_manuale,
    )
    print("🎬 [AutoGen] Fase 2 — GroupChat con hand-off arricchito...", flush=True)
    result = await team.run(task=task)
    raw = extract_json_candidate_from_messages(list(result.messages))

    tokens_est = estimate_crew_pipeline_tokens(
        manuale,
        resolver_handoff_json,
        raw,
        compact_manuale_resolver=compact_manuale,
    )
    metrics = MultiAgentRunMetrics(
        tokens_est=tokens_est,
        handoff_enriched=handoff_enriched,
        cache_policy_hits=cache.policy_hits if cache else 0,
        cache_ltm_hits=cache.ltm_hits if cache else 0,
        compact_manuale_resolver=compact_manuale,
    )
    return raw, metrics


def autogen_triage(
    user_input: str,
    manuale: str,
    *,
    enable_optimizations: bool = True,
    return_metrics: bool = False,
    enable_security_guard: bool = True,
) -> TriageResult | tuple[TriageResult, MultiAgentRunMetrics]:
    """Orchestrazione AutoGen: Analyst solo → arricchimento cache → GroupChat."""
    if enable_security_guard:
        guard_ticket_input(user_input)
    print("\n🎬 [AutoGen] Avvio pipeline Analyst → Resolver...", flush=True)
    raw, metrics = asyncio.run(
        _run_autogen_team(
            user_input,
            manuale,
            enable_optimizations=enable_optimizations,
            enable_security_guard=enable_security_guard,
        )
    )

    log_event(
        "autogen_triage_complete",
        {
            "input_preview": user_input[:200],
            "output_preview": raw[:400],
            "enable_optimizations": enable_optimizations,
            "tokens_est": metrics.tokens_est,
        },
    )
    result = finalize_multi_agent_output(raw, user_input)
    if return_metrics:
        return result, metrics
    return result
