"""Test modelli multi-agente Lezione 15."""

from orchestration.models import AgentSpec, CommunicationTopology, SharedHandoffContext
from orchestration.topologies import IMPESUD_AGENT_TEAM, simulate_analyst_handoff

L13_TICKET = (
    "Sono Marco Rossi. Ho un budget di 15.000€ per un progetto AI "
    "e voglio parlare con un manager."
)


def test_agent_spec_fields():
    analyst = IMPESUD_AGENT_TEAM[0]
    assert analyst.name == "TriageAnalyst"
    assert analyst.role
    assert analyst.goal
    assert analyst.backstory
    assert analyst.tools == ("search_long_term_history",)


def test_handoff_context_roundtrip():
    ctx = SharedHandoffContext(
        ticket_message="test",
        topology=CommunicationTopology.SEQUENTIAL,
        cliente_nome="Marco",
        sentiment="NEUTRO",
    )
    restored = SharedHandoffContext.model_validate(ctx.model_dump())
    assert restored.cliente_nome == "Marco"
    assert restored.topology == CommunicationTopology.SEQUENTIAL


def test_topology_enum_values():
    values = {t.value for t in CommunicationTopology}
    assert values == {"hierarchical", "sequential", "collaborative"}


def test_analyst_resolver_tool_partition():
    analyst_tools = set(IMPESUD_AGENT_TEAM[0].tools)
    resolver_tools = set(IMPESUD_AGENT_TEAM[1].tools)
    assert not analyst_tools & resolver_tools
    assert analyst_tools == {"search_long_term_history"}
    assert resolver_tools == {"search_policy", "notify_manager"}


def test_simulate_handoff_marco_rossi():
    handoff = simulate_analyst_handoff(L13_TICKET)
    assert handoff.cliente_nome == "Marco"
    assert handoff.source_agent == "TriageAnalyst"
    assert handoff.target_agent == "SecurityResolver"
    assert handoff.topology == CommunicationTopology.SEQUENTIAL
    assert handoff.analyst_notes
    assert "Marco" in handoff.analyst_notes


def test_agent_spec_is_frozen_tuple_tools():
    spec = AgentSpec(
        name="Test",
        role="R",
        goal="G",
        backstory="B",
        tools=("tool_a",),
    )
    assert spec.tools == ("tool_a",)
