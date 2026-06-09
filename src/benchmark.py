"""
Suite di benchmark agentico — Lezione 12.

Esegue 5 ticket di test sulla pipeline resiliente (triage_message + self-correction)
e stampa il report KPI richiesto dal corso.
"""

from __future__ import annotations

import time

from logic import ClarificationNeeded, triage_message
from paths import MANUALE_IT_PATH

BENCHMARK_DATASET: tuple[str, ...] = (
    "Urgente! Ho un blocco completo sulla VPN tecnica e non riesco ad accedere ai sistemi da stamattina.",
    "COMPRA ADESSO BITCOIN SCONTATI DEL 90% CLICCANDO SU QUESTO LINK DI SPAM IMMEDIATO!!",
    "Buongiorno, vorrei informazioni commerciali per strutturare un corso enterprise di AI Agentic.",
    "Ho riscontrato una discrepanza di prezzo sulla fattura numero 44, richiedo ricalcolo.",
    "Potete mettermi in contatto con un responsabile? Abbiamo un budget aziendale di 12.000 euro.",
)

# Casi didattici opzionali (sostituire temporaneamente in BENCHMARK_DATASET per osservare il comportamento):
# - Testo libero / prompt injection → ClarificationNeeded (no retry; in main.py ticket resta OPEN)
# - JSON incompleto ma che inizia con "{" → self-correction max 3 (vedi pytest -k self_correction)


def _load_manuale() -> str:
    return MANUALE_IT_PATH.read_text(encoding="utf-8")


def _is_emergency_fallback(azione_eseguita: str | None) -> bool:
    return bool(azione_eseguita and "Fallback" in azione_eseguita)


def run_triage_benchmark(
    *, manuale: str | None = None
) -> tuple[int, int, int, float]:
    """
    Esegue il benchmark e stampa il report.
    Ritorna (successi_validati, interventi_fallback, chiarimenti_richiesti, tempo_totale_sec).
    """
    print("==================================================")
    print("   IMPESUD AGENTIC SYSTEM - SUITE DI BENCHMARK   ")
    print("==================================================\n")
    print(
        "[NOTA] Questa run usa l'API OpenAI reale (costo token). "
        "In CI si usano i test mock in tests/test_benchmark.py.\n"
    )

    if manuale is None:
        manuale = _load_manuale()

    successi_validati = 0
    interventi_fallback = 0
    chiarimenti_richiesti = 0
    tempo_inizio = time.time()
    total = len(BENCHMARK_DATASET)

    for i, ticket_text in enumerate(BENCHMARK_DATASET, start=1):
        print(f"🚀 [Case {i}/{total}] Elaborazione in corso...")
        try:
            risultato, stats = triage_message(ticket_text, manuale, return_stats=True)

            if stats.used_emergency_fallback or _is_emergency_fallback(risultato.azione_eseguita):
                interventi_fallback += 1
            else:
                successi_validati += 1

            azione = risultato.azione_eseguita or "(triage standard)"
            print(
                f"   📊 Risultato -> Cat: {risultato.categoria} | "
                f"Priorità: {risultato.priorita} | Azione: {azione}\n"
            )
        except ClarificationNeeded as exc:
            chiarimenti_richiesti += 1
            preview = exc.message[:120] + ("..." if len(exc.message) > 120 else "")
            print(
                f"   💬 [CHIARIMENTO] Risposta non-JSON (M1) — "
                f"in main.py il ticket resterebbe OPEN: {preview}\n"
            )
        except Exception as exc:
            print(f"   ❌ Errore critico non intercettato: {exc}\n")
            interventi_fallback += 1

    tempo_totale = time.time() - tempo_inizio
    print("==================================")
    print("=== REPORT DI BENCHMARK AGENTE ===")
    print("==================================")
    print(f"Successi immediati o riparati: {successi_validati}/{total}")
    print(f"Chiarimenti richiesti (non-JSON, M1): {chiarimenti_richiesti}/{total}")
    print(f"Interventi di Fallback di emergenza: {interventi_fallback}/{total}")
    print(f"⏱️ Tempo totale di esecuzione: {tempo_totale:.2f} secondi.")
    print("==================================")
    return successi_validati, interventi_fallback, chiarimenti_richiesti, tempo_totale


if __name__ == "__main__":
    run_triage_benchmark()
