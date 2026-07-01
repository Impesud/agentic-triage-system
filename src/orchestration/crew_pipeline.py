"""Pipeline CrewAI sequenziale Analyst → Resolver (Lezione 16)."""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from orchestration.framework_env import ensure_framework_env
from orchestration.models import CommunicationTopology
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


def crew_triage(user_input: str, manuale: str) -> TriageResult:
    """
    Orchestrazione CrewAI Process.sequential: TriageAnalyst → SecurityResolver.
    Topologia sequenziale (Lezione 15).
    """
    ensure_framework_env()

    seed_handoff = simulate_analyst_handoff(
        user_input,
        topology=CommunicationTopology.SEQUENTIAL,
    )
    handoff_json = seed_handoff.model_dump_json()

    analyst = Agent(
        role=TRIAGE_ANALYST.role,
        goal=TRIAGE_ANALYST.goal,
        backstory=build_analyst_system_message(manuale),
        tools=make_crewai_tools(TRIAGE_ANALYST.tools),
        verbose=True,
        allow_delegation=False,
    )
    resolver = Agent(
        role=SECURITY_RESOLVER.role,
        goal=SECURITY_RESOLVER.goal,
        backstory=build_resolver_system_message(manuale, handoff_json),
        tools=make_crewai_tools(SECURITY_RESOLVER.tools),
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
    resolver_task = Task(
        description=build_resolver_task_description(user_input, handoff_json),
        expected_output="Solo JSON TriageResult valido conforme allo schema Impesud.",
        agent=resolver,
        context=[analyst_task],
    )

    crew = Crew(
        agents=[analyst, resolver],
        tasks=[analyst_task, resolver_task],
        process=Process.sequential,
        verbose=True,
    )

    print("\n🎬 [CrewAI] Avvio pipeline sequenziale Analyst → Resolver...", flush=True)
    output = crew.kickoff()
    raw = str(output.raw if hasattr(output, "raw") else output)

    log_event(
        "crew_triage_complete",
        {
            "input_preview": user_input[:200],
            "output_preview": raw[:400],
        },
    )
    return finalize_multi_agent_output(raw, user_input)
