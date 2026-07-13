"""Telemetria strutturata LLM — Lezione 20."""

from __future__ import annotations

import json
import re
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from client import MODEL
from paths import REPO_ROOT
from tools.logger import log_event

CallKind = Literal["tool_turn", "final_json"]
UsageSource = Literal["api", "estimated"]

_L20_TELEMETRY_COLUMNS = (
    "prompt_tokens",
    "completion_tokens",
    "cost_usd_milli",
    "latency_ms",
    "llm_calls",
    "pipeline",
)

current_telemetry_collector: ContextVar[TelemetryCollector | None] = ContextVar(
    "current_telemetry_collector",
    default=None,
)


@dataclass(frozen=True)
class ModelPricing:
    """Tariffe per token (USD per milione di token)."""

    input_usd_per_million_tokens: float
    output_usd_per_million_tokens: float

    def rate_in(self) -> float:
        return self.input_usd_per_million_tokens / 1_000_000

    def rate_out(self) -> float:
        return self.output_usd_per_million_tokens / 1_000_000


@dataclass(frozen=True)
class LlmCallRecord:
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    model: str
    call_kind: CallKind
    source: UsageSource = "api"


@dataclass
class TelemetryCollector:
    """Accumula usage e latenza per una singola run di triage."""

    pipeline: str
    model: str = MODEL
    calls: list[LlmCallRecord] = field(default_factory=list)

    @property
    def prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.calls)

    @property
    def completion_tokens(self) -> int:
        return sum(c.completion_tokens for c in self.calls)

    @property
    def latency_ms(self) -> int:
        return sum(c.latency_ms for c in self.calls)

    @property
    def llm_calls(self) -> int:
        return len(self.calls)

    def record_call(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        call_kind: CallKind,
        source: UsageSource = "api",
    ) -> LlmCallRecord:
        rec = LlmCallRecord(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            model=self.model,
            call_kind=call_kind,
            source=source,
        )
        self.calls.append(rec)
        return rec

    def cost_usd_milli(self, pricing: ModelPricing | None = None) -> int:
        p = pricing or load_model_pricing(self.model)
        cost = (self.prompt_tokens * p.rate_in()) + (self.completion_tokens * p.rate_out())
        return round(cost * 1000)

    def summary(self, pricing: ModelPricing | None = None) -> dict[str, Any]:
        return {
            "pipeline": self.pipeline,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "latency_ms": self.latency_ms,
            "llm_calls": self.llm_calls,
            "cost_usd_milli": self.cost_usd_milli(pricing),
            "calls": [
                {
                    "prompt_tokens": c.prompt_tokens,
                    "completion_tokens": c.completion_tokens,
                    "latency_ms": c.latency_ms,
                    "call_kind": c.call_kind,
                    "source": c.source,
                }
                for c in self.calls
            ],
        }

    def sqlite_fields(self, pricing: ModelPricing | None = None) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd_milli": self.cost_usd_milli(pricing),
            "latency_ms": self.latency_ms,
            "llm_calls": self.llm_calls,
            "pipeline": self.pipeline,
        }


def load_model_pricing(model: str = MODEL) -> ModelPricing:
    path = REPO_ROOT / "data" / "model_pricing.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if model in data:
            entry = data[model]
            return ModelPricing(
                input_usd_per_million_tokens=float(entry["input_usd_per_million_tokens"]),
                output_usd_per_million_tokens=float(entry["output_usd_per_million_tokens"]),
            )
    return ModelPricing(input_usd_per_million_tokens=0.40, output_usd_per_million_tokens=1.60)


def compute_cost_usd_milli(
    prompt_tokens: int,
    completion_tokens: int,
    *,
    pricing: ModelPricing | None = None,
    model: str = MODEL,
) -> int:
    """Costo totale in millesimi di dollaro (USD × 1000)."""
    p = pricing or load_model_pricing(model)
    cost = (prompt_tokens * p.rate_in()) + (completion_tokens * p.rate_out())
    return round(cost * 1000)


def enrich_azione_eseguita(base: str | None, collector: TelemetryCollector | None) -> str:
    """Appende blocco TELEMETRY leggibile a azione_eseguita."""
    text = (base or "Nessuna").strip()
    if collector is None or collector.llm_calls == 0:
        return text
    s = collector.summary()
    suffix = (
        f"TELEMETRY cost_milli={s['cost_usd_milli']} "
        f"tokens_in={s['prompt_tokens']} tokens_out={s['completion_tokens']} "
        f"latency_ms={s['latency_ms']} llm_calls={s['llm_calls']}"
    )
    if "| TELEMETRY" in text:
        return text
    return f"{text} | {suffix}"


