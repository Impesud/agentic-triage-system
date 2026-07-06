"""
Demo didattiche Settimana 12 — Lezioni 15, 16 e 17 (multi-agente).

Documentazione demo live: docs/SETTIMANA_12_DEMO_LIVE.md

Esecuzione:
  PYTHONPATH=src python3 src/main.py              # default: solo l15 (senza LLM)
  PYTHONPATH=src python3 src/main.py --scenario l15
  PYTHONPATH=src python3 src/main.py --scenario l16a
  PYTHONPATH=src python3 src/main.py --scenario l16b
  PYTHONPATH=src python3 src/main.py --scenario l17a
  PYTHONPATH=src python3 src/main.py --scenario l17b
  PYTHONPATH=src python3 src/main.py --scenario all   # L15 → L16a → L16b → L17a → L17b

Al termine viene scritto logs/week12_demo_report.html
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from analytics.week12_report import (
    BenchmarkRow,
    L17aRunRow,
    Week12ReportBuilder,
)
from logic import multi_agent_triage, react_triage
from memory.extractors import detect_sentiment_label, extract_cliente_nome
from orchestration.api_guard import skip_llm_block
from paths import LOG_FILE_PATH, MANUALE_IT_PATH, TRIAGE_DB_PATH, WEEK12_REPORT_PATH
from tools.logger import init_db, log_triage_to_sqlite

L16_TICKET = (
    "Sono Marco Rossi. Ho un budget di 15.000€ per un progetto AI "
    "e voglio parlare con un manager."
)

L13_TICKET_1 = L16_TICKET

WEEK12_SCENARIOS = ("l15", "l16a", "l16b", "l17a", "l17b", "all")


def load_it_manual() -> str:
    return MANUALE_IT_PATH.read_text(encoding="utf-8")


def seed_marco_angry_history(
    n: int = 4,
    log_path: Path | None = None,
    *,
    reset: bool = False,
) -> Path:
    """Scrive n ticket_processed IT+ARRABBIATO per Marco (fixture test)."""
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
    return path


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


def _write_report(report: Week12ReportBuilder) -> Path:
    path = report.write_html()
    print(f"\n[REPORT HTML] Report salvato: {path}", flush=True)
    return path


def _register_api_skip(report: Week12ReportBuilder, scenario: str) -> None:
    """Registra scenario saltato per API key mancante (report HTML completo)."""
    reason = "OPENAI_API_KEY assente in .env"
    report.record_skip(scenario, reason)
    if scenario == "l16a":
        report.add_triage_scenario(
            scenario_id="l16a",
            lesson="16",
            title="CrewAI sequenziale",
            skipped=True,
            skip_reason=reason,
        )
    elif scenario == "l16b":
        report.add_triage_scenario(
            scenario_id="l16b",
            lesson="16",
            title="AutoGen GroupChat",
            skipped=True,
            skip_reason=reason,
        )


def run_l15_topology_demo(*, report: Week12ReportBuilder | None = None) -> None:
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
        "\n[NOTA DIDATTICA] Il SecurityResolver (L16–L17) consumerà questo Blackboard "
        "per policy RAG, escalation e JSON finale."
    )

    if report is not None:
        report.set_l15(
            ticket=L13_TICKET_1,
            topologies=[info.topology.value for info in TOPOLOGY_CATALOG],
            agents=[
                {
                    "name": a.name,
                    "role": a.role,
                    "goal": a.goal,
                    "tools": list(a.tools),
                }
                for a in IMPESUD_AGENT_TEAM
            ],
            handoff=handoff.model_dump(),
        )


def _run_l16_demo(
    orchestrator: Literal["crewai", "autogen"],
    title: str,
    scenario_id: str,
    *,
    report: Week12ReportBuilder | None = None,
) -> None:
    """Demo Lezione 16: orchestrazione multi-agent con CrewAI o AutoGen."""
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    print(f"Ticket: {L16_TICKET}")
    print("-" * 72)
    init_db()
    manuale = load_it_manual()
    t0 = time.perf_counter()
    result = multi_agent_triage(
        L16_TICKET,
        manuale,
        orchestrator=orchestrator,
        enable_optimizations=True,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    _persist_react_result(L16_TICKET, result)
    print(f"\n📊 Verdetto Finale Strutturato:\n{result.model_dump_json(indent=2)}")

    if report is not None:
        report.add_triage_scenario(
            scenario_id=scenario_id,
            lesson="16",
            title=title,
            wall_ms=elapsed_ms,
            result=result.model_dump(),
        )


def run_l16a_crew_demo(*, report: Week12ReportBuilder | None = None) -> None:
    """Demo Lezione 16a: CrewAI Process.sequential (topologia pipeline)."""
    _run_l16_demo(
        "crewai",
        "SCENARIO L16a — Orchestrazione CrewAI (Sequenziale)",
        "l16a",
        report=report,
    )


def run_l16b_autogen_demo(*, report: Week12ReportBuilder | None = None) -> None:
    """Demo Lezione 16b: AutoGen RoundRobinGroupChat (topologia collaborativa)."""
    _run_l16_demo(
        "autogen",
        "SCENARIO L16b — Orchestrazione AutoGen (Collaborativa)",
        "l16b",
        report=report,
    )


def run_l17a_pruning_demo(*, report: Week12ReportBuilder | None = None) -> None:
    """Demo Lezione 17a: confronto ReAct baseline vs compact/cache vs full opt."""
    from logic import ReactRunMetrics, _SHORT_TERM_STORE

    print("\n" + "=" * 72)
    print("SCENARIO L17a — Message Pruning e Context Window")
    print("=" * 72)
    print(f"Ticket: {L16_TICKET}")
    print("-" * 72)

    init_db()
    manuale = load_it_manual()
    runs: list[tuple[str, float, int, ReactRunMetrics | None]] = []
    report_rows: list[L17aRunRow] = []

    configs = [
        ("baseline (no opt)", dict(enable_optimizations=False, session_id="l17a_baseline", return_metrics=True)),
        (
            "compact + cache",
            dict(
                enable_optimizations=True,
                enable_pruning=False,
                enable_cache=True,
                enable_compact_output=True,
                session_id="l17a_compact",
                return_metrics=True,
            ),
        ),
        (
            "full (pruning + cache + compact)",
            dict(
                enable_optimizations=True,
                session_id="l17a_full",
                return_metrics=True,
            ),
        ),
    ]

    for label, kwargs in configs:
        _SHORT_TERM_STORE.pop(kwargs["session_id"], None)
        print(f"\n[RUN] react_triage — {label}")
        t0 = time.perf_counter()
        outcome = react_triage(L16_TICKET, manuale, **kwargs)
        elapsed = (time.perf_counter() - t0) * 1000
        if isinstance(outcome, tuple):
            _result, metrics = outcome
        else:
            _result, metrics = outcome, None
        tokens = metrics.tokens_est if metrics else 0
        runs.append((label, elapsed, tokens, metrics))
        report_rows.append(
            L17aRunRow(
                label=label,
                wall_ms=elapsed,
                tokens_est=tokens,
                enable_pruning=metrics.enable_pruning if metrics else False,
                enable_cache=metrics.enable_cache if metrics else False,
                enable_compact_output=metrics.enable_compact_output if metrics else False,
                categoria=_result.categoria,
                priorita=_result.priorita,
            )
        )
        flags = ""
        if metrics:
            flags = (
                f" | pruning={metrics.enable_pruning} cache={metrics.enable_cache} "
                f"compact={metrics.enable_compact_output}"
            )
        print(f"   Tempo: {elapsed:.0f} ms | Token stimati: {tokens}{flags}")

    print("\n[CONFRONTO]")
    print(f"   {'Run':<32} {'ms':>8}  {'tokens':>8}")
    for label, ms, tok, _ in runs:
        print(f"   {label:<32} {ms:>8.0f}  {tok:>8}")
    print(
        "\n   Eventi attesi in activity.jsonl: message_pruning_applied, "
        "embedding_cache_hit, handoff_enriched_from_cache (su L16/L17 multi-agent)"
    )

    if report is not None:
        report.set_l17a_runs(report_rows)


def run_l17b_latency_demo(*, report: Week12ReportBuilder | None = None) -> None:
    """Demo Lezione 17b: benchmark latenza multi-percorso."""
    from benchmark_multi_agent import run_multi_agent_benchmark

    print("\n" + "=" * 72)
    print("SCENARIO L17b — Benchmark Latenza Pipeline Multi-Agente")
    print("=" * 72)
    init_db()
    results = run_multi_agent_benchmark()

    if report is not None:
        report.set_l17b_rows(
            [
                BenchmarkRow(
                    name=r.name,
                    wall_ms=r.wall_ms,
                    tokens_est=r.tokens_est,
                    categoria=r.categoria,
                )
                for r in results
            ]
        )


def run_week12_all(*, report: Week12ReportBuilder | None = None) -> None:
    """Sequenza didattica L15 → L16a → L16b → L17a → L17b."""
    init_db()
    print("\nDEMO SETTIMANA 12 — Multi-agente e performance (L15–L17)\n")
    run_l15_topology_demo(report=report)

    if skip_llm_block("L16a CrewAI"):
        if report is not None:
            report.record_skip("l16a", "OPENAI_API_KEY assente")
            report.add_triage_scenario(
                scenario_id="l16a",
                lesson="16",
                title="CrewAI sequenziale",
                skipped=True,
                skip_reason="OPENAI_API_KEY assente",
            )
    else:
        run_l16a_crew_demo(report=report)

    if skip_llm_block("L16b AutoGen"):
        if report is not None:
            report.record_skip("l16b", "OPENAI_API_KEY assente")
            report.add_triage_scenario(
                scenario_id="l16b",
                lesson="16",
                title="AutoGen GroupChat",
                skipped=True,
                skip_reason="OPENAI_API_KEY assente",
            )
    else:
        run_l16b_autogen_demo(report=report)

    if skip_llm_block("L17a pruning"):
        if report is not None:
            report.record_skip("l17a", "OPENAI_API_KEY assente")
    else:
        run_l17a_pruning_demo(report=report)

    if skip_llm_block("L17b benchmark"):
        if report is not None:
            report.record_skip("l17b", "OPENAI_API_KEY assente")
    else:
        run_l17b_latency_demo(report=report)


def _run_scenario_with_report(scenario: str, report: Week12ReportBuilder) -> bool:
    """
    Esegue uno scenario Settimana 12. Ritorna False se saltato (es. API key assente).
    """
    if scenario != "l15" and scenario != "all" and skip_llm_block(f"scenario {scenario}"):
        _register_api_skip(report, scenario)
        return False
    _SCENARIO_RUNNERS[scenario](report=report)
    return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demo Settimana 12 — Lezioni 15, 16 e 17 (multi-agente e performance)",
    )
    parser.add_argument(
        "--scenario",
        choices=list(WEEK12_SCENARIOS),
        default="l15",
        help="Demo L15–L17 (default: l15 senza LLM)",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Non generare il report HTML a fine esecuzione",
    )
    return parser.parse_args()


_SCENARIO_RUNNERS = {
    "l15": run_l15_topology_demo,
    "l16a": run_l16a_crew_demo,
    "l16b": run_l16b_autogen_demo,
    "l17a": run_l17a_pruning_demo,
    "l17b": run_l17b_latency_demo,
    "all": run_week12_all,
}


if __name__ == "__main__":
    import sys

    init_db()
    print(f"[SQLite] Database pronto: {TRIAGE_DB_PATH}", flush=True)
    args = _parse_args()
    report = Week12ReportBuilder(root_scenario=args.scenario)
    try:
        if args.scenario == "all":
            run_week12_all(report=report)
        else:
            _run_scenario_with_report(args.scenario, report)
    finally:
        if not args.no_report:
            _write_report(report)
