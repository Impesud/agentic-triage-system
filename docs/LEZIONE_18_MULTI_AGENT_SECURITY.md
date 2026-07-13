# Lezione 18 — Ingegneria della Sicurezza nei Sistemi Multi-Agente

**Settimana 13 (parte 1)** — complementa [LEZIONE_17_MULTI_AGENT_PERFORMANCE.md](LEZIONE_17_MULTI_AGENT_PERFORMANCE.md) e [CORSO_LEZIONI.md](CORSO_LEZIONI.md).

**Demo live:** [SETTIMANA_13_DEMO_LIVE.md](SETTIMANA_13_DEMO_LIVE.md) — sezioni `l18a`, `l18b` e sequenza `all`.

**Branch:** `lesson-18-multi-agent-security` (include lezioni 9–18).

**Durata:** 2 ore — Input Guardrail, injection indiretta, gate tool critici.

## Obiettivi didattici

1. Spiegare **Prompt Injection diretta e indiretta** in pipeline Analyst → Resolver.
2. Implementare un **Input Guardrail deterministico** pre-LLM con persistenza allerte SQLite.
3. Sanitizzare il **SharedHandoffContext** contro contaminazione del Blackboard.
4. Proteggere **tool critici** (`notify_manager`, stub `isolate_account`) con evidenza policy.

## 18.1 Blindare la pipeline da attacchi cognitivi

