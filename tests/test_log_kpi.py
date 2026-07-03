from pathlib import Path

from analytics.log_kpi import (
    event_type_counts,
    format_kpi_report,
    load_events,
    self_correction_metrics,
    tool_usage_rate,
)

FIXTURE = Path(__file__).parent / "fixtures" / "activity_sample.jsonl"


def test_load_events_from_fixture():
    events = load_events(FIXTURE)
    assert len(events) == 5
    assert events[0]["event_type"] == "ticket_received"


def test_self_correction_metrics():
    events = load_events(FIXTURE)
    metrics = self_correction_metrics(events)
    assert metrics["triage_json_retry"] == 1
    assert metrics["emergency_fallback"] == 1
    assert metrics["error"] == 1


def test_event_type_counts():
    events = load_events(FIXTURE)
    counts = event_type_counts(events)
    assert counts["ticket_received"] == 1
    assert counts["ticket_processed"] == 1


def test_format_kpi_report_contains_sections():
    events = load_events(FIXTURE)
    report = format_kpi_report(events)
    assert "=== KPI DA activity.jsonl ===" in report
    assert "triage_json_retry" in report
    assert "emergency_fallback" in report


def test_tool_usage_rate_empty_payload():
    events = [{"event_type": "ping", "payload": {}}]
    assert tool_usage_rate(events) == {}


def test_performance_metrics_l17():
    from analytics.log_kpi import performance_metrics

    events = [
        {"event_type": "message_pruning_applied", "payload": {}},
        {"event_type": "embedding_cache_hit", "payload": {}},
        {"event_type": "handoff_enriched_from_cache", "payload": {}},
    ]
    metrics = performance_metrics(events)
    assert metrics["message_pruning_applied"] == 1
    assert metrics["embedding_cache_hit"] == 1
    assert metrics["handoff_enriched_from_cache"] == 1
