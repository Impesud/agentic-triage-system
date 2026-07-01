"""
Orchestrazione ticket e demo didattiche Lezione 9/10/11/13.

Esecuzione demo:
  PYTHONPATH=src python src/main.py              # M3 → M1 → M2
  PYTHONPATH=src python src/main.py --scenario m1
  PYTHONPATH=src python src/main.py --scenario l10   # RAG semantica su policy
  PYTHONPATH=src python src/main.py --scenario l11   # Self-correction (Lezione 11)
  PYTHONPATH=src python src/main.py --scenario l13   # ReAct + SQLite (Lezione 13)
  PYTHONPATH=src python src/main.py --scenario l14   # Planning multi-step (Lezione 14)
  PYTHONPATH=src python src/main.py --scenario l15   # Multi-agent topologie (Lezione 15)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import paths
from logic import ClarificationNeeded, react_triage, triage_message
from memory.extractors import detect_sentiment_label, extract_cliente_nome
from memory.session_manager import SessionManager
from paths import DEMO_M2_DB_PATH, DEMO_M2_LOG_PATH, LOG_FILE_PATH, MANUALE_IT_PATH, POLICY_PATH, TRIAGE_DB_PATH
from rag.policy_semantic import format_semantic_result, semantic_policy_search
from schemas.ticket import Ticket
from storage.store import get_current_ticket, next_ticket_id, save_ticket
from tools.enrichment import enrich_priority
from tools.logger import init_db, log_event, log_triage_to_sqlite
from tools.office_tools import search_policy
from tools.router import assign_to_team

# --- Testi demo (distinti dai few-shot in triage_v1.py) ---

STM_TURN1 = (
    "Ho un problema urgente con un server in produzione: non si avvia "
    "e non ho altri dettagli al momento."
)
STM_TURN2 = "È il server-X in datacenter Roma."

LTM_MARCO_TICKET = (
    "Sono Marco della divisione Nord. Il cluster db-primary è offline da stamattina, "
    "sono molto deluso: è il quinto incidente critico questa settimana!"
)

SMOKE_IT_TICKET = "Non riesco ad accedere alla casella aziendale, risulta bloccata."

L10_SYNONYM_QUERY = (
    "Voglio annullare il contratto e riavere i soldi: quali sono i termini?"
)

L13_TICKET_1 = (
    "Sono Marco Rossi. Ho un budget di 15.000€ per un progetto AI "
    "e voglio parlare con un manager."
)

L14_TICKET_2 = (
    "Salve, sono sempre Marco Rossi. Volevo sapere se applicate uno sconto "
    "per il progetto di cui vi ho parlato prima."
)


@dataclass(frozen=True)
class Lesson9Scenario:
    """Metadati didattici per uno scenario demo."""

    id: str
    title: str
    objective: str
    watch_for: tuple[str, ...]
    messages: tuple[str, ...]


DEMO_SCENARIOS: tuple[Lesson9Scenario, ...] = (
    Lesson9Scenario(
        id="M3",
        title="Smoke — pipeline base",
        objective="Verificare che triage, enrichment e routing funzionino (senza memoria multi-turno).",
        watch_for=(
            "=== TICKET PROCESSATO ===",
            "categoria",
            "team",
        ),
        messages=(SMOKE_IT_TICKET,),
    ),
    Lesson9Scenario(
        id="M1",
        title="Short-term — thread multi-turno",
        objective=(
            "Mostrare la memoria a breve termine: turno 1 ambiguo → chiarimento; "
            "turno 2 con ID server → triage completo sullo stesso ticket_id."
        ),
        watch_for=(
            "[CHIARIMENTO]",
            "continue_ticket / turno 2",
            "SessionManager (cronologia in logic.build_chat_messages)",
            "=== TICKET PROCESSATO ===",
        ),
        messages=(STM_TURN1, STM_TURN2),
    ),
    Lesson9Scenario(
        id="M2",
        title="Long-term — storico cliente Marco",
        objective=(
            "Mostrare la memoria a lungo termine: 4 ticket passati IT+ARRABBIATO in seed, "
            "poi quinto ticket → search_long_term_history e possibile notify_manager."
        ),
        watch_for=(
            "[SEED]",
            "[AGENTE] Attivazione tool",
            "search_long_term_history",
            "🚨 [ESCALATION LIVE]",
            "data/demo_m2_triage.db",
        ),
        messages=(LTM_MARCO_TICKET,),
    ),
)

session_manager = SessionManager()


def load_it_manual() -> str:
    return MANUALE_IT_PATH.read_text(encoding="utf-8")


def _print_scenario_intro(scenario: Lesson9Scenario) -> None:
    print("\n" + "=" * 72)
    print(f"SCENARIO {scenario.id} — {scenario.title}")
    print("=" * 72)
    print(f"Obiettivo: {scenario.objective}")
    if len(scenario.messages) > 1:
        print("Messaggi (in ordine):")
        for i, msg in enumerate(scenario.messages, start=1):
            print(f"  Turno {i}: {msg}")
    else:
        print(f"Messaggio: {scenario.messages[0]}")
    print("Cosa osservare in console / log:")
    for signal in scenario.watch_for:
        print(f"  • {signal}")
    print("-" * 72)


def _user_thread_text(ticket_id: int, latest: str) -> str:
    parts = [
        m["content"]
        for m in session_manager.get_messages(ticket_id)
        if m["role"] == "user"
    ]
    if not parts:
        return latest
    return "\n".join(parts)


def _log_ticket_processed(ticket: Ticket) -> None:
    full_text = _user_thread_text(ticket.id, ticket.messaggio_originale)
    cliente = extract_cliente_nome(full_text)
    sentiment = detect_sentiment_label(full_text)
    log_event(
        "ticket_processed",
        {
            "ticket": ticket.model_dump(),
            "cliente_nome": cliente,
            "sentiment": sentiment,
        },
    )
    log_triage_to_sqlite(
        {
            "cliente_nome": cliente or "Anonimo",
            "categoria": ticket.categoria or "GENERAL",
            "priorita": ticket.priorita or "LOW",
            "sentiment": sentiment,
            "riassunto_breve": ticket.riassunto_breve or "",
            "lingua": "Italiano",
            "azione_eseguita": "Nessuna",
        }
    )


def _run_triage_pipeline(ticket: Ticket, user_input: str, manuale: str) -> Ticket | None:
    history = session_manager.get_messages(ticket.id)
    if history and history[-1].get("role") == "user" and history[-1].get("content") == user_input:
        history = history[:-1]

    try:
        triage = triage_message(user_input, manuale, history=history or None)
    except ClarificationNeeded as exc:
        session_manager.append(ticket.id, "assistant", exc.message)
        log_event("clarification_requested", {"ticket_id": ticket.id, "question": exc.message})
        print(f"\n[CHIARIMENTO] {exc.message}")
        print(
            f"[M1] Ticket #{ticket.id} resta OPEN — usa continue_ticket({ticket.id}, '<risposta>')"
        )
        return ticket

    log_event("triage_cot", {"analisi_problema": triage.analisi_problema})

    ticket = ticket.model_copy(
        update={
            "analisi_problema": triage.analisi_problema,
            "categoria": triage.categoria,
            "priorita": triage.priorita,
            "riassunto_breve": triage.riassunto_breve,
        }
    )

    ticket = enrich_priority(ticket)
    log_event("ticket_enriched", {"ticket": ticket.model_dump()})

    ticket = ticket.model_copy(update={"status": "TRIAGED"})
    save_ticket(ticket)
    log_event("ticket_saved", {"ticket": ticket.model_dump(), "phase": "triaged"})

    ticket = assign_to_team(ticket)
    save_ticket(ticket)
    log_event("ticket_saved", {"ticket": ticket.model_dump(), "phase": "routed"})
    _log_ticket_processed(ticket)

    session_manager.append(
        ticket.id,
        "assistant",
        f"Triage completato: {ticket.categoria} / {ticket.priorita} — {ticket.riassunto_breve}",
    )

    print("\n=== TICKET PROCESSATO ===")
    print(ticket.model_dump())
    return ticket


def process_ticket(user_input: str) -> Ticket | None:
    """Nuovo ticket: persistenza OPEN, triage agentico, enrichment, routing."""
    try:
        log_event("ticket_received", {"input": user_input})

        ticket = Ticket(
            id=next_ticket_id(),
            status="OPEN",
            messaggio_originale=user_input,
        )
        save_ticket(ticket)
        log_event("ticket_saved", {"ticket": ticket.model_dump(), "phase": "open"})

        session_manager.append(ticket.id, "user", user_input)
        manuale = load_it_manual()
        return _run_triage_pipeline(ticket, user_input, manuale)

    except (FileNotFoundError, ValueError, OSError) as e:
        log_event("error", {"message": str(e), "input": user_input})
        print("\n[ERRORE]", str(e))
        return None


def continue_ticket(ticket_id: int, user_input: str) -> Ticket | None:
    """Turno successivo sullo stesso ticket_id (short-term memory)."""
    try:
        if get_current_ticket(ticket_id) is None:
            raise ValueError(f"Ticket {ticket_id} non trovato")

        log_event("ticket_received", {"input": user_input, "ticket_id": ticket_id})
        session_manager.append(ticket_id, "user", user_input)

        ticket = Ticket(
            id=ticket_id,
            status="OPEN",
            messaggio_originale=_user_thread_text(ticket_id, user_input),
        )
        manuale = load_it_manual()
        return _run_triage_pipeline(ticket, user_input, manuale)

    except (FileNotFoundError, ValueError, OSError) as e:
        log_event("error", {"message": str(e), "input": user_input, "ticket_id": ticket_id})
        print("\n[ERRORE]", str(e))
        return None


def seed_marco_sqlite(
    n: int = 4,
    db_path: Path | None = None,
    *,
    reset: bool = False,
) -> Path:
    """
    Scrive n record IT+ARRABBIATO per Marco nel database SQLite (demo M2 / L13).
    """
    path = db_path or TRIAGE_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    if reset and path.exists():
        path.unlink()

    init_db(str(path))
    now = datetime.now(UTC)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        for i in range(n):
            ts = (now - timedelta(hours=2 - i * 0.25)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                INSERT INTO tickets (
                    cliente_nome, categoria, priorita, sentiment,
                    riassunto_breve, lingua, azione_eseguita, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Marco",
                    "IT",
                    "HIGH",
                    "ARRABBIATO",
                    f"Incidente db-primary ripetuto #{i + 1}",
                    "Italiano",
                    "Nessuna",
                    ts,
                ),
            )
        conn.commit()

    action = "Ricreato" if reset else "Aggiornato"
    print(f"[SEED] {action} storico SQLite: {n} ticket IT+ARRABBIATO per Marco → {path}")
    return path


def seed_marco_angry_history(
    n: int = 4,
    log_path: Path | None = None,
    *,
    reset: bool = False,
) -> Path:
    """
    Scrive n ticket_processed IT+ARRABBIATO per Marco (demo M2).

    Con reset=True il file viene ricreato (demo ripetibile in classe).
    """
    path = log_path or LOG_FILE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    mode = "w" if reset else "a"
    with open(path, mode, encoding="utf-8") as f:
        for i in range(n):
            ts = (now - timedelta(hours=2 - i * 0.25)).isoformat()
            entry = {
                "timestamp": ts,
                "event_type": "ticket_processed",
                "payload": {
                    "cliente_nome": "Marco",
                    "sentiment": "ARRABBIATO",
                    "ticket": {
                        "categoria": "IT",
                        "priorita": "HIGH",
                        "riassunto_breve": f"Incidente db-primary ripetuto #{i + 1}",
                        "messaggio_originale": (
                            f"Sono Marco. Cluster db-primary down — incidente #{i + 1}"
                        ),
                    },
                },
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    action = "Ricreato" if reset else "Aggiornato"
    print(f"[SEED] {action} storico: {n} ticket IT+ARRABBIATO per Marco → {path}")
    return path


class _SqliteDbPatch:
    """Contesto: LTM ReAct legge da un DB SQLite isolato (demo M2)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._previous: Path | None = None

    def __enter__(self) -> Path:
        self._previous = paths.TRIAGE_DB_PATH
        paths.TRIAGE_DB_PATH = self._path
        return self._path

    def __exit__(self, *args: object) -> None:
        if self._previous is not None:
            paths.TRIAGE_DB_PATH = self._previous


