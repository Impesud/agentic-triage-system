"""
Benchmark multi-percorso — Lezione 17.

Confronta latenza e token stimati tra pipeline agentiche (mock-friendly in CI).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from logic import ReactRunMetrics, TriageRunMetrics, multi_agent_triage, react_triage, triage_message
from orchestration.models import MultiAgentRunMetrics
from paths import MANUALE_IT_PATH
from tools.logger import log_event

L17_BENCHMARK_TICKET = (
    "Sono Marco Rossi. Ho un budget di 15.000€ per un progetto AI "
    "e voglio parlare con un manager."
)


@dataclass(frozen=True)
class PipelineRunResult:
    name: str
    wall_ms: float
    tokens_est: int | None
    cache_policy_hits: int | None = None
    cache_ltm_hits: int | None = None
    categoria: str | None = None


def _load_manuale() -> str:
    return MANUALE_IT_PATH.read_text(encoding="utf-8")


def _extract_tokens(extra: object) -> int | None:
    if isinstance(extra, (ReactRunMetrics, TriageRunMetrics, MultiAgentRunMetrics)):
        return extra.tokens_est
    if isinstance(extra, dict):
        val = extra.get("tokens_est")
        return int(val) if val is not None else None
    return None


def _extract_cache(extra: object) -> tuple[int | None, int | None]:
    if isinstance(extra, MultiAgentRunMetrics):
        return extra.cache_policy_hits, extra.cache_ltm_hits
    if isinstance(extra, dict):
        return extra.get("cache_policy_hits"), extra.get("cache_ltm_hits")
    return None, None


def _run_labeled(name: str, fn) -> PipelineRunResult:
    start = time.perf_counter()
    outcome = fn()
    wall_ms = (time.perf_counter() - start) * 1000

    if isinstance(outcome, tuple):
        result, extra = outcome
    else:
        result, extra = outcome, {}

    policy_hits, ltm_hits = _extract_cache(extra)
    report = PipelineRunResult(
        name=name,
        wall_ms=wall_ms,
        tokens_est=_extract_tokens(extra),
        cache_policy_hits=policy_hits,
        cache_ltm_hits=ltm_hits,
        categoria=getattr(result, "categoria", None),
    )
    log_event(
        "pipeline_latency_report",
        {
            "path": name,
            "wall_ms": round(wall_ms, 1),
            "tokens_est": report.tokens_est,
            "categoria": report.categoria,
        },
    )
    return report


def run_multi_agent_benchmark(*, manuale: str | None = None) -> list[PipelineRunResult]:
    """Esegue confronto su ticket Marco Rossi (API reale se non mockato)."""
    if manuale is None:
        manuale = _load_manuale()

    ticket = L17_BENCHMARK_TICKET
    print("==================================================")
    print("   IMPESUD - BENCHMARK PERFORMANCE MULTI-AGENT   ")
    print("==================================================\n")
    print(f"Ticket: {ticket}\n")

    results: list[PipelineRunResult] = []

    results.append(
        _run_labeled(
            "triage_message",
            lambda: triage_message(ticket, manuale, return_metrics=True),
        )
    )
    results.append(
        _run_labeled(
            "triage_message (cache)",
            lambda: triage_message(
                ticket, manuale, enable_optimizations=True, return_metrics=True
            ),
        )
    )
    results.append(
        _run_labeled(
            "react_triage (no opt)",
            lambda: react_triage(
                ticket, manuale, enable_optimizations=False, return_metrics=True
            ),
        )
    )
    results.append(
        _run_labeled(
            "react_triage (full opt)",
            lambda: react_triage(
                ticket, manuale, enable_optimizations=True, return_metrics=True
            ),
        )
    )

    try:
        results.append(
            _run_labeled(
                "multi_agent_triage (crewai)",
                lambda: multi_agent_triage(
                    ticket, manuale, orchestrator="crewai", return_metrics=True
                ),
            )
        )
    except ImportError as exc:
        print(f"[SKIP] crewai: {exc}")

    try:
        results.append(
            _run_labeled(
                "multi_agent_triage (autogen)",
                lambda: multi_agent_triage(
                    ticket, manuale, orchestrator="autogen", return_metrics=True
                ),
            )
        )
    except ImportError as exc:
        print(f"[SKIP] autogen: {exc}")

    print(f"{'Pipeline':<34} {'ms':>8}  {'tokens':>8}  categoria")
    print("-" * 70)
    for row in results:
        tok = row.tokens_est if row.tokens_est is not None else "-"
        cat = row.categoria or "-"
        print(f"{row.name:<34} {row.wall_ms:>8.0f}  {str(tok):>8}  {cat}")
    print()
    return results


if __name__ == "__main__":
    run_multi_agent_benchmark()
