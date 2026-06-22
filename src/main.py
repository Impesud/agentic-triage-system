"""
Progetto 2 — Triage SOC su 10 scenari dataset_test.

Esecuzione:
  PYTHONPATH=src python3 scripts/init_triage_db.py
  PYTHONPATH=src python3 scripts/seed_progettino.py
  PYTHONPATH=src python3 src/main.py                    # tutti e 10 (+ report HTML)
  PYTHONPATH=src python3 src/main.py --scenario 4       # singolo scenario
  PYTHONPATH=src python3 src/main.py --no-html          # senza report HTML
  python3 scripts/open_report.py                        # apri ultimo report (WSL)
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dataset_test import DATASET_TEST, get_scenario
from logic import react_triage_progettino
from memory.extractors import detect_sentiment_label, extract_cliente_nome
from paths import MANUALE_IT_PATH, REPO_ROOT, TRIAGE_DB_PATH
from reporting.html_report import ScenarioReport, build_scenario_report, write_report
from tools.logger import init_db, log_triage_to_sqlite
from tools.router import team_for_category


def load_it_manual() -> str:
    return MANUALE_IT_PATH.read_text(encoding="utf-8")


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


def process_ticket_progettino(user_input: str, session_id: str | None = None):
    """
    Wrapper Progetto 2: react_triage con fallback SOC e gestione prompt injection.
    """
    manuale = load_it_manual()
    result = react_triage_progettino(user_input, manuale, session_id=session_id)
    _persist_react_result(user_input, result)
    team = team_for_category(result.categoria)
    print(f"\n=== PROGETTO 2 — TRIAGE COMPLETATO (team: {team}) ===")
    print(result.model_dump_json(indent=2))
    return result


def run_progettino_demo(
    scenarios: tuple | None = None,
    *,
    write_html: bool = True,
) -> Path | None:
    """Esegue gli scenari dataset_test in sequenza con report console e HTML."""
    batch = scenarios or DATASET_TEST
    print("\n" + "=" * 72)
    print("   PROGETTO 2 — DATASET TEST SOC")
    print("=" * 72)
    print("Prerequisito: PYTHONPATH=src python3 scripts/seed_progettino.py\n")

    init_db()
    manuale = load_it_manual()
    reports: list[ScenarioReport] = []

    for scenario in batch:
        print("\n" + "-" * 72)
        print(f">>> Scenario {scenario.number}/10: {scenario.title}")
        print(f"    Capacità: {scenario.capability}")
        print("-" * 72)
        result = react_triage_progettino(
            scenario.message,
            manuale,
            session_id=scenario.session_id,
        )
        team = team_for_category(result.categoria)
        _persist_react_result(scenario.message, result)
        reports.append(build_scenario_report(scenario, result, team))
        print(f"\n📊 Esito: {result.categoria} / {result.priorita} → team {team}")

    print("\n" + "=" * 72)
    print("REPORT PROGETTO 2")
    print("=" * 72)
    for entry in reports:
        print(
            f"  [{entry.number:02d}] {entry.title[:40]:40} | "
            f"{entry.categoria:8} | {entry.priorita:8} | {entry.team}"
        )

    if not write_html:
        return None

    report_path = write_report(reports)
    rel = report_path.relative_to(REPO_ROOT)
    print(f"\n[REPORT] Report HTML: {report_path}")
    print(f"[REPORT] Apri con: python3 scripts/open_report.py {rel}")
    return report_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Progetto 2 — triage SOC su dataset_test (OPENAI_API_KEY in .env)",
    )
    parser.add_argument(
        "--scenario",
        nargs="?",
        const="all",
        default="all",
        metavar="N",
        help="Numero scenario 1-10, oppure omit/all per tutti (default: all)",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Non generare report HTML in logs/reports/",
    )
    return parser.parse_args()


if __name__ == "__main__":
    init_db()
    print(f"[SQLite] Database pronto: {TRIAGE_DB_PATH}", flush=True)
    args = _parse_args()

    if args.scenario in (None, "all"):
        run_progettino_demo(write_html=not args.no_html)
    else:
        try:
            num = int(args.scenario)
        except ValueError as exc:
            raise SystemExit(
                f"Scenario non valido: {args.scenario!r}. Usa 1-10 o ometti per tutti."
            ) from exc
        if not 1 <= num <= 10:
            raise SystemExit(f"Scenario fuori range: {num}. Usa 1-10.")
        run_progettino_demo((get_scenario(num),), write_html=not args.no_html)
