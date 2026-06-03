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


def format_kpi_report(events: list[dict[str, Any]]) -> str:
    """Report testuale per terminale."""
    types = event_type_counts(events)
    tools = tool_usage_rate(events)
    correction = self_correction_metrics(events)
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
            "==================================",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    events = load_events()
    print(format_kpi_report(events))


if __name__ == "__main__":
    main()
