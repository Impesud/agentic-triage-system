"""
Orchestrazione ticket e demo didattiche Lezione 9 (memoria short/long-term).

Esecuzione demo:
  PYTHONPATH=src python src/main.py              # M3 → M1 → M2
  PYTHONPATH=src python src/main.py --scenario m1
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from logic import ClarificationNeeded, triage_message
from memory.extractors import detect_sentiment_label, extract_cliente_nome
from memory.session_manager import SessionManager
from paths import DEMO_M2_LOG_PATH, LOG_FILE_PATH, MANUALE_IT_PATH
from schemas.ticket import Ticket
from storage.store import get_current_ticket, next_ticket_id, save_ticket
from tools import history_tools
from tools.enrichment import enrich_priority
from tools.logger import log_event
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
            "logs/demo_m2_activity.jsonl",
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
    log_event(
        "ticket_processed",
        {
            "ticket": ticket.model_dump(),
            "cliente_nome": extract_cliente_nome(full_text),
            "sentiment": detect_sentiment_label(full_text),
        },
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


def _patch_long_term_log(path: Path):
    """Contesto: search_long_term_history legge da path isolato (solo demo M2)."""
    return _LogPathPatch(path)


class _LogPathPatch:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._previous: Path | None = None

    def __enter__(self) -> Path:
        self._previous = history_tools.LOG_FILE_PATH
        history_tools.LOG_FILE_PATH = self._path
        return self._path

    def __exit__(self, *args: object) -> None:
        if self._previous is not None:
            history_tools.LOG_FILE_PATH = self._previous


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


def run_ltm_demo() -> None:
    scenario = next(s for s in DEMO_SCENARIOS if s.id == "M2")
    _print_scenario_intro(scenario)

    demo_log = seed_marco_angry_history(4, DEMO_M2_LOG_PATH, reset=True)
    print(
        f"[DEMO M2] Lo storico per search_long_term_history è in:\n"
        f"         {demo_log}\n"
        f"         (non mescolato con logs/activity.jsonl principale)"
    )

    print("\n>>> Turno unico — quinto ticket di Marco (dopo 4 incidenti in seed)")
    with _patch_long_term_log(demo_log):
        process_ticket(LTM_MARCO_TICKET)


def run_demo() -> None:
    """Ordine didattico: smoke → short-term → long-term."""
    print(
        "\nDEMO LEZIONE 9 — Memoria agentica\n"
        "Ordine: M3 (pipeline) → M1 (thread) → M2 (storico audit)\n"
    )
    run_smoke_demo()
    run_stm_demo()
    run_ltm_demo()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demo Lezione 9 — memoria short/long-term (richiede OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--scenario",
        choices=["m1", "m2", "m3", "all"],
        default="all",
        help="Esegue un solo scenario o tutti (default: all = M3→M1→M2)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.scenario == "all":
        run_demo()
    elif args.scenario == "m1":
        run_stm_demo()
    elif args.scenario == "m2":
        run_ltm_demo()
    elif args.scenario == "m3":
        run_smoke_demo()
