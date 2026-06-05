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
| Tool usage (proxy) | stringhe `search_policy`, `notify_manager`, … nei payload |

Se `triage_json_retry` è alto → problema **sintassi JSON** (prompt o self-correction).

Se `emergency_fallback` è alto → prompt o schema troppo rigido; pochi shot su casi limite.

## 2. Benchmark

```bash
PYTHONPATH=src python3 src/benchmark.py
```

Confronta due run (prima/dopo ottimizzazione prompt):

- `Successi immediati o riparati` — triage valido senza emergency fallback
- `Interventi di Fallback di emergenza` — `azione_eseguita` con Fallback

**Costo API:** 5 chiamate complete all’LLM. In laboratorio usare `pytest tests/test_benchmark.py -q`.

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
- [GESTIONE_ERRORI.md](../GESTIONE_ERRORI.md)
- [LEZIONE_10B_CHROMADB.md](LEZIONE_10B_CHROMADB.md)
