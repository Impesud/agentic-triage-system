# Lezione 17 — Ottimizzazione delle Performance nei Sistemi Multi-Agente

**Settimana 12 (parte 3)** — complementa [LEZIONE_16_CREW_AUTOGEN.md](LEZIONE_16_CREW_AUTOGEN.md) e [CORSO_LEZIONI.md](CORSO_LEZIONI.md).

**Demo live:** [SETTIMANA_12_DEMO_LIVE.md](SETTIMANA_12_DEMO_LIVE.md) — sezioni `l17a`, `l17b` e sequenza `all`.

**Branch:** `lesson-17-multi-agent-performance` (include lezioni 9–17).

**Durata:** 2 ore — Context Window, Message Pruning, contenimento latenza.

## Obiettivi didattici

1. Spiegare l'**esplosione dei token** in catene Analyst → Resolver con tool ReAct.
2. Implementare **Message Pruning** sulla cronologia e compattazione output tool.
3. Applicare **PipelineContextCache** per evitare embedding/query RAG ridondanti.
4. Misurare impatto con benchmark e KPI JSONL (estensione L12).

## 17.1 L'esplosione dei Token

Nello scenario multi-agente (L16), l'output dell'Analyst entra nel contesto del Resolver. Ogni tool (`search_policy`, `search_long_term_history`) aggiunge observation verbose → saturazione Context Window, costi elevati, **Lost in the Middle**.

| Fonte | Effetto |
|-------|---------|
| Manuale duplicato in entrambi gli agenti | 2× token fissi |
| Hand-off + `context=[analyst_task]` (CrewAI) | Ridondanza anagrafica |
| Chunk RAG interi nelle observation | Centinaia di token per call |
| `embed_texts([query])` a ogni `search_policy` | Latenza API ripetuta |

## 17.2 Message Pruning

Modulo [`message_pruning.py`](../src/orchestration/message_pruning.py):

| Funzione | Ruolo |
|----------|--------|
| `estimate_tokens` / `estimate_conversation_tokens` | Stima grezza `len//4` |
| `prune_conversation` | Compatta observation tool obsolete |
| `compact_tool_output` | Tronca output tool all'origine (adapter L16) |
| `apply_pruning_with_log` | Pruning + evento `message_pruning_applied` |

Orchestrazione **due fasi** (L17 migliorata): Analyst esegue per primo e popola la cache; poi il Resolver riceve `policy_excerpt` / `ltm_digest` nel Blackboard (evento `handoff_enriched_from_cache`).

Integrazione:

- **`react_triage`**: pruning prima di ogni step se `enable_optimizations=True`
- **`tool_adapters`**: `compact_output` per CrewAI/AutoGen

## 17.3 Contenimento latenza — Cache pipeline

[`pipeline_cache.py`](../src/orchestration/pipeline_cache.py) — scope **per singola invocazione** di triage:

- `get_or_call_policy(query, fn)` — dedup query normalizzata
- `get_or_call_ltm(cliente, hours, fn)` — dedup storico SQLite

[`handoff_enrichment.py`](../src/orchestration/handoff_enrichment.py) propaga `policy_excerpt` e `ltm_digest` su `SharedHandoffContext` così il Resolver evita tool ridondanti.

Parametro unificato: `enable_optimizations=True` su `react_triage` e `multi_agent_triage`.

## Installazione

```bash
git checkout lesson-17-multi-agent-performance
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[test,multiagent]"
PYTHONPATH=src python3 scripts/init_triage_db.py
```

## Demo live (solo Settimana 12)

Vedi anche [SETTIMANA_12_DEMO_LIVE.md](SETTIMANA_12_DEMO_LIVE.md) per prerequisiti, output atteso e troubleshooting.

```bash
PYTHONPATH=src python3 src/main.py                    # default: solo l15
PYTHONPATH=src python3 src/main.py --scenario l15    # topologie (no LLM)
PYTHONPATH=src python3 src/main.py --scenario l16a   # CrewAI
PYTHONPATH=src python3 src/main.py --scenario l16b   # AutoGen
PYTHONPATH=src python3 src/main.py --scenario l17a   # pruning before/after
PYTHONPATH=src python3 src/main.py --scenario l17b   # benchmark latenza
PYTHONPATH=src python3 src/main.py --scenario all    # sequenza L15→L17
```

Benchmark standalone:

```bash
PYTHONPATH=src python3 src/benchmark_multi_agent.py
PYTHONPATH=src python3 -m analytics.log_kpi
```

