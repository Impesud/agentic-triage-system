"""Team AutoGen conversazionale Analyst + Resolver (Lezione 16)."""

from __future__ import annotations

import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient

from client import MODEL
from orchestration.framework_env import ensure_framework_env
from orchestration.models import CommunicationTopology
from orchestration.result_parser import extract_json_candidate_from_messages, finalize_multi_agent_output
from orchestration.tool_adapters import make_autogen_tools
from orchestration.topologies import SECURITY_RESOLVER, TRIAGE_ANALYST, simulate_analyst_handoff
from prompts.agents.triage_analyst import build_analyst_system_message
from prompts.agents.security_resolver import build_resolver_system_message
from schemas.ticket import TriageResult
from tools.logger import log_event


def _build_autogen_task(user_input: str, manuale: str, handoff_json: str) -> str:
    return (
        f"TICKET DA TRIAGEARE:\n{user_input}\n\n"
        f"MANUALE IT:\n{manuale}\n\n"
        f"SEED HAND-OFF (SharedHandoffContext):\n{handoff_json}\n\n"
        "Collaborate: l'Analyst raccoglie anagrafica e storico; il Resolver conclude "
        "con il JSON TriageResult finale. Il Resolver deve terminare con il JSON completo."
    )


async def _run_autogen_team(user_input: str, manuale: str) -> str:
    api_key = ensure_framework_env()
    seed_handoff = simulate_analyst_handoff(
        user_input,
        topology=CommunicationTopology.COLLABORATIVE,
    )
    handoff_json = seed_handoff.model_dump_json()

    model_client = OpenAIChatCompletionClient(model=MODEL, api_key=api_key)

    analyst = AssistantAgent(
        name=TRIAGE_ANALYST.name,
        description=TRIAGE_ANALYST.role,
        system_message=build_analyst_system_message(manuale),
        model_client=model_client,
        tools=make_autogen_tools(TRIAGE_ANALYST.tools),
    )
    resolver = AssistantAgent(
        name=SECURITY_RESOLVER.name,
        description=SECURITY_RESOLVER.role,
        system_message=build_resolver_system_message(manuale, handoff_json),
        model_client=model_client,
        tools=make_autogen_tools(SECURITY_RESOLVER.tools),
    )

    termination = MaxMessageTermination(8) | TextMentionTermination("TRIAGE_COMPLETE")
    team = RoundRobinGroupChat(
        participants=[analyst, resolver],
        termination_condition=termination,
        max_turns=8,
    )

    task = _build_autogen_task(user_input, manuale, handoff_json)
    result = await team.run(task=task)
    return extract_json_candidate_from_messages(list(result.messages))


def autogen_triage(user_input: str, manuale: str) -> TriageResult:
    """
    Orchestrazione AutoGen RoundRobinGroupChat (topologia collaborativa L15).
  """
    print("\n🎬 [AutoGen] Avvio GroupChat Analyst ↔ Resolver...", flush=True)
    raw = asyncio.run(_run_autogen_team(user_input, manuale))

    log_event(
        "autogen_triage_complete",
        {
            "input_preview": user_input[:200],
            "output_preview": raw[:400],
        },
    )
    return finalize_multi_agent_output(raw, user_input)
