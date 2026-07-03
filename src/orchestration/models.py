"""Modelli concettuali per sistemi multi-agente (Lezione 15)."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from dataclasses import dataclass

from pydantic import BaseModel, Field


class CommunicationTopology(str, Enum):
    """Topologie di comunicazione tra agenti in un MAS."""

    HIERARCHICAL = "hierarchical"
    SEQUENTIAL = "sequential"
    COLLABORATIVE = "collaborative"


class AgentSpec(BaseModel):
    """Definizione statica di un agente specializzato (Role / Goal / Backstory)."""

    name: str
    role: str
    goal: str
    backstory: str
    tools: tuple[str, ...] = Field(default_factory=tuple)


class SharedHandoffContext(BaseModel):
    """
    Blackboard condiviso per il passaggio di consegne tra agenti (hand-off).

    L'Analyst popola anagrafica e note; il Resolver (L16) consumerà questo stato
    per policy, escalation e output JSON finale.
    """

    ticket_message: str
    topology: CommunicationTopology = CommunicationTopology.SEQUENTIAL
    cliente_nome: str | None = None
    sentiment: Literal["NEUTRO", "ARRABBIATO"] = "NEUTRO"
    storico_summary: str | None = None
    analyst_notes: str | None = None
    policy_excerpt: str | None = None
    ltm_digest: str | None = None
    source_agent: str | None = None
    target_agent: str | None = None



@dataclass(frozen=True)
class MultiAgentRunMetrics:
    """Metriche run multi-agent per benchmark L17."""

    tokens_est: int
    handoff_enriched: bool = False
    cache_policy_hits: int = 0
    cache_ltm_hits: int = 0
    compact_manuale_resolver: bool = False