def _patch_sqlite_db(path: Path) -> _SqliteDbPatch:
    return _SqliteDbPatch(path)


def run_smoke_demo() -> None:
    scenario = next(s for s in DEMO_SCENARIOS if s.id == "M3")
    _print_scenario_intro(scenario)
    process_ticket(SMOKE_IT_TICKET)


def run_stm_demo() -> None:
    scenario = next(s for s in DEMO_SCENARIOS if s.id == "M1")
    _print_scenario_intro(scenario)

    print("\n>>> Turno 1 — messaggio vago (manca ID server)")
    ticket = process_ticket(STM_TURN1)
    if ticket is None:
        return

    if ticket.status == "TRIAGED":
        print(
            "\n[NOTA DIDATTICA] L'LLM ha completato il triage al turno 1. "
            "Eseguiamo comunque il turno 2 per mostrare continue_ticket e la cronologia."
        )

    print(f"\n>>> Turno 2 — stesso ticket #{ticket.id}")
    continue_ticket(ticket.id, STM_TURN2)


def run_l11_resilience_demo() -> None:
    """Demo Lezione 11: pipeline resiliente con self-correction (API reale)."""
    print("\n" + "=" * 72)
    print("SCENARIO L11 — Resilienza e Self-Correction")
    print("=" * 72)
    print(
        "Obiettivo: osservare validazione JSON con retry in-context "
        "(max 3) e emergency fallback se la validazione fallisce."
    )
    print("Messaggio di test: ticket IT standard (VPN).")
    print("-" * 72)
    manuale = load_it_manual()
    testo = (
        "Urgente! Ho un blocco completo sulla VPN tecnica e non riesco "
        "ad accedere ai sistemi da stamattina."
    )
    result, stats = triage_message(testo, manuale, return_stats=True)
    print(f"\n[RISULTATO] categoria={result.categoria} priorita={result.priorita}")
    print(f"[STATS] tentativi={stats.attempts} self_correction={stats.used_self_correction}")
    print(f"        emergency_fallback={stats.used_emergency_fallback}")
    if result.azione_eseguita:
        print(f"        azione_eseguita={result.azione_eseguita}")


