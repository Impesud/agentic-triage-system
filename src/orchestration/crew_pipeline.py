"""Pipeline CrewAI sequenziale Analyst → Resolver (Lezione 16–18)."""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from orchestration.framework_env import ensure_framework_env
from orchestration.handoff_enrichment import enrich_handoff_from_cache
from orchestration.handoff_sanitizer import enforce_handoff_safety
from orchestration.message_pruning import estimate_tokens
from orchestration.models import CommunicationTopology, MultiAgentRunMetrics
from orchestration.pipeline_cache import PipelineContextCache
from orchestration.prompt_compression import compact_manuale_for_resolver
from orchestration.security_pipeline import guard_ticket_input
from orchestration.tool_policy_gate import ToolPolicyContext
from orchestration.result_parser import finalize_multi_agent_output
from orchestration.tool_adapters import make_crewai_tools
from orchestration.topologies import SECURITY_RESOLVER, TRIAGE_ANALYST, simulate_analyst_handoff
from prompts.agents.triage_analyst import build_analyst_system_message
from prompts.agents.security_resolver import build_resolver_system_message
from schemas.ticket import TriageResult
from tools.logger import log_event


def build_resolver_task_description(user_input: str, handoff_json: str) -> str:
    """Descrizione task Resolver con Blackboard serializzato (testabile)."""
    return (
        f"Ticket originale: {user_input}\n\n"
        f"Hand-off Analyst (SharedHandoffContext):\n{handoff_json}\n\n"
        "Applica policy ed escalation se necessario, poi produci SOLO il JSON TriageResult finale."
    )


def estimate_crew_pipeline_tokens(
    manuale: str,
    handoff_json: str,
    output: str,
    *,
    compact_manuale_resolver: bool,
) -> int:
    """Stima grezza token cumulativi Analyst + Resolver (benchmark L17)."""
    analyst_part = estimate_tokens(manuale) + estimate_tokens(handoff_json)
    resolver_manual = (
        compact_manuale_for_resolver(manuale) if compact_manuale_resolver else manuale
    )
    resolver_part = (
        estimate_tokens(resolver_manual)
        + estimate_tokens(handoff_json)
        + estimate_tokens(output)
    )
    return analyst_part + resolver_part


def _handoff_is_enriched(handoff) -> bool:
    return bool(handoff.policy_excerpt or handoff.ltm_digest)


def _build_resolver_agent(
    manuale: str,
    resolver_handoff_json: str,
    *,
    cache: PipelineContextCache | None,
    compact: bool,
    compact_manuale: bool,
    policy_ctx: ToolPolicyContext | None = None,
) -> Agent:
    ctx = policy_ctx or ToolPolicyContext(cache=cache)
    return Agent(
        role=SECURITY_RESOLVER.role,
        goal=SECURITY_RESOLVER.goal,
        backstory=build_resolver_system_message(
            manuale,
            resolver_handoff_json,
            compact_manuale=compact_manuale,
        ),
        tools=make_crewai_tools(
            SECURITY_RESOLVER.tools,
            cache=cache,
            compact_output=compact,
            policy_ctx=ctx,
        ),
        verbose=True,
        allow_delegation=False,
    )


def crew_triage(
    user_input: str,
    manuale: str,
    *,
    enable_optimizations: bool = True,
    return_metrics: bool = False,
    enable_security_guard: bool = True,
) -> TriageResult | tuple[TriageResult, MultiAgentRunMetrics]:
    """
    Orchestrazione CrewAI in due fasi: Analyst → arricchimento Blackboard → Resolver.
    """
    if enable_security_guard:
        guard_ticket_input(user_input)
    ensure_framework_env()
    cache = PipelineContextCache() if enable_optimizations else None
    compact = enable_optimizations

    seed_handoff = simulate_analyst_handoff(
        user_input,
        topology=CommunicationTopology.SEQUENTIAL,
    )

    analyst = Agent(
        role=TRIAGE_ANALYST.role,
        goal=TRIAGE_ANALYST.goal,
        backstory=build_analyst_system_message(manuale),
        tools=make_crewai_tools(TRIAGE_ANALYST.tools, cache=cache, compact_output=compact),
        verbose=True,
        allow_delegation=False,
    )

    analyst_task = Task(
        description=(
            f"Analizza il ticket: {user_input}\n"
            "Identifica cliente e sentiment, invoca search_long_term_history se applicabile. "
            "Restituisci un report strutturato per il Resolver (non il JSON finale)."
        ),
        expected_output=(
            "Report con cliente_nome, sentiment, storico_summary e analyst_notes."
        ),
        agent=analyst,
    )

    print("\n🎬 [CrewAI] Fase 1 — TriageAnalyst...", flush=True)
    analyst_crew = Crew(
        agents=[analyst],
        tasks=[analyst_task],
        process=Process.sequential,
        verbose=True,
    )
    analyst_crew.kickoff()

    enriched_handoff = (
        enrich_handoff_from_cache(seed_handoff, cache) if cache else seed_handoff
    )
    if enable_security_guard:
        enriched_handoff = enforce_handoff_safety(enriched_handoff)
    resolver_handoff_json = enriched_handoff.model_dump_json()
    handoff_enriched = _handoff_is_enriched(enriched_handoff)
    compact_manuale = enable_optimizations and handoff_enriched
    policy_ctx = ToolPolicyContext(cache=cache, handoff=enriched_handoff)

    if handoff_enriched:
        log_event(
            "handoff_enriched_from_cache",
            {
                "has_policy_excerpt": bool(enriched_handoff.policy_excerpt),
                "has_ltm_digest": bool(enriched_handoff.ltm_digest),
                "cache_policy_hits": cache.policy_hits if cache else 0,
                "cache_ltm_hits": cache.ltm_hits if cache else 0,
                "compact_manuale_resolver": compact_manuale,
            },
        )

    resolver = _build_resolver_agent(
        manuale,
        resolver_handoff_json,
        cache=cache,
        compact=compact,
        compact_manuale=compact_manuale,
        policy_ctx=policy_ctx,
    )
    resolver_task = Task(
        description=build_resolver_task_description(user_input, resolver_handoff_json),
        expected_output="Solo JSON TriageResult valido conforme allo schema Impesud.",
        agent=resolver,
        context=[analyst_task],
    )

    print("🎬 [CrewAI] Fase 2 — SecurityResolver (hand-off arricchito)...", flush=True)
    resolver_crew = Crew(
        agents=[resolver],
        tasks=[resolver_task],
        process=Process.sequential,
        verbose=True,
    )
    output = resolver_crew.kickoff()
    raw = str(output.raw if hasattr(output, "raw") else output)

    tokens_est = estimate_crew_pipeline_tokens(
        manuale,
        resolver_handoff_json,
        raw,
        compact_manuale_resolver=compact_manuale,
    )

    log_event(
        "crew_triage_complete",
        {
            "input_preview": user_input[:200],
            "output_preview": raw[:400],
            "enable_optimizations": enable_optimizations,
            "cache_policy_hits": cache.policy_hits if cache else 0,
            "cache_ltm_hits": cache.ltm_hits if cache else 0,
            "handoff_enriched": handoff_enriched,
            "tokens_est": tokens_est,
        },
    )
    result = finalize_multi_agent_output(raw, user_input)
    if return_metrics:
        return result, MultiAgentRunMetrics(
            tokens_est=tokens_est,
            handoff_enriched=handoff_enriched,
            cache_policy_hits=cache.policy_hits if cache else 0,
            cache_ltm_hits=cache.ltm_hits if cache else 0,
            compact_manuale_resolver=compact_manuale,
        )
    return result