## Test automatici (L17)

```bash
pytest tests/test_message_pruning.py tests/test_pipeline_cache.py tests/test_benchmark_multi_agent.py -q
pytest tests/test_week12_report.py tests/test_main_report.py tests/test_open_html.py -q
pytest tests/ -q   # ~129 test
```

## Ottimizzazioni aggiuntive (review L17)

### Manuale compatto per il Resolver

Quando il Blackboard è arricchito post-Analyst (`policy_excerpt`, `ltm_digest`), [`prompt_compression.py`](../src/orchestration/prompt_compression.py) sostituisce il manuale IT completo con un puntatore nel prompt del SecurityResolver — riduzione token strutturale senza perdere i dati già in cache.

### Guardrail API key

[`api_guard.py`](../src/orchestration/api_guard.py) impedisce esecuzioni costose senza `OPENAI_API_KEY`:

- scenari singoli `l16a`/`l16b`/`l17a`/`l17b` → messaggio `[SKIP]` ed exit 0
- `--scenario all` → esegue sempre `l15`, salta i blocchi LLM con `skip_llm_block`

### Stima token con `tiktoken` opzionale

`estimate_tokens` in [`message_pruning.py`](../src/orchestration/message_pruning.py) usa `tiktoken` se installato, altrimenti fallback `len(text)//4`. Le metriche `return_metrics` su `triage_message`, `react_triage` e `multi_agent_triage` alimentano [`benchmark_multi_agent.py`](../src/benchmark_multi_agent.py).

## File chiave

| File | Ruolo L17 |
|------|-----------|
| [`orchestration/message_pruning.py`](../src/orchestration/message_pruning.py) | Pruning history |
| [`orchestration/pipeline_cache.py`](../src/orchestration/pipeline_cache.py) | Cache per pipeline |
| [`orchestration/handoff_enrichment.py`](../src/orchestration/handoff_enrichment.py) | Blackboard arricchito |
| [`orchestration/prompt_compression.py`](../src/orchestration/prompt_compression.py) | Manuale compatto Resolver |
| [`orchestration/api_guard.py`](../src/orchestration/api_guard.py) | Guardrail API key CLI |
| [`orchestration/tool_adapters.py`](../src/orchestration/tool_adapters.py) | Cache + compact output |
| [`benchmark_multi_agent.py`](../src/benchmark_multi_agent.py) | Confronto latenza |
| [`main.py`](../src/main.py) | Solo scenari L15–L17 |

## Checklist docente

- [ ] Branch `lesson-17-multi-agent-performance` attivo
- [ ] `main.py --help` mostra solo L15–L17
- [ ] Demo `l17a`: Δ token visibile in console
- [ ] Eventi `message_pruning_applied` / `embedding_cache_hit` in `activity.jsonl`
- [ ] `pytest tests/ -q` verde

## Prerequisito

[LEZIONE_16_CREW_AUTOGEN.md](LEZIONE_16_CREW_AUTOGEN.md) — orchestrazione CrewAI/AutoGen.

## Collegamenti

- [LEZIONE_15_MULTI_AGENT_COORDINATION.md](LEZIONE_15_MULTI_AGENT_COORDINATION.md) — Blackboard
- [LEZIONE_14_PLANNING_LOOPS.md](LEZIONE_14_PLANNING_LOOPS.md) — ReAct / STM
- [LEZIONE_17_MULTI_AGENT_PERFORMANCE.md](LEZIONE_17_MULTI_AGENT_PERFORMANCE.md) — KPI log

## Prossimo passo (Lezione 18)

[LEZIONE_18_MULTI_AGENT_SECURITY.md](LEZIONE_18_MULTI_AGENT_SECURITY.md) — branch `lesson-18-multi-agent-security`.

## Documentazione correlata

- [CORSO_LEZIONI.md](CORSO_LEZIONI.md) — mappa branch e comandi
- [README.md](../README.md) — architettura cumulativa
- [GESTIONE_ERRORI.md](../GESTIONE_ERRORI.md) — eventi audit L17

## Nota branch L18

Su `lesson-18-multi-agent-security`, `main.py` include anche `l18a`/`l18b`. Vedi [SETTIMANA_13_DEMO_LIVE.md](SETTIMANA_13_DEMO_LIVE.md) e [LEZIONE_18_MULTI_AGENT_SECURITY.md](LEZIONE_18_MULTI_AGENT_SECURITY.md).
