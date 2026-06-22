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
| Injection | `ClarificationNeeded` + `_is_prompt_injection_attempt` | `react_triage_progettino` (solo scenario 3) |
| Clarification retry | Testo piano su ticket legittimo | Correzione in-loop in `react_triage` (progetto_mode) |
| Arricchimento output | `azione_eseguita` vuoto dopo JSON valido | `_enrich_progetto_result` |
| Policy fallback | `search_policy` omesso su incidente SECURITY | `_requires_policy_search` + `_policy_query_for_context` |
| Injection post-parse | JSON IT/LOW su messaggio scenario 3 | `_normalize_injection_result` |
| Payload strutturato | JSON LLM non valido su scenari 7/10 | `_progetto_payload_structured_result` |

**Motore unico:** `react_triage_progettino` → `react_triage(progetto_mode=True)` con `_apply_progetto_fallbacks`.

Manca ancora una gerarchia opzionale di eccezioni di dominio (`errors.py`).

---

## Flusso errori nel ciclo ReAct

```mermaid
flowchart TD
    Start[react_triage_progettino] --> Loop{step <= max_steps?}
    Loop -->|no| MaxFB{payload 7/10?}
    MaxFB -->|sì| PayloadFB[_progetto_payload_structured_result]
    MaxFB -->|no, progetto_mode| ProjFB[_progetto_max_steps_fallback]
    MaxFB -->|no| GenFB[react_max_steps_fallback GENERAL]
    Loop -->|sì| LLM[LLM + tool]
    LLM --> Tools{tool_calls?}
    Tools -->|sì| FB[_apply_progetto_fallbacks]
    FB --> Loop
    Tools -->|no| JSON{JSON valido?}
    JSON -->|sì| NormInj{_normalize_injection_result}
    NormInj --> Enrich[_enrich_progetto_result]
    Enrich --> Done[TriageResult]
    JSON -->|no, inizia con `{`| SC[self-correction → step++]
    SC --> Loop
    SC -->|payload, step>=3| PayloadEarly[_progetto_payload_structured_result]
    JSON -->|testo piano| InjGate{injection attempt?}
    InjGate -->|sì, progetto_mode| Clarify[ClarificationNeeded]
    Clarify --> InjTpl[_progetto_injection_result]
    InjGate -->|no, progetto_mode| RetryMsg[messaggio correzione JSON → step++]
    RetryMsg --> Loop
    InjGate -->|no, legacy| ClarifyLegacy[ClarificationNeeded]
```

### Tipi di errore

| Tipo | Esempio | Comportamento |
|------|---------|---------------|
| **Hard** | API key mancante, file policy assente | `ValueError` / `FileNotFoundError` in CLI |
| **Soft** | JSON malformato con `{` iniziale | Self-correction in-loop (consuma uno step); messaggio extra per scenari 7/10 |
| **Clarification retry** | LLM chiede chiarimenti su ticket legittimo (2, 5, 9) | Messaggio di correzione in-loop; **non** template injection |
| **Injection** | «DO NOT GENERATE JSON» (scenario 3) + testo piano LLM | `ClarificationNeeded` → `_progetto_injection_result` SECURITY |
| **Injection post-parse** | LLM produce JSON `IT`/`LOW` su scenario 3 | `_normalize_injection_result` → `_progetto_injection_result` |
| **Policy fallback** | Phishing/esfiltrazione/tablet senza `search_policy` | `_requires_policy_search` in `_apply_security_fallback` |
| **Payload strutturato** | Parser fallisce su input ostile (scenari 7/10) | `_progetto_payload_structured_result` (dal 3° errore o a max_steps) |
| **Max steps** | Esauriti gli step senza JSON (altri scenari) | `_progetto_max_steps_fallback` → SECURITY |
| **Arricchimento** | JSON valido ma `azione_eseguita` assente | `_enrich_progetto_result` da `_collect_tools_called` |

### Eventi audit (`logs/activity.jsonl`)

| `event_type` | Quando |
|--------------|--------|
| `progetto_clarification_injection` | Scenario 3 — testo non-JSON **e** `_is_prompt_injection_attempt` |
| `progetto_security_fallback` | Fallback `isolate_account` / `verify_sender_identity` |
| `react_max_steps_fallback` | Esauriti 6 step (o 8 per payload 7/10) ReAct |

---

## Fallback deterministici

`_apply_progetto_fallbacks` combina:

1. **`_apply_all_fallbacks`** — VIP budget > 10k€, sentiment ARRABBIATO, storico cliente critico
2. **`_apply_security_fallback`** — `search_policy` (se omesso), isolamento account, verifica CEO, ransomware

Iniettati come tool calls sintetici se l'LLM li omette.

### Budget step ReAct in `progetto_mode`

| Condizione | `max_steps` |
|------------|-------------|
| Default Progetto 2 | `DEFAULT_PROGETTO_REACT_MAX_STEPS` = **6** |
| Payload scenari 7/10 (`_needs_extra_react_steps`) | `PROGETTO_REACT_MAX_STEPS_PAYLOAD` = **8** |

### Arricchimento `azione_eseguita`

Dopo un JSON valido, `_enrich_progetto_result()` legge i tool dalla conversazione ReAct (`_collect_tools_called`) e compila `azione_eseguita` se l'LLM lo ha lasciato vuoto. Il report HTML confronta i tool attesi con questo campo.

### Euristica injection (`_is_prompt_injection_attempt`)

Attiva il template scenario 3 solo se il **messaggio utente** contiene indicatori come:

- `TERMINATE TRIAGE`
- `DO NOT GENERATE JSON`
- `BYPASS VALIDATION`
- `SYSTEM SAFE`

Ticket legittimi che generano chiarimenti LLM non matchano questa euristica e seguono il percorso di retry JSON.

Se l'LLM produce comunque JSON debole (`IT`/`LOW`), `_normalize_injection_result()` applica il template SECURITY.

### Payload ostili (scenari 7 e 10)

Quando `_needs_extra_react_steps(user_input)` è vero e il parser fallisce:

- Dal **3° errore** di validazione JSON → `_progetto_payload_structured_result()` (senza attendere max_steps).
- A **esaurimento step** → stessa funzione al posto di `_progetto_max_steps_fallback`.

Il risultato è un `TriageResult` valido con `messaggio_originale` verbatim e `search_policy` eseguito se non già presente.

---

## File chiave

| File | Ruolo |
|------|--------|
| `src/logic.py` | `react_triage`, fallback, `_normalize_injection_result`, `_progetto_payload_structured_result`, `_requires_policy_search` |
| `src/reporting/html_report.py` | Report HTML/JSON post-run |
| `src/parsing/parser.py` | `parse_llm_output` — validazione Pydantic |
| `src/main.py` | CLI demo scenari |
| `src/client.py` | Connessione OpenAI |
| `tests/test_logic.py` | ReAct, max_steps, self-correction |
| `tests/test_dataset_test.py` | Scenari SOC, injection gate, arricchimento `azione_eseguita` |

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
