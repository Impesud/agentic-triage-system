"""Test telemetria strutturata L20."""

from unittest.mock import MagicMock

from orchestration.telemetry import (
    TelemetryCollector,
    apply_multi_agent_telemetry,
    compute_cost_usd_milli,
    enrich_azione_eseguita,
    load_model_pricing,
    migrate_tickets_telemetry_columns,
    parse_telemetry_from_azione,
    tickets_has_telemetry_columns,
)
from schemas.ticket import TriageResult


def test_compute_cost_usd_milli_formula():
    pricing = load_model_pricing("gpt-4.1-mini")
    # 1M input @ 0.40 + 0 output = 0.40 USD → 400 milli
    assert compute_cost_usd_milli(1_000_000, 0, pricing=pricing) == 400
    # 0 input + 1M output @ 1.60 = 1.60 USD → 1600 milli
    assert compute_cost_usd_milli(0, 1_000_000, pricing=pricing) == 1600
    # 1200 in + 340 out
    cost = compute_cost_usd_milli(1200, 340, pricing=pricing)
    assert cost == round((1200 * pricing.rate_in() + 340 * pricing.rate_out()) * 1000)


def test_collector_accumulates_calls():
    collector = TelemetryCollector(pipeline="test")
    collector.record_call(
        prompt_tokens=100,
        completion_tokens=50,
        latency_ms=120,
        call_kind="tool_turn",
    )
    collector.record_call(
        prompt_tokens=200,
        completion_tokens=80,
        latency_ms=300,
        call_kind="final_json",
    )
    assert collector.prompt_tokens == 300
    assert collector.completion_tokens == 130
    assert collector.latency_ms == 420
    assert collector.llm_calls == 2
    assert collector.cost_usd_milli() >= 0


def test_enrich_azione_eseguita_appends_block():
    collector = TelemetryCollector(pipeline="react_triage")
    collector.record_call(
        prompt_tokens=500,
        completion_tokens=100,
        latency_ms=200,
        call_kind="final_json",
    )
    out = enrich_azione_eseguita("notify_manager", collector)
    assert "notify_manager" in out
    assert "| TELEMETRY" in out
    assert "cost_milli=" in out
    assert "tokens_in=500" in out
    assert "llm_calls=1" in out


def test_enrich_azione_eseguita_idempotent():
    collector = TelemetryCollector(pipeline="x")
    collector.record_call(
        prompt_tokens=10,
        completion_tokens=5,
        latency_ms=1,
        call_kind="tool_turn",
    )
    once = enrich_azione_eseguita("base", collector)
    twice = enrich_azione_eseguita(once, collector)
    assert twice.count("TELEMETRY") == 1


def test_parse_telemetry_from_azione_roundtrip():
    collector = TelemetryCollector(pipeline="react_triage")
    collector.record_call(
        prompt_tokens=1200,
        completion_tokens=340,
        latency_ms=890,
        call_kind="tool_turn",
    )
    collector.record_call(
        prompt_tokens=800,
        completion_tokens=120,
        latency_ms=100,
        call_kind="final_json",
    )
    azione = enrich_azione_eseguita("tool list", collector)
    parsed = parse_telemetry_from_azione(azione)
    assert parsed["prompt_tokens"] == 2000
    assert parsed["completion_tokens"] == 460
    assert parsed["cost_usd_milli"] == collector.cost_usd_milli()
    assert parsed["latency_ms"] == 990
    assert parsed["llm_calls"] == 2


def test_migrate_tickets_telemetry_columns_idempotent(tmp_path):
    import sqlite3

    db = tmp_path / "t.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE tickets (
                id INTEGER PRIMARY KEY,
                cliente_nome TEXT,
                categoria TEXT
            )
            """
        )
        migrate_tickets_telemetry_columns(conn)
        conn.commit()
    assert tickets_has_telemetry_columns(db)
    with sqlite3.connect(db) as conn:
        migrate_tickets_telemetry_columns(conn)
        conn.commit()
    assert tickets_has_telemetry_columns(db)


def test_apply_multi_agent_telemetry_enriches_result():
    result = TriageResult(
        analisi_problema="test",
        categoria="IT",
        priorita="LOW",
        riassunto_breve="ok",
        messaggio_originale="help",
        azione_eseguita="Nessuna",
    )
    enriched, collector = apply_multi_agent_telemetry(
        result,
        pipeline="crewai",
        tokens_est=1000,
        latency_ms=5000,
    )
    assert "| TELEMETRY" in enriched.azione_eseguita
    assert collector.llm_calls == 1
    assert collector.sqlite_fields()["pipeline"] == "crewai"
