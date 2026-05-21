from paths import MANUALE_IT_PATH
from client import call_llm
from parsing.parser import parse_llm_output
from prompts.triage_v1 import build_prompt
from schemas.ticket import Ticket, TriageResult
from storage.store import next_ticket_id, save_ticket
from tools.enrichment import enrich_priority
from tools.logger import log_event
from tools.router import assign_to_team


def load_it_manual() -> str:
    """Carica il manuale IT; solleva FileNotFoundError se assente."""
    return MANUALE_IT_PATH.read_text(encoding="utf-8")


def process_ticket(user_input: str) -> Ticket | None:
    """
    Pipeline Parte 1 + Parte 2:

    1. Ricezione ticket
    2. Assegnazione ID + save OPEN
    3. Chiamata LLM + parsing/validazione (CoT + manuale IT)
    4. Enrichment deterministico
    5. Stato TRIAGED + save
    6. Routing team + save snapshot finale
    7. Logging
    """
    try:
        log_event("ticket_received", {"input": user_input})

        ticket = Ticket(
            id=next_ticket_id(),
            status="OPEN",
            messaggio_originale=user_input,
        )
        save_ticket(ticket)
        log_event("ticket_saved", {"ticket": ticket.model_dump(), "phase": "open"})

        manuale = load_it_manual()
        prompt = build_prompt(user_input, manuale)
        raw_output = call_llm(prompt)
        log_event("llm_raw_response", {"response": raw_output})

        triage: TriageResult = parse_llm_output(raw_output)
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
        log_event("ticket_processed", {"ticket": ticket.model_dump()})

        print("\n=== TICKET PROCESSATO ===")
        print(ticket.model_dump())
        return ticket

    except (FileNotFoundError, ValueError, OSError) as e:
        log_event("error", {"message": str(e), "input": user_input})
        print("\n[ERRORE]", str(e))
        return None

# Ticket dello studente (Scenario D): simile al few-shot VPN, formulazione didattica ufficiale
VPN_STUDENT_TICKET = (
    "Ciao, non riesco a collegarmi da casa alla rete aziendale, "
    "mi dà errore di connessione."
)

# Ticket ambiguo (Scenario E): SALES vs IT — risoluzione via manuale (RAG)
AMBIGUOUS_RAG_TICKET = (
    "Vorrei acquistare il corso online ma il sito non carica "
    "la pagina di pagamento, potete aiutarmi?"
)

# Stesso dominio dei few-shot, testi diversi (A–C, E); D = ticket studente VPN
DEMO_SCENARIOS: list[tuple[str, str]] = [
    (
        "A — IT (accesso email)",
        "Non riesco più ad accedere alla casella aziendale, risulta bloccata",
    ),
    (
        "B — BILLING (pagamento)",
        "Ho fatto un bonifico la settimana scorsa, avete ricevuto il pagamento?",
    ),
    (
        "C — SECURITY (spam)",
        "Investi in crypto e guadagni migliaia di euro! Clicca subito per info!!!",
    ),
    ("D — IT / VPN (ticket studente)", VPN_STUDENT_TICKET),
    ("E — Ambiguo (SALES vs IT, RAG)", AMBIGUOUS_RAG_TICKET),
]


def run_demo_scenarios() -> None:
    """Esegue i 5 scenari di valutazione (incluso ambiguo RAG)."""
    for label, message in DEMO_SCENARIOS:
        print(f"\n\n--- SCENARIO {label} ---")
        process_ticket(message)


# Alias per compatibilità con invocazioni precedenti
run_tests = run_demo_scenarios


if __name__ == "__main__":
    run_demo_scenarios()