def run_l10_rag_demo() -> None:
    """Demo Lezione 10: RAG semantica su policy (percorso principale; keyword solo se fallisce)."""
    print("\n" + "=" * 72)
    print("SCENARIO L10 — RAG semantica su data/policy.txt")
    print("=" * 72)
    print(
        "Obiettivo: mostrare che una query con sinonimi concettuali "
        "(annullare contratto / riavere soldi) recupera il paragrafo su "
        "recesso/rimborso 14 giorni senza match lessicale esatto."
    )
    print(f"\nQuery utente: {L10_SYNONYM_QUERY}")
    print("-" * 72)

    print("\n[RISULTATO RAG semantica]")
    try:
        result = semantic_policy_search(L10_SYNONYM_QUERY, POLICY_PATH)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"[ERRORE embeddings] {exc}")
        result = None

    if result is not None:
        print(format_semantic_result(result))
        print("-" * 72)
        print(f"[OK] RAG semantica: score={result.score:.3f} (soglia 0.38)")
    else:
        fallback = search_policy(L10_SYNONYM_QUERY)
        print(fallback)
        print("-" * 72)
        print(
            "[NOTA] RAG non disponibile o sotto soglia — "
            "mostrato fallback keyword (eccezione, non percorso principale)."
        )


def run_ltm_demo() -> None:
    scenario = next(s for s in DEMO_SCENARIOS if s.id == "M2")
    _print_scenario_intro(scenario)

    demo_db = seed_marco_sqlite(4, DEMO_M2_DB_PATH, reset=True)
    print(
        f"[DEMO M2] Lo storico per search_long_term_history è in:\n"
        f"         {demo_db}\n"
        f"         (database SQLite isolato, non mescolato con data/triage_system.db)"
    )

    print("\n>>> Turno unico — quinto ticket di Marco (dopo 4 incidenti in seed)")
    with _patch_sqlite_db(demo_db):
        process_ticket(LTM_MARCO_TICKET)


