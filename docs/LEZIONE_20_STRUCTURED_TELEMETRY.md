# Lezione 20 — Monitoraggio, tracciabilità e telemetria custom

**Branch:** `lesson-20-structured-telemetry` (da `lesson-19-hitl-breakpoints`)

Telemetria **didattica** ma **strutturata**: usage API reale (`response.usage`), costo in **millesimi di dollaro**, latenza per chiamata LLM, persistenza SQLite e blocco leggibile in `azione_eseguita`.

**Demo live:** `l20a` e `l20b` **senza LLM** (mock controllato) — spiegazione in [SETTIMANA_15_DEMO_LIVE.md](SETTIMANA_15_DEMO_LIVE.md). Panoramica tutti gli scenari: [SETTIMANA_12_DEMO_LIVE.md](SETTIMANA_12_DEMO_LIVE.md#panoramica-rapida--tutti-gli-scenari).

---

## 20.1 Perché telemetria enterprise

| Livello | Cosa misuriamo | Nel repo |
|---------|----------------|----------|
| Proxy L17 | `tokens_est` (tiktoken / len÷4) | `message_pruning.estimate_conversation_tokens` |
| Benchmark L12 | `pipeline_latency_report` | `benchmark_multi_agent.py` |
| **L20** | `prompt_tokens`, `completion_tokens`, `cost_usd_milli`, `latency_ms`, `llm_calls` | `orchestration/telemetry.py` |

Il chokepoint unico è in `logic.py`: `_call_llm_with_tools` e `_request_final_json`.

---

## Formula costo

Tariffe in [`data/model_pricing.json`](../data/model_pricing.json) (default `gpt-4.1-mini`):

```
cost_usd = prompt_tokens × rate_in + completion_tokens × rate_out
cost_usd_milli = round(cost_usd × 1000)
```

`rate_in` / `rate_out` = USD per **token** (tariffa per milione ÷ 1_000_000).

---

## Modulo `orchestration/telemetry.py`

| Componente | Ruolo |
|------------|-------|
| `ModelPricing` | Tariffe input/output |
| `TelemetryCollector` | Accumula chiamate per run |
| `LlmCallRecord` | Singola completion (`tool_turn` \| `final_json`) |
| `enrich_azione_eseguita` | Append `| TELEMETRY cost_milli=…` |
| `ContextVar` `current_telemetry_collector` | Hook senza cambiare firme pubbliche |

**Fallback:** se `response.usage` assente → stima L17 per quella chiamata (`source: estimated` nel JSONL).

**Multi-agent (CrewAI/AutoGen):** al boundary pipeline — wall-clock reale + `tokens_est` come proxy (`source: estimated_sdk_boundary`); gli SDK non espongono usage uniforme.

---

## Eventi JSONL

| event_type | Quando |
|------------|--------|
| `llm_call_telemetry` | Ogni completion instrumentata |
| `triage_telemetry_complete` | Fine run (successo o fallback con almeno 1 call) |

KPI: `analytics/log_kpi.telemetry_metrics`.

---

## SQLite `tickets` (colonne L20)

| Colonna | Tipo | Note |
|---------|------|------|
| `prompt_tokens` | INTEGER | Somma input API |
| `completion_tokens` | INTEGER | Somma output API |
| `cost_usd_milli` | INTEGER | USD × 1000 |
| `latency_ms` | INTEGER | Wall-clock LLM nel run |
| `llm_calls` | INTEGER | N. completion |
| `pipeline` | TEXT | `triage_message` \| `react_triage` \| `crewai` \| `autogen` |

Migrazione idempotente: `init_db()` → `migrate_tickets_telemetry_columns`.

**Query didattica (costo medio per categoria):**

```sql
SELECT categoria,
       ROUND(AVG(cost_usd_milli) / 1000.0, 4) AS avg_cost_usd,
       AVG(latency_ms) AS avg_latency_ms,
       COUNT(*) AS n
FROM tickets
WHERE cost_usd_milli IS NOT NULL
GROUP BY categoria;
```

CLI: `PYTHONPATH=src python3 -m analytics.telemetry_report`

---

## Metriche run (`return_metrics=True`)

Estensioni L20 (retrocompatibili con `tokens_est` L17):

- `TriageRunMetrics` / `ReactRunMetrics` / `MultiAgentRunMetrics`: `prompt_tokens`, `completion_tokens`, `cost_usd_milli`, `latency_ms`, `llm_calls`

---

## Come usare la telemetria — guida pratica

### Quando si attiva

- Ogni `triage_message`, `react_triage`, `react_triage_resume` apre un `TelemetryCollector` per pipeline.
- Le pause HITL L19 **non** generano completion → non contano in `llm_calls`.
- CrewAI/AutoGen: una entry stimata al boundary con latenza wall-clock totale.

### Leggere `azione_eseguita`

Esempio:

```
notify_manager | TELEMETRY cost_milli=45 tokens_in=1200 tokens_out=340 latency_ms=890 llm_calls=2
```

Il blocco è pensato per log umani e audit; le colonne SQLite restano la fonte per query aggregate.

### Confronto stima L17 vs usage API

- **L17:** stima conversazione intera (`tokens_est`) — utile per pruning/benchmark.
- **L20:** somma `response.usage` per chiamata — utile per **billing** e SLO produzione.
- Demo `l20a`: due chiamate mock con usage fittizio e confronto numerico.

### Eseguire query aggregate

1. Run instrumentato (`l20b` o `react_triage` reale).
2. `_persist_react_result` scrive colonne L20.
3. `python3 -m analytics.telemetry_report` o query SQL sopra.

---

## Demo CLI

| Scenario | LLM | Contenuto |
|----------|-----|-----------|
| `l20a` | No | Formula, 2 mock `usage`, eventi JSONL |
| `l20b` | No (mock) | ReAct → SQLite → query per `categoria` |

```bash
PYTHONPATH=src python3 src/main.py --scenario l20a
PYTHONPATH=src python3 src/main.py --scenario l20b
PYTHONPATH=src python3 src/main.py --scenario all
```

Manuale operativo: [SETTIMANA_15_DEMO_LIVE.md](SETTIMANA_15_DEMO_LIVE.md)

---

## Checklist docente

- [ ] Branch `lesson-20-structured-telemetry` attivo
- [ ] `scripts/init_triage_db.py` → colonne telemetry OK
- [ ] Demo `l20a`: eventi `llm_call_telemetry` + `triage_telemetry_complete`
- [ ] Demo `l20b`: ticket con `cost_usd_milli` valorizzato; query IT vs SALES
- [ ] `pytest tests/ -q` verde (~184 test)

## Prerequisito

[LEZIONE_19_HITL_BREAKPOINTS.md](LEZIONE_19_HITL_BREAKPOINTS.md) — HITL non interrompe la telemetria LLM, solo le completion.

## Collegamenti

- [LEZIONE_17_MULTI_AGENT_PERFORMANCE.md](LEZIONE_17_MULTI_AGENT_PERFORMANCE.md) — `tokens_est` e latenza benchmark
- [LEZIONE_12_PROMPT_OPTIMIZATION.md](LEZIONE_12_PROMPT_OPTIMIZATION.md) — tabella KPI JSONL
- [GESTIONE_ERRORI.md](../GESTIONE_ERRORI.md) — eventi audit L20
- [CORSO_LEZIONI.md](CORSO_LEZIONI.md) — mappa branch

## Fine percorso lezioni 9–20

Con la Lezione 20 il corso **Agentic Customer Care Triage System** copre l'intero arco didattico:

| Settimana | Lezioni | Competenza chiave |
|-----------|---------|-------------------|
| 8 | 11–12 | Resilienza, benchmark, KPI |
| 9 | 13–14 | ReAct, SQLite LTM, planning loop |
| 12 | 15–17 | Multi-agente, CrewAI/AutoGen, performance |
| 13 | 18 | Sicurezza MAS (guardrail, tool gate) |
| 14 | 19 | HITL, breakpoint, resume operatore |
| 15 | 20 | Telemetria strutturata, costo USD, tracciabilità LLM |

**Branch di riferimento completo:** `lesson-20-structured-telemetry` — `184 test`, demo `l15` … `l20b`, CLI `telemetry_report` e `log_kpi`.
