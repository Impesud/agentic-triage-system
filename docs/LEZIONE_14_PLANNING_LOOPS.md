# Lezione 14 — Planning Multi-Step Avanzato e Controllo dei Loop

**Settimana 9 (parte 2)** — complementa [README — Lezione 14](../README.md#planning-multi-step-lezione-14) e [CORSO_LEZIONI.md](CORSO_LEZIONI.md).

**Branch:** `lesson-14-planning-loops` (include lezioni 9–13).

## Obiettivi

1. Prevenire **Infinite Reasoning Loops** con `max_steps = 4` deterministico.
2. Implementare **Short-Term Memory** ReAct via `_SHORT_TERM_STORE` e `session_id`.
3. **Self-correction in-loop**: errori Pydantic reiniettati nel ciclo ReAct prima del fallback.

## 14.1 Prevenzione loop e riparazione sintattica

| Meccanismo | Implementazione |
|------------|-----------------|
| Hard stop | `DEFAULT_REACT_MAX_STEPS = 4` in [`logic.py`](../src/logic.py) |
| Fallback | `TriageResult` con `azione_eseguita: "Fallback per interruzione ciclo ReAct"` |
| Log audit | `event_type: react_max_steps_fallback` in JSONL |
| Self-correction | Errore Pydantic → messaggio `user` in-context → prossimo step ReAct |

Differenza da L11: la correzione avviene **dentro** il loop ReAct (consuma uno step), non solo in `_finalize_with_self_correction` post-loop.

## 14.2 Short-Term Memory ReAct

```python
from logic import react_triage

# Turno 1 — inizializza session_01
react_triage(ticket_1, manuale, session_id="session_01")

# Turno 2 — riusa la conversazione accumulata
react_triage(ticket_2, manuale, session_id="session_01")
```

Store: `_SHORT_TERM_STORE: dict[str, list]` — parallelo a `SessionManager` (M1, integer `ticket_id`) ma dedicato alla demo ReAct multi-turno.

## Comandi

```bash
PYTHONPATH=src python3 src/main.py --scenario l14

pytest tests/test_logic.py -k "react or short_term" -q
```

## Demo L14

Due ticket Marco Rossi sulla stessa `session_01`:

1. Budget 15k → manager (popola SQLite)
2. Richiesta sconto → agente consulta LTM SQL + STM del thread

## File chiave

| File | Modifica L14 |
|------|----------------|
| [`logic.py`](../src/logic.py) | `session_id`, `_SHORT_TERM_STORE`, in-loop self-correction, `max_steps=4` |
| [`main.py`](../src/main.py) | `process_ticket_react`, `run_l14_planning_demo` |

## Prerequisito

[LEZIONE_13_REACT_SQLITE.md](LEZIONE_13_REACT_SQLITE.md) — SQLite LTM e loop ReAct base.
