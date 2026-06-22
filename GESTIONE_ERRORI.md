# Gestione errori — Progetto 2 SOC

Manuale su errori, fallback e resilienza nel sistema di triage su **10 scenari `dataset_test`**.

Documentazione correlata: [README.md](README.md) · [MANUALE_PROGETTINO_DATASET_TEST.md](docs/MANUALE_PROGETTINO_DATASET_TEST.md)

---

## Stato attuale

Il codice gestisce errori a **livello 1–3**:

| Livello | Meccanismo | Dove |
|---------|------------|------|
| Fail-fast | `ValueError` su input/API | `client.py`, `parser.py`, `logic.py` |
| Soft error | Self-correction in-loop ReAct | `react_triage` — JSON invalido reiniettato nel ciclo |
| Hard stop | Emergency / max_steps fallback | `_emergency_triage_result`, `react_max_steps_fallback` |
| Injection | `ClarificationNeeded` → SECURITY | `react_triage_progettino` (scenario 3) |

**Motore unico:** `react_triage_progettino` → `react_triage(progetto_mode=True)` con `_apply_progetto_fallbacks`.

Manca ancora una gerarchia opzionale di eccezioni di dominio (`errors.py`).

---

## Flusso errori nel ciclo ReAct

```mermaid
flowchart TD
    Start[react_triage_progettino] --> Loop{step <= max_steps?}
    Loop -->|no| MaxFB[react_max_steps_fallback]
    Loop -->|sì| LLM[LLM + tool]
    LLM --> Tools{tool_calls?}
    Tools -->|sì| FB[_apply_progetto_fallbacks]
    FB --> Loop
    Tools -->|no| JSON{JSON valido?}
    JSON -->|sì| Done[TriageResult]
    JSON -->|no, inizia con `{`| SC[self-correction → step++]
    SC --> Loop
    JSON -->|testo piano| Clarify[ClarificationNeeded]
    Clarify --> Inj[react_triage_progettino → SECURITY]
```

### Tipi di errore

| Tipo | Esempio | Comportamento |
|------|---------|---------------|
| **Hard** | API key mancante, file policy assente | `ValueError` / `FileNotFoundError` in CLI |
| **Soft** | JSON malformato con `{` iniziale | Self-correction in-loop (consuma uno step) |
| **Injection** | «DO NOT GENERATE JSON» (scenario 3) | `ClarificationNeeded` → `TriageResult` SECURITY |
| **Max steps** | Loop tool senza convergenza | `TriageResult` fallback + evento `react_max_steps_fallback` |

### Eventi audit (`logs/activity.jsonl`)

| `event_type` | Quando |
|--------------|--------|
| `progetto_clarification_injection` | Scenario 3 — testo non-JSON intercettato |
| `progetto_security_fallback` | Fallback `isolate_account` / `verify_sender_identity` |
| `react_max_steps_fallback` | Esauriti 6 step ReAct |

---

## Fallback deterministici

`_apply_progetto_fallbacks` combina:

1. **`_apply_all_fallbacks`** — VIP budget > 10k€, sentiment ARRABBIATO, storico cliente critico
2. **`_apply_security_fallback`** — isolamento account, verifica CEO, ransomware

Iniettati come tool calls sintetici se l'LLM li omette.

---

## File chiave

| File | Ruolo |
|------|--------|
| `src/logic.py` | `react_triage`, `react_triage_progettino`, fallback, `ClarificationNeeded` |
| `src/parsing/parser.py` | `parse_llm_output` — validazione Pydantic |
| `src/main.py` | CLI demo scenari |
| `src/client.py` | Connessione OpenAI |
| `tests/test_logic.py` | ReAct, max_steps, self-correction |
| `tests/test_dataset_test.py` | Scenari SOC e injection |

---

## Test

```bash
pytest tests/ -q
```

Percorso scenari SOC:

```bash
pytest tests/test_dataset_test.py tests/test_security_progetto.py -q
```

---

## Collegamenti

- [README.md](README.md) — architettura e setup
- [docs/PROGETTO_2_SCENARI.md](docs/PROGETTO_2_SCENARI.md) — svolgimento scenari 1–10
- [`scripts/init_triage_db.py`](scripts/init_triage_db.py) — bootstrap SQLite
- [`data/schema/triage_system.sql`](data/schema/triage_system.sql) — DDL LTM
