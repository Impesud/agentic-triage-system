# Lezione 19 — Scalabilità del Flusso e Stato Human-in-the-Loop (HITL)

**Settimana 14** — complementa [LEZIONE_18_MULTI_AGENT_SECURITY.md](LEZIONE_18_MULTI_AGENT_SECURITY.md) e [CORSO_LEZIONI.md](CORSO_LEZIONI.md).

**Demo live:** [SETTIMANA_14_DEMO_LIVE.md](SETTIMANA_14_DEMO_LIVE.md) — sezioni `l19a`, `l19b` e sequenza `all`.

**Branch:** `lesson-19-hitl-breakpoints` (include lezioni 9–19).

**Durata:** 2 ore — Breakpoint deterministici, persistenza STM, resume workflow.

## Obiettivi didattici

1. Spiegare perché le **azioni irreversibili** richiedono approvazione umana oltre al tool gate L18.
2. Implementare **breakpoint deterministici** prima di `isolate_account` e `notify_manager` priority ≥ 4.
3. Persistere **STM e contesto pipeline** su SQLite (`ticket_states`) con `PENDING_APPROVAL`.
4. Eseguire **resume** via CLI operatore (`approve` / `reject`) e **riprendere il loop ReAct** dopo approvazione.

## 19.1 Azioni irreversibili e concorrenza

Il tool gate L18 **nega** azioni senza evidenza policy. La L19 **mette in pausa** azioni ammesse ma ad alto impatto:

| Tool | Regola HITL |
|------|-------------|
| `isolate_account` | Pausa sempre (dopo passaggio L18) |
| `notify_manager` | Pausa se `priority >= 4` |
| Altri tool | Esecuzione immediata |

Al breakpoint il runtime:

1. interrompe l'esecuzione del tool (non blocca il server con thread in attesa);
2. serializza STM (`stm_json`) e contesto (`pipeline_context_json`);
3. salva su `ticket_states` con `status = PENDING_APPROVAL`;
4. restituisce observation `[HITL PAUSED] session_id=…`.

**Moduli:** [`hitl_breakpoints.py`](../src/orchestration/hitl_breakpoints.py), [`hitl_pipeline.py`](../src/orchestration/hitl_pipeline.py)

## 19.2 Architettura database `ticket_states`

Tabella SQLite (oltre a `tickets` LTM e `security_alerts` L18):

| Colonna | Ruolo |
|---------|--------|
| `session_id` | Chiave univoca sessione HITL |
| `status` | `PENDING_APPROVAL` \| `RESUMED` \| `REJECTED` |
| `pending_tool` / `pending_args_json` | Azione in sospeso |
| `stm_json` | Snapshot conversazione ReAct |
| `pipeline_context_json` | Cache policy/LTM, handoff, categoria |

**Modulo:** [`hitl_store.py`](../src/orchestration/hitl_store.py)

**CLI operatore:**

```bash
PYTHONPATH=src python3 -m orchestration.hitl_cli list
PYTHONPATH=src python3 -m orchestration.hitl_cli approve <session_id> --operator mario.rossi
PYTHONPATH=src python3 -m orchestration.hitl_cli reject <session_id> --operator mario.rossi --reason "falso positivo"
```

## Integrazione pipeline

| Entry point | Flag | Note |
|-------------|------|------|
| `react_triage` | `enable_hitl=True` (default) | Pausa su tool critici nel loop ReAct |
| `triage_message` fallback L11 | `enable_hitl=False` | Fallback automatici VIP/ARRABBIATO senza pausa |
| `tool_adapters` | via `ToolPolicyContext.enable_hitl` | CrewAI / AutoGen Resolver |

**Eccezione:** `HitlApprovalRequired` in [`errors.py`](../src/errors.py)

## Resume ReAct completo

Dopo `approve_session`, se `pipeline_context_json` contiene `react_resume`:

1. l'observation del tool approvato viene aggiunta a `stm_json`;
2. `_SHORT_TERM_STORE` viene ripristinato con la conversazione aggiornata;
3. `react_triage_resume()` continua il loop dal passo successivo (`from_step + 1`) fino a JSON finale o `max_steps`.

Alias didattico: `resume_session = approve_session` in [`hitl_pipeline.py`](../src/orchestration/hitl_pipeline.py).

**Modulo:** [`logic.py`](../src/logic.py) — `react_triage_resume`, `_react_triage_loop`

## Installazione

```bash
git checkout lesson-19-hitl-breakpoints
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[test,multiagent]"
PYTHONPATH=src python3 scripts/init_triage_db.py
```

## Demo live

```bash
PYTHONPATH=src python3 src/main.py --scenario l19a   # breakpoint (no LLM)
PYTHONPATH=src python3 src/main.py --scenario l19b   # approve/reject (no LLM)
PYTHONPATH=src python3 src/main.py --scenario all    # L15 → L19
```

KPI HITL:

```bash
PYTHONPATH=src python3 -m analytics.log_kpi
```

## Test automatici (L19)

```bash
pytest tests/test_hitl_breakpoints.py tests/test_hitl_store.py \
       tests/test_hitl_pipeline.py tests/test_hitl_cli.py -q
pytest tests/ -q   # ~164 test
```

## File chiave

| File | Ruolo L19 |
|------|-----------|
| [`hitl_breakpoints.py`](../src/orchestration/hitl_breakpoints.py) | Regole breakpoint |
| [`hitl_store.py`](../src/orchestration/hitl_store.py) | SQLite `ticket_states` |
| [`hitl_pipeline.py`](../src/orchestration/hitl_pipeline.py) | Pause / approve / reject |
| [`hitl_cli.py`](../src/orchestration/hitl_cli.py) | CLI operatore |
| [`logic.py`](../src/logic.py) | Hook `_react_tool_output` |
| [`main.py`](../src/main.py) | Demo `l19a`/`l19b` |

## Checklist docente

- [ ] Branch `lesson-19-hitl-breakpoints` attivo
- [ ] Demo `l19a`: `isolate_account` → `PENDING_APPROVAL` in SQLite
- [ ] Demo `l19b`: approve → `RESUMED`; reject → `REJECTED`
- [ ] Eventi `hitl_breakpoint_reached`, `hitl_session_resumed` in `activity.jsonl`
- [ ] `pytest tests/ -q` verde

## Prerequisito

[LEZIONE_18_MULTI_AGENT_SECURITY.md](LEZIONE_18_MULTI_AGENT_SECURITY.md) — guardrail e tool policy gate.

## Collegamenti

- [LEZIONE_17_MULTI_AGENT_PERFORMANCE.md](LEZIONE_17_MULTI_AGENT_PERFORMANCE.md) — latenza pipeline
- [SETTIMANA_14_DEMO_LIVE.md](SETTIMANA_14_DEMO_LIVE.md) — manuale operativo
- [GESTIONE_ERRORI.md](../GESTIONE_ERRORI.md) — eventi audit L19

## Documentazione correlata

- [CORSO_LEZIONI.md](CORSO_LEZIONI.md) — mappa branch e comandi
- [README.md](../README.md) — architettura cumulativa
