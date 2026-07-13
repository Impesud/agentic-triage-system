# Lezione 11 — Resilienza dell'agente e Self-Correction

**Settimana 8 (parte 1)** — complementa [README — Lezione 11](../README.md#resilienza-e-self-correction-lezione-11) e [CORSO_LEZIONI.md](CORSO_LEZIONI.md).

**Branch:** `lesson-11-resilienza-self-correction` (include anche lezioni 9–10).

## Obiettivi

1. Distinguere **hard error** (infrastruttura) e **soft error** (output LLM non valido).
2. Implementare **Self-Correction Loop** con feedback Pydantic in-context (`max_retries = 3`).
3. Garantire **Emergency Fallback** deterministico senza crash né `None` in pipeline.

## 11.1 Tipi di fallimento

| Tipo | Esempi | Gestione nel progetto |
|---
**Branch storico demo:** `lesson-11-resilienza-self-correction`. Su `lesson-20-structured-telemetry` (e branch successivi a L11), `main.py` non espone più la demo CLI di questa lezione — fare checkout su `lesson-11-resilienza-self-correction`.
---|--------|------------------------|
| **Hard error** | API timeout, API key assente, `manuale_it.txt` mancante, disco pieno | Propagazione → boundary `main.py` → `[ERRORE]`, `return None` |
| **Soft error** | JSON malformato, campi mancanti, `riassunto_breve` > 15 parole | `_finalize_with_self_correction` in [`logic.py`](../src/logic.py) |

`ClarificationNeeded` (M1, messaggio vago) **non** è soft error: non entra nel loop di riparazione JSON.

## 11.2 Self-Correction Loop

Flusso dopo `_run_agent_loop` (tool + fallback policy/LTM):

1. Ottenere `raw` JSON (`_request_final_json` o risposta diretta).
2. `parse_llm_output(raw)` → `TriageResult`.
3. Se `ValueError`: append `assistant` + `user` con messaggio errore → richiesta nuovo JSON.
4. Ripetere fino a 3 tentativi (`MAX_TRIAGE_JSON_RETRIES`).

Log: `event_type: triage_json_retry` in `logs/activity.jsonl`.

## 11.3 Emergency Fallback

Al terzo fallimento:

- `categoria: GENERAL`, `priorita: CRITICAL`
- `azione_eseguita: "Emergency Fallback attivato"`
- `riassunto_breve` con prefisso `FALLBACK:`
- Routing → team `GeneralQueue` ([`router.py`](../src/tools/router.py))
- Log: `event_type: emergency_fallback`

## API e metriche

```python
from logic import triage_message, TriageStats

result = triage_message(testo, manuale)  # solo TriageResult

result, stats = triage_message(testo, manuale, return_stats=True)
# stats.attempts, stats.used_self_correction, stats.used_emergency_fallback
```

## Demo e test

```bash
git checkout lesson-11-resilienza-self-correction
PYTHONPATH=src python3 src/main.py --scenario l11
pytest tests/test_logic.py -q -k "self_correction or emergency"
```

## Collegamenti

- [Lezione 17 — Performance MAS](LEZIONE_17_MULTI_AGENT_PERFORMANCE.md) — pruning, cache, KPI latenza
- [GESTIONE_ERRORI.md](../GESTIONE_ERRORI.md) — moduli 2–4 vs L11
- [Lezione 12 — Benchmark](LEZIONE_12_PROMPT_OPTIMIZATION.md) — misura impatto retry/fallback
- [Lezione 13 — ReAct + SQLite](LEZIONE_13_REACT_SQLITE.md) — secondo percorso agentico (`react_triage`)
- [Lezione 14 — Planning loop](LEZIONE_14_PLANNING_LOOPS.md) — self-correction **in-loop** ReAct (distinto da L11)
- [Lezione 15 — Multi-agent](LEZIONE_15_MULTI_AGENT_COORDINATION.md) — separazione ruoli e topologie
- [Lezione 16 — CrewAI/AutoGen](LEZIONE_16_CREW_AUTOGEN.md) — orchestrazione multi-agent con framework
- [README — branch e corso](CORSO_LEZIONI.md)
