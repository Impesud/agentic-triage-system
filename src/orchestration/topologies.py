"""Catalogo topologie e squadra Impesud per la Lezione 15."""

from __future__ import annotations

from dataclasses import dataclass

from memory.extractors import detect_sentiment_label, extract_cliente_nome
from orchestration.models import AgentSpec, CommunicationTopology, SharedHandoffContext


@dataclass(frozen=True)
class TopologyInfo:
    """Metadati didattici di una topologia di comunicazione."""

    topology: CommunicationTopology
    control_mechanism: str
    ideal_use_case: str
    impesud_mapping: str


TOPOLOGY_CATALOG: tuple[TopologyInfo, ...] = (
    TopologyInfo(
        topology=CommunicationTopology.HIERARCHICAL,
        control_mechanism=(
            "Un agente Supervisore riceve l'input, delega i sotto-task "
            "agli agenti operativi e valida il risultato finale."
        ),
        ideal_use_case=(
            "Flussi aziendali rigidi con approvazione finale "
            "(es. triage e reportistica formale SOC)."
        ),
        impesud_mapping=(
            "Supervisore valida il TriageResult prima della persistenza SQLite; "
            "Analyst e Resolver operano sotto coordinamento centrale."
        ),
    ),
    TopologyInfo(
        topology=CommunicationTopology.SEQUENTIAL,
        control_mechanism=(
            "L'output dell'Agente A diventa l'input dell'Agente B "
            "in una catena lineare di montaggio cognitivo."
        ),
        ideal_use_case=(
            "Elaborazione dati a stadi sequenziali "
            "(es. Estrazione anagrafica → Analisi policy → Escalation)."
        ),
        impesud_mapping=(
            "TriageAnalyst completa il Blackboard; SecurityResolver "
            "riceve il hand-off e produce il JSON finale (pattern CrewAI L16)."
        ),
    ),
    TopologyInfo(
        topology=CommunicationTopology.COLLABORATIVE,
        control_mechanism=(
            "Gli agenti discutono in una chat condivisa, intervenendo "
            "autonomamente quando le loro competenze sono necessarie."
        ),
        ideal_use_case=(
            "Problem solving creativo o investigazione di minacce non strutturate."
        ),
        impesud_mapping=(
            "Round-robin tra Analyst e Resolver fino a convergenza "
            "(pattern AutoGen GroupChat — Lezione 16)."
        ),
    ),
)


TRIAGE_ANALYST = AgentSpec(
    name="TriageAnalyst",
    role="SOC Triage Analyst",
    goal=(
        "Identificare il cliente, valutare il sentiment e recuperare "
        "lo storico ticket prima del passaggio al resolver."
    ),
    backstory=(
        "Analista di primo livello specializzato in anagrafica e correlazione "
        "incidenti. Non gestisce policy commerciali né escalation dirette."
    ),
    tools=("search_long_term_history",),
)

SECURITY_RESOLVER = AgentSpec(
    name="SecurityResolver",
    role="Security & Policy Resolver",
    goal=(
        "Applicare policy RAG, valutare escalation manager e produrre "
        "il TriageResult JSON finale conforme allo schema Pydantic."
    ),
    backstory=(
        "Specialista compliance e policy aziendali. Riceve il contesto "
        "dall'Analyst tramite SharedHandoffContext e conclude il triage."
    ),
    tools=("search_policy", "notify_manager"),
)

IMPESUD_AGENT_TEAM: tuple[AgentSpec, ...] = (TRIAGE_ANALYST, SECURITY_RESOLVER)


def simulate_analyst_handoff(
    ticket_message: str,
    *,
    topology: CommunicationTopology = CommunicationTopology.SEQUENTIAL,
    storico_summary: str | None = None,
) -> SharedHandoffContext:
    """
    Simula il passaggio di consegne dell'Analyst verso il Resolver (demo L15).

    Usa gli extractor esistenti — nessuna chiamata LLM.
    """
    cliente = extract_cliente_nome(ticket_message)
    sentiment = detect_sentiment_label(ticket_message)
    notes_parts = [
        f"Cliente estratto: {cliente or 'non identificato'}",
        f"Sentiment rilevato: {sentiment}",
    ]
    if storico_summary:
        notes_parts.append(f"Storico LTM: {storico_summary}")

    return SharedHandoffContext(
        ticket_message=ticket_message,
        topology=topology,
        cliente_nome=cliente,
        sentiment=sentiment,  # type: ignore[arg-type]
        storico_summary=storico_summary,
        analyst_notes=" | ".join(notes_parts),
        source_agent=TRIAGE_ANALYST.name,
        target_agent=SECURITY_RESOLVER.name,
    )