def _persist_react_result(user_input: str, result) -> None:
    cliente = extract_cliente_nome(user_input) or "Anonimo"
    log_triage_to_sqlite(
        {
            "cliente_nome": cliente,
            "categoria": result.categoria,
            "priorita": result.priorita,
            "sentiment": detect_sentiment_label(user_input),
            "riassunto_breve": result.riassunto_breve,
            "lingua": "Italiano",
            "azione_eseguita": result.azione_eseguita or "Nessuna",
        }
    )


def process_ticket_react(user_input: str, session_id: str | None = None):
    """Wrapper demo ReAct: triage multi-step con optional Short-Term Memory."""
    manuale = load_it_manual()
    result = react_triage(user_input, manuale, session_id=session_id)
    _persist_react_result(user_input, result)
    return result


def run_l13_react_demo() -> None:
    """Demo Lezione 13: loop ReAct + persistenza SQLite indicizzata."""
    print("\n" + "=" * 72)
    print("   IMPESUD AGENTIC TRIAGE - SUITE REACT & SQLITE   ")
    print("=" * 72)
    print(
        "Obiettivo: osservare il ciclo Thought → Action → Observation "
        "e la scrittura indicizzata su data/triage_system.db."
    )
    print(f"\nTicket: {L13_TICKET_1}")
    print("-" * 72)

    init_db()
    manuale = load_it_manual()
    result = react_triage(L13_TICKET_1, manuale)
    _persist_react_result(L13_TICKET_1, result)
    print(f"\n📊 Verdetto Finale Strutturato:\n{result.model_dump_json(indent=2)}")


