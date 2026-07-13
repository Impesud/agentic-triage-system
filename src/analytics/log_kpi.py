"""
KPI da logs/activity.jsonl — Lezione 12 (Log-Driven Development).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from paths import LOG_FILE_PATH


def load_events(path: Path | None = None) -> list[dict[str, Any]]:
    """Carica eventi strutturati da un file JSONL."""
    log_path = path or LOG_FILE_PATH
    if not log_path.exists():
        return []

    events: list[dict[str, Any]] = []
    with open(log_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def event_type_counts(events: list[dict[str, Any]]) -> Counter[str]:
    return Counter(e.get("event_type", "unknown") for e in events)


def tool_usage_rate(events: list[dict[str, Any]]) -> dict[str, int]:
    """
    Conta occorrenze indicative di tool nei payload (ticket_processed, log agente).
    Proxy per Tool Usage Rate quando i tool non hanno event_type dedicato.
    """
    counts: Counter[str] = Counter()
    markers = (
        "search_policy",
        "search_long_term_history",
        "notify_manager",
        "[AGENTE] Attivazione tool",
    )
    for event in events:
        blob = json.dumps(event.get("payload", {}), ensure_ascii=False)
        for name in markers:
            if name in blob:
                counts[name] += 1
    return dict(counts)


def self_correction_metrics(events: list[dict[str, Any]]) -> dict[str, int]:
    """Metriche su soft error e emergency fallback (Lezione 11)."""
    types = event_type_counts(events)
    return {
        "triage_json_retry": types.get("triage_json_retry", 0),
        "emergency_fallback": types.get("emergency_fallback", 0),
        "error": types.get("error", 0),
    }




def security_metrics(events: list[dict[str, Any]]) -> dict[str, int]:
    """Metriche Lezione 18: guardrail input, hand-off, tool gate."""
    types = event_type_counts(events)
    return {
        "security_input_blocked": types.get("security_input_blocked", 0),
        "security_handoff_blocked": types.get("security_handoff_blocked", 0),
        "security_tool_denied": types.get("security_tool_denied", 0),
        "handoff_field_redacted": types.get("handoff_field_redacted", 0),
        "isolate_account_stub": types.get("isolate_account_stub", 0),
    }


def hitl_metrics(events: list[dict[str, Any]]) -> dict[str, int]:
    """Metriche Lezione 19: breakpoint, approve, reject, resume."""
    types = event_type_counts(events)
    return {
        "hitl_breakpoint_reached": types.get("hitl_breakpoint_reached", 0),
        "hitl_session_approved": types.get("hitl_session_approved", 0),
        "hitl_session_rejected": types.get("hitl_session_rejected", 0),
        "hitl_session_resumed": types.get("hitl_session_resumed", 0),
    }


def performance_metrics(events: list[dict[str, Any]]) -> dict[str, int]:
    """Metriche Lezione 17: pruning, cache embedding, latenza pipeline."""
    types = event_type_counts(events)
    return {
        "message_pruning_applied": types.get("message_pruning_applied", 0),
        "embedding_cache_hit": types.get("embedding_cache_hit", 0),
        "pipeline_latency_report": types.get("pipeline_latency_report", 0),
        "crew_triage_complete": types.get("crew_triage_complete", 0),
        "autogen_triage_complete": types.get("autogen_triage_complete", 0),
        "multi_agent_fallback": types.get("multi_agent_fallback", 0),
        "handoff_enriched_from_cache": types.get("handoff_enriched_from_cache", 0),
    }


def telemetry_metrics(events: list[dict[str, Any]]) -> dict[str, int | float]:
    """Metriche Lezione 20: usage API, costo millesimi, latenza LLM."""
    types = event_type_counts(events)
    llm_calls = 0
    total_cost_milli = 0
    total_prompt = 0
    total_completion = 0
    latency_sum = 0
    complete_runs = 0

    for event in events:
        if event.get("event_type") == "llm_call_telemetry":
            llm_calls += 1
            payload = event.get("payload", {})
            total_prompt += int(payload.get("prompt_tokens", 0) or 0)
            total_completion += int(payload.get("completion_tokens", 0) or 0)
            latency_sum += int(payload.get("latency_ms", 0) or 0)
        if event.get("event_type") == "triage_telemetry_complete":
            complete_runs += 1
            payload = event.get("payload", {})
            total_cost_milli += int(payload.get("cost_usd_milli", 0) or 0)

    avg_latency = (latency_sum / llm_calls) if llm_calls else 0.0
    return {
        "llm_call_telemetry": types.get("llm_call_telemetry", 0),
        "triage_telemetry_complete": types.get("triage_telemetry_complete", 0),
        "telemetry_llm_calls": llm_calls,
        "telemetry_cost_usd_milli": total_cost_milli,
        "telemetry_prompt_tokens": total_prompt,
        "telemetry_completion_tokens": total_completion,
        "telemetry_avg_latency_ms": round(avg_latency, 1),
        "telemetry_complete_runs": complete_runs,
    }


def format_kpi_report(events: list[dict[str, Any]]) -> str:
    """Report testuale per terminale."""
    types = event_type_counts(events)
    tools = tool_usage_rate(events)
    correction = self_correction_metrics(events)
    performance = performance_metrics(events)
    security = security_metrics(events)
    hitl = hitl_metrics(events)
    telemetry = telemetry_metrics(events)
    lines = [
        "=== KPI DA activity.jsonl ===",
        f"Eventi totali: {len(events)}",
        "",
        "Conteggio per event_type:",
    ]
    for name, count in sorted(types.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"  {name}: {count}")
    lines.extend(["", "Tool usage (proxy su payload):"])
    if tools:
        for name, count in sorted(tools.items(), key=lambda x: -x[1]):
            lines.append(f"  {name}: {count}")
    else:
        lines.append("  (nessun marker tool trovato)")
    lines.extend(
        [
            "",
            "Self-correction / resilienza:",
            f"  triage_json_retry: {correction['triage_json_retry']}",
            f"  emergency_fallback: {correction['emergency_fallback']}",
            f"  error: {correction['error']}",
            "",
            "Performance multi-agent (L17):",
            f"  message_pruning_applied: {performance['message_pruning_applied']}",
            f"  embedding_cache_hit: {performance['embedding_cache_hit']}",
            f"  pipeline_latency_report: {performance['pipeline_latency_report']}",
            f"  crew_triage_complete: {performance['crew_triage_complete']}",
            f"  autogen_triage_complete: {performance['autogen_triage_complete']}",
            f"  multi_agent_fallback: {performance['multi_agent_fallback']}",
            f"  handoff_enriched_from_cache: {performance['handoff_enriched_from_cache']}",
            "",
            "Sicurezza multi-agent (L18):",
            f"  security_input_blocked: {security['security_input_blocked']}",
            f"  security_handoff_blocked: {security['security_handoff_blocked']}",
            f"  security_tool_denied: {security['security_tool_denied']}",
            f"  handoff_field_redacted: {security['handoff_field_redacted']}",
            "",
            "HITL multi-agent (L19):",
            f"  hitl_breakpoint_reached: {hitl['hitl_breakpoint_reached']}",
            f"  hitl_session_approved: {hitl['hitl_session_approved']}",
            f"  hitl_session_rejected: {hitl['hitl_session_rejected']}",
            f"  hitl_session_resumed: {hitl['hitl_session_resumed']}",
            "",
            "Telemetria strutturata (L20):",
            f"  llm_call_telemetry: {telemetry['llm_call_telemetry']}",
            f"  triage_telemetry_complete: {telemetry['triage_telemetry_complete']}",
            f"  cost_usd_milli (somma run): {telemetry['telemetry_cost_usd_milli']}",
            f"  prompt_tokens (somma chiamate): {telemetry['telemetry_prompt_tokens']}",
            f"  completion_tokens (somma chiamate): {telemetry['telemetry_completion_tokens']}",
            f"  latenza media per chiamata (ms): {telemetry['telemetry_avg_latency_ms']}",
            "==================================",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    events = load_events()
    print(format_kpi_report(events))


if __name__ == "__main__":
    main()