def start_telemetry_collector(pipeline: str, *, model: str = MODEL) -> tuple[TelemetryCollector, Token]:
    collector = TelemetryCollector(pipeline=pipeline, model=model)
    token = current_telemetry_collector.set(collector)
    return collector, token


def reset_telemetry_collector(token: Token) -> None:
    current_telemetry_collector.reset(token)


def get_active_collector() -> TelemetryCollector | None:
    return current_telemetry_collector.get()


def extract_usage_from_response(
    response: Any,
    messages: list[Any],
    *,
    call_kind: CallKind,
) -> tuple[int, int, UsageSource]:
    """Legge response.usage o stima token dalla conversazione."""
    usage = getattr(response, "usage", None)
    if usage is not None:
        prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion = int(getattr(usage, "completion_tokens", 0) or 0)
        if prompt or completion:
            return prompt, completion, "api"
    from orchestration.message_pruning import estimate_conversation_tokens

    estimated = estimate_conversation_tokens(messages)
    if call_kind == "final_json":
        return max(0, estimated // 2), max(0, estimated - estimated // 2), "estimated"
    return estimated, 0, "estimated"


def parse_telemetry_from_azione(azione: str | None) -> dict[str, Any]:
    """Estrae campi SQLite dal blocco TELEMETRY in azione_eseguita."""
    text = azione or ""
    if "| TELEMETRY" not in text:
        return {}
    block = text.split("| TELEMETRY", 1)[1].strip()
    fields: dict[str, Any] = {}
    for key in (
        "cost_milli",
        "tokens_in",
        "tokens_out",
        "latency_ms",
        "llm_calls",
    ):
        match = re.search(rf"{key}=(\d+)", block)
        if match:
            fields[key] = int(match.group(1))
    if not fields:
        return {}
    return {
        "prompt_tokens": fields.get("tokens_in"),
        "completion_tokens": fields.get("tokens_out"),
        "cost_usd_milli": fields.get("cost_milli"),
        "latency_ms": fields.get("latency_ms"),
        "llm_calls": fields.get("llm_calls"),
    }


def apply_multi_agent_telemetry(
    result: Any,
    *,
    pipeline: str,
    tokens_est: int,
    latency_ms: int,
) -> Any:
    """
    Telemetria al boundary CrewAI/AutoGen: wall-clock reale + token stimati (SDK senza usage).
    """
    collector = TelemetryCollector(pipeline=pipeline)
    half = max(0, tokens_est // 2)
    record = collector.record_call(
        prompt_tokens=half,
        completion_tokens=max(0, tokens_est - half),
        latency_ms=latency_ms,
        call_kind="final_json",
        source="estimated",
    )
    log_event(
        "llm_call_telemetry",
        {
            "pipeline": pipeline,
            "call_kind": "final_json",
            "prompt_tokens": record.prompt_tokens,
            "completion_tokens": record.completion_tokens,
            "latency_ms": record.latency_ms,
            "source": "estimated",
            "model": collector.model,
            "note": "multi_agent_sdk_boundary",
        },
    )
    enriched = enrich_azione_eseguita(result.azione_eseguita, collector)
    summary = collector.summary()
    summary["source"] = "estimated_sdk_boundary"
    log_event("triage_telemetry_complete", summary)
    return result.model_copy(update={"azione_eseguita": enriched}), collector


def migrate_tickets_telemetry_columns(conn: Any) -> None:
    """Aggiunge colonne L20 a tickets se assenti (idempotente)."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(tickets)")
    existing = {row[1] for row in cursor.fetchall()}
    additions = {
        "prompt_tokens": "INTEGER",
        "completion_tokens": "INTEGER",
        "cost_usd_milli": "INTEGER",
        "latency_ms": "INTEGER",
        "llm_calls": "INTEGER",
        "pipeline": "TEXT",
    }
    for col, col_type in additions.items():
        if col not in existing:
            cursor.execute(f"ALTER TABLE tickets ADD COLUMN {col} {col_type}")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_tickets_categoria_cost "
        "ON tickets(categoria, cost_usd_milli)"
    )


def tickets_has_telemetry_columns(db_path: str | Path) -> bool:
    path = Path(db_path)
    if not path.exists():
        return False
    import sqlite3

    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(tickets)")
        existing = {row[1] for row in cursor.fetchall()}
    return all(col in existing for col in _L20_TELEMETRY_COLUMNS)