Nei sistemi coordinati, un ticket manipolato può forzare azioni SOC ostili (es. isolare l'amministratore dichiarando il sistema sicuro). Prima che il testo entri nella pipeline:

| Componente | Ruolo |
|------------|--------|
| [`input_guardrail.py`](../src/orchestration/input_guardrail.py) | `scan_ticket_input`, pattern regex su vettori noti |
| [`security_pipeline.py`](../src/orchestration/security_pipeline.py) | `guard_ticket_input` → SQLite + JSONL + `SecurityGuardrailError` |
| [`security_store.py`](../src/orchestration/security_store.py) | Tabella `security_alerts` |

Vettori rilevati: `POLICY_OVERRIDE`, `TOOL_HIJACK`, `DIRECT_INJECTION`, `LOG_SUPPRESSION`, `ROLE_OVERRIDE`.

Integrazione: `enable_security_guard=True` (default) su `triage_message`, `react_triage`, `multi_agent_triage`. I fallback L11 su `notify_manager` (priority ≥ 4) passano dal tool gate e richiedono `search_policy` nella stessa catena fallback.

### Confronto con scenario 3 progettino

| Approccio | Quando interviene | Ruolo |
|-----------|-------------------|--------|
| **L18 guardrail** | Prima dell'LLM, pattern deterministici | Blocco hard + allerta SQLite |
| **Scenario 3 progettino** | Durante/ dopo risposta LLM | Resilienza comportamentale del modello |

Le due strategie sono **complementari** (difesa in profondità), non sostitutive.

## 18.2 Mitigazione injection indiretta (hand-off)

Se l'Analyst propaga istruzioni ostili in `analyst_notes` / `policy_excerpt` / `ltm_digest`, il Resolver le tratta come contesto attendibile.

| Funzione | Comportamento |
|----------|---------------|
| `sanitize_handoff` | Scansiona campi Blackboard |
| `enforce_handoff_safety` | Blocca campi critici contaminati |
| `strip_injection_markers` | Redazione soft su campi non critici |

Hook in [`crew_pipeline.py`](../src/orchestration/crew_pipeline.py) e [`autogen_team.py`](../src/orchestration/autogen_team.py) dopo `enrich_handoff_from_cache`.

## 18.3 Protezione accesso ai tool critici

[`tool_policy_gate.py`](../src/orchestration/tool_policy_gate.py):

| Regola | Dettaglio |
|--------|-----------|
| `notify_manager` priority ≥ 3 | Richiede hit `search_policy` in cache o `policy_excerpt` nel hand-off |
| Target admin | Blocco isolamento/escalation su account amministratore senza categoria SECURITY |
| `isolate_account` | Stub in [`security_tools.py`](../src/tools/security_tools.py); sempre dietro gate |

Wrapper in [`tool_adapters.py`](../src/orchestration/tool_adapters.py) per CrewAI/AutoGen.

## Installazione

```bash
git checkout lesson-18-multi-agent-security
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[test,multiagent]"
PYTHONPATH=src python3 scripts/init_triage_db.py
```

## Demo live

```bash
PYTHONPATH=src python3 src/main.py --scenario l18a   # guardrail (no LLM)
PYTHONPATH=src python3 src/main.py --scenario l18b   # hand-off + tool gate (no LLM)
PYTHONPATH=src python3 src/main.py --scenario all    # L15 → L18
```

KPI sicurezza:

```bash
PYTHONPATH=src python3 -m analytics.log_kpi
```

## Test automatici (L18)

```bash
pytest tests/test_input_guardrail.py tests/test_handoff_sanitizer.py \
       tests/test_tool_policy_gate.py tests/test_security_store.py \
       tests/test_security_pipeline.py -q
pytest tests/ -q
```

## File chiave

| File | Ruolo L18 |
|------|-----------|
| [`errors.py`](../src/errors.py) | `SecurityGuardrailError` |
| [`orchestration/input_guardrail.py`](../src/orchestration/input_guardrail.py) | Pattern attacco |
| [`orchestration/security_pipeline.py`](../src/orchestration/security_pipeline.py) | Facade pre-pipeline |
| [`orchestration/security_store.py`](../src/orchestration/security_store.py) | SQLite `security_alerts` |
| [`orchestration/handoff_sanitizer.py`](../src/orchestration/handoff_sanitizer.py) | Blackboard |
| [`orchestration/tool_policy_gate.py`](../src/orchestration/tool_policy_gate.py) | Gate tool critici |
| [`tools/security_tools.py`](../src/tools/security_tools.py) | Stub `isolate_account` |
| [`main.py`](../src/main.py) | Demo `l18a`/`l18b` |

## Checklist docente

- [ ] Branch `lesson-18-multi-agent-security` attivo
- [ ] Demo `l18a`: ticket benigno ALLOWED, SOC weaponized BLOCKED
- [ ] Record in `security_alerts` visibili dopo `l18a`
- [ ] Demo `l18b`: hand-off avvelenato bloccato; `notify_manager` negato senza policy
- [ ] Eventi `security_input_blocked`, `security_tool_denied` in `activity.jsonl`
- [ ] `pytest tests/ -q` verde (~150 test)

## Nota branch L18

Su `lesson-18-multi-agent-security`, `main.py` espone anche `l18a`/`l18b` e la sequenza `all` estesa. Vedi [SETTIMANA_13_DEMO_LIVE.md](SETTIMANA_13_DEMO_LIVE.md).

## Prerequisito

[LEZIONE_17_MULTI_AGENT_PERFORMANCE.md](LEZIONE_17_MULTI_AGENT_PERFORMANCE.md) — orchestrazione e cache pipeline.

## Collegamenti

- [LEZIONE_16_CREW_AUTOGEN.md](LEZIONE_16_CREW_AUTOGEN.md) — Analyst/Resolver
- [LEZIONE_12_PROMPT_OPTIMIZATION.md](LEZIONE_12_PROMPT_OPTIMIZATION.md) — resilienza prompt (complementare)
- [MANUALE_PROGETTINO_DATASET_TEST.md](MANUALE_PROGETTINO_DATASET_TEST.md) — scenario 3 injection, tool SOC completi
- [GESTIONE_ERRORI.md](../GESTIONE_ERRORI.md) — eventi audit L18

## Lezioni successive — 19 e 20 (completate)

[LEZIONE_19_HITL_BREAKPOINTS.md](LEZIONE_19_HITL_BREAKPOINTS.md) — branch `lesson-19-hitl-breakpoints`. [LEZIONE_20_STRUCTURED_TELEMETRY.md](LEZIONE_20_STRUCTURED_TELEMETRY.md) — branch `lesson-20-structured-telemetry` (**corso completo 9–20**). Demo: [SETTIMANA_14_DEMO_LIVE.md](SETTIMANA_14_DEMO_LIVE.md), [SETTIMANA_15_DEMO_LIVE.md](SETTIMANA_15_DEMO_LIVE.md).

## Documentazione correlata

- [CORSO_LEZIONI.md](CORSO_LEZIONI.md) — mappa branch e comandi
- [SETTIMANA_13_DEMO_LIVE.md](SETTIMANA_13_DEMO_LIVE.md) — manuale operativo demo L18
- [README.md](../README.md) — architettura cumulativa
