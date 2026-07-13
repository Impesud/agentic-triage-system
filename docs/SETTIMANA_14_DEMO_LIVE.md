# Manuale demo live — Settimana 14 (Lezione 19) — completata

**Human-in-the-Loop e breakpoint workflow** — complementa [SETTIMANA_13_DEMO_LIVE.md](SETTIMANA_13_DEMO_LIVE.md) e [LEZIONE_19_HITL_BREAKPOINTS.md](LEZIONE_19_HITL_BREAKPOINTS.md) (guida completa: [come usare i breakpoint](LEZIONE_19_HITL_BREAKPOINTS.md#come-usare-i-breakpoint-guida-pratica)).

**Branch:** `lesson-19-hitl-breakpoints` (**ultimo branch** del percorso lezioni 9–19)

---

## Prerequisiti

1. Checkout branch L19 e venv attivo.
2. `pip install -e ".[test,multiagent]"`
3. `PYTHONPATH=src python3 scripts/init_triage_db.py` (verifica `ticket_states`)
4. **Non serve** `OPENAI_API_KEY` per `l19a` e `l19b`.
5. Leggere la [guida breakpoint](LEZIONE_19_HITL_BREAKPOINTS.md#come-usare-i-breakpoint-guida-pratica) prima della demo live.

---

## Scenari L19

| Scenario | LLM | Contenuto |
|----------|-----|-----------|
| `l19a` | No | Breakpoint HITL: notify p3 immediato, isolate_account → PENDING_APPROVAL |
| `l19b` | No | Approve → RESUMED + esecuzione tool; Reject → REJECTED |
| `all` | Parziale | Sequenza L15–L19; L19a/L19b sempre eseguiti anche senza API key |

```bash
PYTHONPATH=src python3 src/main.py --scenario l19a
PYTHONPATH=src python3 src/main.py --scenario l19b
PYTHONPATH=src python3 src/main.py --scenario all
```

**CLI operatore (post-demo):**

```bash
PYTHONPATH=src python3 -m orchestration.hitl_cli list
PYTHONPATH=src python3 -m orchestration.hitl_cli approve <session_id> --operator docente
PYTHONPATH=src python3 -m orchestration.hitl_cli reject <session_id> --operator docente --reason "motivo"
```

Report post-run: `logs/week12_demo_report.html` (sezioni L19a/L19b).

---

## Output atteso — `l19a`

```
SCENARIO L19a — Breakpoint HITL e ticket_states SQLite
[1] notify_manager priority=3 → esecuzione immediata
[2] isolate_account → PAUSED — session_id=hitl-l19a-isolate
[SQLite] Sessioni PENDING_APPROVAL: ...
```

---

## Output atteso — `l19b`

```
[2] Approve operatore → RESUMED
[4] Reject operatore → REJECTED
```

Eventi JSONL: `hitl_breakpoint_reached`, `hitl_session_approved`, `hitl_session_resumed`, `hitl_session_rejected`.

---

## Resume ReAct (integrazione `react_triage`)

Le demo `l19a`/`l19b` usano `invoke_critical_tool_with_hitl` **senza LLM**. Nel percorso reale con `react_triage`:

1. al breakpoint, `HitlApprovalRequired` interrompe il loop; STM salvato in `ticket_states`;
2. `pipeline_context_json` include `react_resume` (sessione ReAct, step, manuale, flag ottimizzazioni);
3. dopo `approve`, `react_triage_resume()` ripristina `_SHORT_TERM_STORE` e continua dal passo successivo.

Session ID HITL nel loop ReAct: `hitl-{react_session_id}` (distinto dalla sessione STM ReAct).

---

## Troubleshooting

| Problema | Soluzione |
|----------|-----------|
| Tabella `ticket_states` assente | `PYTHONPATH=src python3 scripts/init_triage_db.py` |
| Demo `l19a`/`l19b` fallisce su secondo run | ID fissi: le demo chiamano `delete_ticket_state` prima del run; in dev usare `list` e pulire manualmente |
| Sessioni pendenti da run precedenti | Normale in dev; `list` mostra tutte le `PENDING_APPROVAL` |
| Tool non eseguito dopo approve | Verificare `status=RESUMED` e output tool in console |
| Loop ReAct non riparte dopo approve | Verificare `react_resume` in `pipeline_context_json` e evento `hitl_session_resumed` |

---

## Checklist fine sessione

- [ ] `l19a` e `l19b` eseguiti senza errori
- [ ] Almeno una riga `PENDING_APPROVAL` visibile in `l19a`
- [ ] `approve` / `reject` dimostrati in `l19b`
- [ ] Spiegata differenza demo tool-only vs resume ReAct in `react_triage`
- [ ] `python3 -m analytics.log_kpi` mostra sezione HITL L19
- [ ] `pytest tests/ -q` verde (174 test)
