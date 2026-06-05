# Lezione 13 — Architettura ReAct e Upgrade Infrastrutturale (SQLite)

**Settimana 9 (parte 1)** — complementa [README — Lezione 13](../README.md#react-e-sqlite-lezione-13) e [CORSO_LEZIONI.md](CORSO_LEZIONI.md).

**Branch:** `lesson-13-react-sqlite` (include lezioni 9–12).

## Obiettivi

1. Migrare la Long-Term Memory da scansione JSONL O(N) a SQLite indicizzato O(log N).
2. Introdurre il loop **ReAct** (Thought → Action → Observation) multi-step.
3. Mantenere dual-write JSONL + SQLite per analytics L12 e audit operativo.

## 13.1 Perché SQLite?

Fino alla Settimana 8, `logs/activity.jsonl` resta lo strumento di audit per KPI e benchmark. Per la memoria a lungo termine del cliente, però, la scansione riga-per-riga non scala.

| Aspetto | JSONL (audit) | SQLite (LTM) |
|---------|---------------|--------------|
| Uso | KPI, eventi, benchmark L12 | Storico ticket per cliente |
| Ricerca cliente | O(N) scan | O(log N) con indice `idx_cliente` |
| Modulo | `log_event()` | `log_triage_to_sqlite()` |

Database: `data/triage_system.db` — tabella `tickets` con indice su `cliente_nome`.

## 13.2 Framework ReAct

Il tool calling single-step decide tutti gli strumenti in un turno. ReAct decompone dinamicamente:

1. **Thought** — l'LLM valuta cosa manca nel contesto.
2. **Action** — invoca un tool (es. `search_long_term_history` su SQLite).
3. **Observation** — il runtime esegue e restituisce il risultato grezzo.

Il ciclo ripete fino a convergenza JSON o esaurimento `max_steps` (default 8 in L13; 4 in L14).

API: `react_triage()` in [`logic.py`](../src/logic.py). La pipeline classica `triage_message()` resta per benchmark e demo M1–M3.

## Comandi

```bash
# Inizializza DB e demo ReAct + SQLite
PYTHONPATH=src python3 src/main.py --scenario l13

# Test
pytest tests/test_logger_sqlite.py tests/test_logic.py -q
```

## File modificati

| File | Ruolo |
|------|--------|
| [`paths.py`](../src/paths.py) | `TRIAGE_DB_PATH`, `DEMO_M2_DB_PATH` |
| [`tools/logger.py`](../src/tools/logger.py) | `init_db`, `log_triage_to_sqlite`, `search_long_term_history_sql` |
| [`tools/history_tools.py`](../src/tools/history_tools.py) | Delega a SQLite |
| [`tools/registry.py`](../src/tools/registry.py) | Tool map aggiornata |
| [`logic.py`](../src/logic.py) | `react_triage()` |
| [`main.py`](../src/main.py) | Dual-write, `seed_marco_sqlite`, demo `l13` |

## Prossimo passo

Lezione 14 — vedi [LEZIONE_14_PLANNING_LOOPS.md](LEZIONE_14_PLANNING_LOOPS.md).
