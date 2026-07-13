# Manuale demo live — Settimana 14 (Lezione 19)

**Human-in-the-Loop e breakpoint workflow** — complementa [SETTIMANA_13_DEMO_LIVE.md](SETTIMANA_13_DEMO_LIVE.md) e [LEZIONE_19_HITL_BREAKPOINTS.md](LEZIONE_19_HITL_BREAKPOINTS.md).

**Branch:** `lesson-19-hitl-breakpoints`

---

## Prerequisiti

1. Checkout branch L19 e venv attivo.
2. `pip install -e ".[test,multiagent]"`
3. `PYTHONPATH=src python3 scripts/init_triage_db.py` (verifica `ticket_states`)
4. **Non serve** `OPENAI_API_KEY` per `l19a` e `l19b`.

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

## Troubleshooting

| Problema | Soluzione |
|----------|-----------|
| Tabella `ticket_states` assente | `PYTHONPATH=src python3 scripts/init_triage_db.py` |
| Sessioni pendenti da run precedenti | Normale in dev; `list` mostra tutte le `PENDING_APPROVAL` |
| Tool non eseguito dopo approve | Verificare `status=RESUMED` e output tool in console |

---

## Checklist fine sessione

- [ ] `l19a` e `l19b` eseguiti senza errori
- [ ] Almeno una riga `PENDING_APPROVAL` visibile in `l19a`
- [ ] `approve` / `reject` dimostrati in `l19b`
- [ ] `python3 -m analytics.log_kpi` mostra sezione HITL L19
