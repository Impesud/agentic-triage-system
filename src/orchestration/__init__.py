"""Modelli di coordinazione multi-agente (Lezioni 15–16)."""

from orchestration.models import AgentSpec, CommunicationTopology, SharedHandoffContext
from orchestration.topologies import IMPESUD_AGENT_TEAM, TOPOLOGY_CATALOG, simulate_analyst_handoff

__all__ = [
    "AgentSpec",
    "CommunicationTopology",
    "SharedHandoffContext",
    "IMPESUD_AGENT_TEAM",
    "TOPOLOGY_CATALOG",
    "simulate_analyst_handoff",
]
