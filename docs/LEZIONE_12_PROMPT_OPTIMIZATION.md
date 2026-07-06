# Lezione 12 — Ottimizzazione prompt da log e benchmark

**Settimana 8 (parte 2)** — complementa [README — Lezione 12](../README.md#benchmark-e-log-analytics-lezione-12) e [CORSO_LEZIONI.md](CORSO_LEZIONI.md).

**Branch:** `lesson-12-benchmark-log-analytics`.

## Obiettivo

Imparare a migliorare l’agente **senza toccare Python** quando il problema è comportamentale (tool sbagliati, JSON instabile), usando:

1. Analisi di `logs/activity.jsonl`
2. Benchmark (`src/benchmark.py`)
3. Nuova versione prompt `triage_v2.py`

## 1. Analisi log (JSONL Analytics)

```bash
PYTHONPATH=src python3 -m analytics.log_kpi
```

KPI disponibili:

| KPI | Fonte |
|-----|--------|
| Conteggio `event_type` | `ticket_received`, `ticket_processed`, `error`, … |
| Self-correction | `triage_json_retry`, `emergency_fallback` |
| ReAct (L14) | `react_max_steps_fallback` |
| Multi-agent (L15) | Nessun nuovo evento JSONL (demo concettuale `l15`) |
| Orchestrazione (L16) | `crew_triage_complete`, `autogen_triage_complete`, `multi_agent_fallback` |
| Performance (L17) | `message_pruning_applied`, `embedding_cache_hit`, `pipeline_latency_report` |
| Sicurezza (L18) | `security_input_blocked`, `security_handoff_blocked`, `security_tool_denied` |
| Tool usage (proxy) | stringhe `search_policy`, `notify_manager`, … nei payload |

Se `triage_json_retry` è alto → problema **sintassi JSON** (prompt o self-correction).

Se `emergency_fallback` è alto → prompt o schema troppo rigido; pochi shot su casi limite.

## 2. Benchmark

```bash
PYTHONPATH=src python3 src/benchmark.py
```

Confronta due run (prima/dopo ottimizzazione prompt):

- `Successi immediati o riparati` — triage valido senza emergency fallback
- `Chiarimenti richiesti (non-JSON, M1)` — `ClarificationNeeded`: risposta testuale, non JSON (nessun retry)
- `Interventi di Fallback di emergenza` — `azione_eseguita` con Fallback

**Costo API:** 5 chiamate complete all’LLM. In laboratorio usare `pytest tests/test_benchmark.py -q`.

### FAQ — Retry JSON vs ClarificationNeeded

| Categoria | Esempio | Retry x3? |
|-----------|---------|-----------|
| **Soft error (L11)** | `{"categoria":"IT"}` senza campi obbligatori | **Sì** — `_finalize_with_self_correction` |
| **ClarificationNeeded (L9/M1)** | Testo libero, messaggio vago, rifiuto off-topic | **No** — in `main.py` ticket resta `OPEN` |
| **Hard error** | API timeout, API key assente | **No** — boundary in `main.py` |

I 3 retry **non** coprono ogni forma di «JSON non valido»: partono solo se la risposta **inizia con `{`** ma fallisce `parse_llm_output`. Se il modello risponde in prosa (es. prompt injection *«non rispondere in JSON»*), `logic.py` solleva `ClarificationNeeded` **prima** del loop di self-correction.

Per osservare i retry in laboratorio senza costo API:

```bash
pytest tests/test_logic.py -q -k "self_correction or emergency"
```

Per provare `ClarificationNeeded` nel benchmark, sostituire temporaneamente un ticket in `BENCHMARK_DATASET` con testo libero o prompt injection (vedi commenti in `src/benchmark.py`).

## 3. Workflow prompt v1 → v2

1. Eseguire benchmark e salvare output terminale.
2. Analizzare log con `analytics.log_kpi`.
3. Formulare ipotesi (es. «non chiama notify_manager su ARRABBIATO»).
4. Copiare [`src/prompts/triage_v1.py`](../src/prompts/triage_v1.py) → adattare [`triage_v2.py`](../src/prompts/triage_v2.py):
   - unire `FEW_SHOTS` + `FEW_SHOTS_V2_EXTENSION`
   - rafforzare regole su ARRABBIATO nel `SYSTEM_PROMPT`
5. In `logic.py`, importare `build_chat_messages` da `triage_v2`.
6. Ripetere benchmark e confrontare KPI.

**Non modificare** `logic.py` per fix comportamentali puri — solo il prompt.

## 4. Esempio didattico: ARRABBIATO + notify_manager

Vedi few-shot in [`src/prompts/triage_v2.py`](../src/prompts/triage_v2.py) (`EXTRA_FEW_SHOT_ARRABBIATO`).

Dopo l’aggiunta, il benchmark con ticket budget 12k€ / tono aggressivo dovrebbe mostrare più invocazioni coerenti di `notify_manager` nei log (proxy tool usage).

## Checklist docente

- [ ] Studente interpreta report benchmark (quali case stressano il parser?)
- [ ] Studente legge `triage_json_retry` / `emergency_fallback` nel log
- [ ] Migrazione v2 documentata (diff prompt, non refactor massivo)
- [ ] `max_retries` invariato (3) — nessun loop infinito introdotto dal prompt

## Collegamenti

- [Lezione 11 — Self-Correction](../README.md#resilienza-e-self-correction-lezione-11)
- [Lezione 13 — ReAct + SQLite](LEZIONE_13_REACT_SQLITE.md) — dual-write JSONL + SQLite (KPI restano su JSONL)
- [Lezione 15 — Multi-agent](LEZIONE_15_MULTI_AGENT_COORDINATION.md) — topologie e Blackboard
- [Lezione 16 — CrewAI/AutoGen](LEZIONE_16_CREW_AUTOGEN.md) — eventi `crew_triage_complete`, `autogen_triage_complete`
- [Lezione 17 — Performance MAS](LEZIONE_17_MULTI_AGENT_PERFORMANCE.md) — pruning, cache, benchmark multi-agent
- [Lezione 18 — Sicurezza MAS](LEZIONE_18_MULTI_AGENT_SECURITY.md) — guardrail, hand-off, tool gate
- [GESTIONE_ERRORI.md](../GESTIONE_ERRORI.md)
- [LEZIONE_10B_CHROMADB.md](LEZIONE_10B_CHROMADB.md)
