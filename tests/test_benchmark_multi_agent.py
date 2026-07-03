"""Test benchmark multi-agent — Lezione 17."""

from unittest.mock import patch

from benchmark_multi_agent import run_multi_agent_benchmark
from logic import ReactRunMetrics, TriageRunMetrics
from orchestration.models import MultiAgentRunMetrics
from schemas.ticket import TriageResult

_VALID = TriageResult(
    analisi_problema="1. P. 2. C. 3. SALES. 4. HIGH.",
    categoria="SALES",
    priorita="HIGH",
    riassunto_breve="Budget AI manager",
    messaggio_originale="ticket demo",
)

_REACT_METRICS = ReactRunMetrics(
    tokens_est=120,
    enable_pruning=True,
    enable_cache=True,
    enable_compact_output=True,
)

_TRIAGE_METRICS = TriageRunMetrics(tokens_est=80)

_MULTI_METRICS = MultiAgentRunMetrics(
    tokens_est=200,
    handoff_enriched=True,
    cache_policy_hits=1,
    cache_ltm_hits=0,
    compact_manuale_resolver=True,
)


@patch("benchmark_multi_agent.multi_agent_triage")
@patch("benchmark_multi_agent.react_triage")
@patch("benchmark_multi_agent.triage_message")
def test_benchmark_multi_agent_mocked(mock_triage, mock_react, mock_multi):
    mock_triage.return_value = (_VALID, _TRIAGE_METRICS)
    mock_react.return_value = (_VALID, _REACT_METRICS)
    mock_multi.return_value = (_VALID, _MULTI_METRICS)

    results = run_multi_agent_benchmark(manuale="Manuale IT")
    assert len(results) >= 4
    assert results[0].name == "triage_message"
    assert results[0].tokens_est == 80
    assert results[2].tokens_est == 120
    assert results[-1].tokens_est == 200
