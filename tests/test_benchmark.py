from io import StringIO
from unittest.mock import MagicMock, patch

from logic import ClarificationNeeded
from benchmark import BENCHMARK_DATASET, run_triage_benchmark


def _completion(content=None, tool_calls=None):
    msg = MagicMock(tool_calls=tool_calls, content=content)
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    return resp


_VALID = (
    '{"analisi_problema":"1. P. 2. C. 3. IT. 4. LOW.",'
    '"categoria":"IT","priorita":"LOW","riassunto_breve":"vpn ok",'
    '"messaggio_originale":"vpn"}'
)


@patch("benchmark.triage_message")
def test_run_triage_benchmark_report_format(mock_triage):
    from logic import TriageStats
    from schemas.ticket import TriageResult

    mock_triage.return_value = (
        TriageResult(
            analisi_problema="1. P. 2. C. 3. IT. 4. LOW.",
            categoria="IT",
            priorita="LOW",
            riassunto_breve="ok",
            messaggio_originale="x",
        ),
        TriageStats(attempts=1, used_self_correction=False, used_emergency_fallback=False),
    )

    import sys

    captured = StringIO()
    with patch.object(sys, "stdout", captured):
        successi, fallback, chiarimenti, _elapsed = run_triage_benchmark(manuale="Manuale test")

    out = captured.getvalue()
    assert successi == len(BENCHMARK_DATASET)
    assert fallback == 0
    assert chiarimenti == 0
    assert "=== REPORT DI BENCHMARK AGENTE ===" in out
    assert f"Successi immediati o riparati: {len(BENCHMARK_DATASET)}/{len(BENCHMARK_DATASET)}" in out
    assert "Chiarimenti richiesti (non-JSON, M1): 0/" in out
    assert "Interventi di Fallback di emergenza: 0/" in out
    assert mock_triage.call_count == len(BENCHMARK_DATASET)


@patch("benchmark.triage_message")
def test_run_triage_benchmark_counts_emergency_fallback(mock_triage):
    from logic import TriageStats
    from schemas.ticket import TriageResult

    mock_triage.return_value = (
        TriageResult(
            analisi_problema="1. P. 2. C. 3. GENERAL. 4. CRITICAL.",
            categoria="GENERAL",
            priorita="CRITICAL",
            riassunto_breve="FALLBACK test",
            messaggio_originale="x",
            azione_eseguita="Emergency Fallback attivato",
        ),
        TriageStats(attempts=3, used_self_correction=True, used_emergency_fallback=True),
    )

    import sys

    captured = StringIO()
    with patch.object(sys, "stdout", captured):
        successi, fallback, chiarimenti, _ = run_triage_benchmark(manuale="")

    assert successi == 0
    assert fallback == len(BENCHMARK_DATASET)
    assert chiarimenti == 0


@patch("benchmark.triage_message")
def test_run_triage_benchmark_counts_clarification_needed(mock_triage):
    mock_triage.side_effect = ClarificationNeeded(
        "Per favore descrivi il problema tecnico o commerciale."
    )

    import sys

    captured = StringIO()
    with patch.object(sys, "stdout", captured):
        successi, fallback, chiarimenti, _ = run_triage_benchmark(manuale="")

    out = captured.getvalue()
    assert successi == 0
    assert fallback == 0
    assert chiarimenti == len(BENCHMARK_DATASET)
    assert "[CHIARIMENTO]" in out
    assert "Errore critico non intercettato" not in out
    assert f"Chiarimenti richiesti (non-JSON, M1): {len(BENCHMARK_DATASET)}/" in out


@patch("logic.get_client")
def test_benchmark_integration_one_case_mocked(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.chat.completions.create.return_value = _completion(content=_VALID)

    from logic import triage_message

    result, stats = triage_message(BENCHMARK_DATASET[0], manuale="", return_stats=True)
    assert result.categoria == "IT"
    assert stats.used_emergency_fallback is False