def run_l14_planning_demo() -> None:
    """Demo Lezione 14: ReAct multi-turn con STM, max_steps=4 e LTM SQLite."""
    print("\n" + "=" * 72)
    print("   IMPESUD AGENTIC TRIAGE - SUITE REACT & SQLITE   ")
    print("=" * 72)
    print(
        "Obiettivo: verificare Short-Term Memory (session_01), max_steps=4 "
        "e storico cliente su SQLite al secondo ticket."
    )
    print("-" * 72)

    init_db()

    print(f"\n📥 Ricezione Ticket 1: {L13_TICKET_1}")
    process_ticket_react(L13_TICKET_1, session_id="session_01")

    print("-" * 50)

    print(f"📥 Ricezione Ticket 2 (Verifica ReAct Multi-Step): {L14_TICKET_2}")
    risultato = process_ticket_react(L14_TICKET_2, session_id="session_01")

    print(f"\n📊 Verdetto Finale Strutturato salvato in DB:\n{risultato.model_dump_json(indent=2)}")



def run_l15_topology_demo() -> None:
    """Demo Lezione 15: topologie multi-agente e hand-off Blackboard (senza LLM)."""
    from orchestration.models import CommunicationTopology
    from orchestration.topologies import IMPESUD_AGENT_TEAM, TOPOLOGY_CATALOG, simulate_analyst_handoff

    print("\n" + "=" * 72)
    print("SCENARIO L15 — Modelli di Coordinazione e Sistemi Distribuiti")
    print("=" * 72)
    print(
        "Obiettivo: confrontare le topologie di comunicazione e simulare "
        "un hand-off Analyst → Resolver su SharedHandoffContext."
    )
    print("-" * 72)

    for info in TOPOLOGY_CATALOG:
        print(f"\n[{info.topology.value.upper()}]")
        print(f"  Controllo: {info.control_mechanism}")
        print(f"  Caso d'uso: {info.ideal_use_case}")
        print(f"  Impesud: {info.impesud_mapping}")

    print("\n" + "-" * 72)
    print("SQUADRA IMPESUD (Role / Goal / Tool partizionati)")
    for agent in IMPESUD_AGENT_TEAM:
        print(f"\n  {agent.name} — {agent.role}")
        print(f"    Goal: {agent.goal}")
        print(f"    Tools: {', '.join(agent.tools)}")

    print("\n" + "-" * 72)
    print(f"SIMULAZIONE HAND-OFF (topologia sequenziale)\nTicket: {L13_TICKET_1}")
    handoff = simulate_analyst_handoff(
        L13_TICKET_1,
        topology=CommunicationTopology.SEQUENTIAL,
        storico_summary="Nessun ticket precedente in DB demo",
    )
    print(handoff.model_dump_json(indent=2))
    print(
        "\n[NOTA DIDATTICA] Il SecurityResolver (L16) consumerà questo Blackboard "
        "per policy RAG, escalation e JSON finale."
    )

def run_demo() -> None:
    """Ordine didattico: smoke → short-term → long-term."""
    init_db()
    print(
        "\nDEMO LEZIONE 9 — Memoria agentica\n"
        "Ordine: M3 (pipeline) → M1 (thread) → M2 (storico SQLite)\n"
    )
    run_smoke_demo()
    run_stm_demo()
    run_ltm_demo()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demo Lezioni 9–15 — memoria, RAG, resilienza, ReAct/SQLite, multi-agent (OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--scenario",
        choices=["m1", "m2", "m3", "l10", "l11", "l13", "l14", "l15", "all"],
        default="all",
        help="Esegue un solo scenario o tutti (default: all = M3→M1→M2)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    init_db()
    print(f"[SQLite] Database pronto: {TRIAGE_DB_PATH}", flush=True)
    args = _parse_args()
    if args.scenario == "all":
        run_demo()
    elif args.scenario == "m1":
        run_stm_demo()
    elif args.scenario == "m2":
        run_ltm_demo()
    elif args.scenario == "m3":
        run_smoke_demo()
    elif args.scenario == "l10":
        run_l10_rag_demo()
    elif args.scenario == "l11":
        run_l11_resilience_demo()
    elif args.scenario == "l13":
        run_l13_react_demo()
    elif args.scenario == "l14":
        run_l14_planning_demo()
    elif args.scenario == "l15":
        run_l15_topology_demo()
