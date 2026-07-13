# Manuale demo live — Settimana 14 (Lezione 19) — completata

**Human-in-the-Loop e breakpoint workflow** — complementa [SETTIMANA_13_DEMO_LIVE.md](SETTIMANA_13_DEMO_LIVE.md) e [LEZIONE_19_HITL_BREAKPOINTS.md](LEZIONE_19_HITL_BREAKPOINTS.md) (guida completa: [come usare i breakpoint](LEZIONE_19_HITL_BREAKPOINTS.md#come-usare-i-breakpoint-guida-pratica)).

**Branch:** `lesson-19-hitl-breakpoints` (checkpoint Settimana 14). Su **`lesson-20-structured-telemetry`** la sequenza `all` include anche L20 — vedi [SETTIMANA_15_DEMO_LIVE.md](SETTIMANA_15_DEMO_LIVE.md).

---

## Prerequisiti

1. Checkout branch L19 e venv attivo.
2. `pip install -e ".[test,multiagent]"`
3. `PYTHONPATH=src python3 scripts/init_triage_db.py` (verifica `ticket_states`)
4. **Non serve** `OPENAI_API_KEY` per `l19a` e `l19b` — vedi sotto *Perché senza LLM*.
5. Leggere la [guida breakpoint](LEZIONE_19_HITL_BREAKPOINTS.md#come-usare-i-breakpoint-guida-pratica) prima della demo live.

### Cos'è HITL (in sintesi)

**HITL** = *Human-in-the-Loop* (umano nel ciclo). Per alcune azioni critiche il sistema **non esegue subito**: si ferma, salva lo stato su SQLite (`ticket_states`) e aspetta che un operatore **approvi** o **rifiuti**. È diverso dal tool gate L18, che **nega** in automatico senza coinvolgere una persona.

### Perché le demo L19 sono senza LLM

L'obiettivo è mostrare **regole e stati** (pausa, approve, reject), non la variabilità del modello. Con LLM la demo sarebbe meno ripetibile in aula. Il loop ReAct reale con HITL (`react_triage` + `react_triage_resume`) resta opzionale come esercizio avanzato.

---

## Scenari L19

| Scenario | LLM | Contenuto |
|----------|-----|-----------|
| `l19a` | No | Breakpoint HITL: notify p3 immediato, isolate_account → PENDING_APPROVAL |
| `l19b` | No | Approve → RESUMED + esecuzione tool; Reject → REJECTED |
| `all` | Parziale | Su branch L19: L15–L19. Su branch L20: L15–L20 (`l20a`/`l20b` senza API key) |

### Cosa fa ogni scenario (in breve)

**`l19a` — Quando scatta la pausa**

Simula due azioni critiche su un ticket SOC, **senza LLM**:

1. **`notify_manager` con priorità 3** → il tool parte **subito** (sotto la soglia HITL, nessuna pausa).
2. **`isolate_account`** → il sistema **si ferma**: salva la sessione su SQLite (`ticket_states`) con stato `PENDING_APPROVAL` e mostra il messaggio `[HITL PAUSED]`.

Obiettivo didattico: capire la **differenza** tra tool che passano e tool che richiedono approvazione umana.

**`l19b` — Cosa fa l'operatore dopo la pausa**

Crea due pause HITL di prova e mostra le due decisioni possibili, **senza LLM**:

1. **Approve** → l'operatore autorizza: il tool pendente viene **eseguito** e la sessione diventa `RESUMED`.
2. **Reject** → l'operatore rifiuta: il tool **non** parte e la sessione diventa `REJECTED`.

Obiettivo didattico: vedere il workflow **approve / reject** che in produzione si usa con `hitl_cli`.

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
- [ ] `python3 -m analytics.log_kpi` mostra sezione HITL L19 e telemetria L20 (su branch L20)
- [ ] `pytest tests/ -q` verde (174 su branch L19; **184** su L20)

---

## Documentazione correlata

- [LEZIONE_19_HITL_BREAKPOINTS.md](LEZIONE_19_HITL_BREAKPOINTS.md)
- [LEZIONE_20_STRUCTURED_TELEMETRY.md](LEZIONE_20_STRUCTURED_TELEMETRY.md) — lezione successiva (Settimana 15)
- [SETTIMANA_15_DEMO_LIVE.md](SETTIMANA_15_DEMO_LIVE.md)
- [CORSO_LEZIONI.md](CORSO_LEZIONI.md)
- [GESTIONE_ERRORI.md](../GESTIONE_ERRORI.md)
