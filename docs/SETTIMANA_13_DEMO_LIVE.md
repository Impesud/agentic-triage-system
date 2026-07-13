# Manuale demo live — Settimana 13 (Lezione 18)

**Sicurezza nei sistemi multi-agente** — complementa [SETTIMANA_12_DEMO_LIVE.md](SETTIMANA_12_DEMO_LIVE.md) e [LEZIONE_18_MULTI_AGENT_SECURITY.md](LEZIONE_18_MULTI_AGENT_SECURITY.md).

**Branch:** `lesson-18-multi-agent-security` (checkpoint L18). Gli scenari `l18a`/`l18b` sono disponibili anche su **`lesson-20-structured-telemetry`** (corso completo 9–20).

---

## Prerequisiti

1. Checkout branch L18 e venv attivo.
2. `pip install -e ".[test,multiagent]"`
3. `PYTHONPATH=src python3 scripts/init_triage_db.py`
4. **Non serve** `OPENAI_API_KEY` per `l18a` e `l18b` (demo deterministiche).

---

## Scenari L18

| Scenario | LLM | Contenuto |
|----------|-----|-----------|
| `l18a` | No | Input Guardrail: 3 ticket (benigno, injection, SOC weaponized) + query `security_alerts` |
| `l18b` | No | Hand-off avvelenato + `notify_manager` con/senza evidenza policy |
| `all` | Parziale | Sequenza L15–L18; L18a/L18b sempre eseguiti anche senza API key |

### Cosa fa ogni scenario (in breve)

**`l18a` — Input Guardrail**

Senza LLM. Tre messaggi di prova:

1. Ticket **benigno** → passa
2. **Injection** (“ignora le istruzioni…”) → bloccato
3. **SOC weaponized** → bloccato

Le allerte finiscono in SQLite (`security_alerts`). Messaggio chiave: la difesa parte **prima** dell'LLM.

**`l18b` — Hand-off e tool gate**

Senza LLM. Tre prove:

1. Hand-off **avvelenato** tra agenti → bloccato
2. `notify_manager` priorità alta **senza** evidenza policy → negato
3. `notify_manager` **con** policy in cache → consentito

```bash
PYTHONPATH=src python3 src/main.py --scenario l18a
PYTHONPATH=src python3 src/main.py --scenario l18b
PYTHONPATH=src python3 src/main.py --scenario all
```

Report post-run (revisione studenti):

| File | Ruolo |
|------|--------|
| `logs/week12_demo_report.html` | Sintesi + `<details>` per L15–L20 (su branch L20; L15–L19 su branch L19) |
| `logs/week12_demo_report.json` | Stessi dati strutturati (diff tra run) |
| `logs/activity.jsonl` | Trace completo (`security_input_blocked`, `security_tool_denied`, …) |

---

## Output atteso — `l18a`

```
SCENARIO L18a — Input Guardrail e allerte SQLite
benigno                ALLOWED   nessun pattern di attacco
injection diretta      BLOCKED   Input bloccato dal guardrail ...
SOC weaponized         BLOCKED   Input bloccato dal guardrail ...

[SQLite] Ultime N allerte in security_alerts:
   #1 [CRITICAL] INPUT_INJECTION @ pre_pipeline: ...
```

---

## Output atteso — `l18b`

```
[1] Hand-off avvelenato → BLOCKED (SecurityGuardrailError)
[2] notify_manager priority=4 senza policy → [SECURITY DENIED]
[3] notify_manager con policy in cache → Notifica inviata con successo
```

---

## Troubleshooting

| Problema | Soluzione |
|----------|-----------|
| Nessuna riga in `security_alerts` | Eseguire `init_db()` o `scripts/init_triage_db.py` |
| Ticket benigno BLOCKED | Verificare pattern in `ATTACK_PATTERNS` — falsi positivi rari |
| `all` salta L16–L17 | Normale senza API key; L18a/L18b devono comunque eseguirsi |
| Confusione con `api_guard` L17 | `api_guard` = costo API docente; L18 = sicurezza input |

---

## Timeline aula (2 ore)

| Min | Attività |
|-----|----------|
| 0–20 | Teoria injection diretta vs indiretta |
| 20–35 | Teoria tool gate SOC |
| 35–70 | Lab `l18a` + ispezione SQLite |
| 70–100 | Lab `l18b` + KPI `log_kpi` |
| 100–120 | Confronto scenario 3 progettino, checklist |

---

## Checklist fine sessione

- [ ] Studente spiega differenza guardrail deterministico vs prompt hardening L12
- [ ] Studente legge allerta SQLite e evento JSONL correlato
- [ ] Studente descrive perché `notify_manager` priority 4 richiede evidenza policy
- [ ] `pytest tests/ -q` verde sul branch L18 (~150 test); **184** su `lesson-20-structured-telemetry`

---

## Lezione 19 — completata (Settimana 14)

La [Lezione 19](LEZIONE_19_HITL_BREAKPOINTS.md) estende L18 con breakpoint operatore, tabella `ticket_states` e resume ReAct (branch `lesson-19-hitl-breakpoints`).

## Lezione 20 — completata (Settimana 15)

La [Lezione 20](LEZIONE_20_STRUCTURED_TELEMETRY.md) aggiunge telemetria strutturata, costo USD e colonne L20 su `tickets` (branch **`lesson-20-structured-telemetry`** — corso completo 9–20).

| Risorsa | Link |
|---------|------|
| Teoria L19 + guida breakpoint | [LEZIONE_19_HITL_BREAKPOINTS.md](LEZIONE_19_HITL_BREAKPOINTS.md) |
| Demo live `l19a` / `l19b` | [SETTIMANA_14_DEMO_LIVE.md](SETTIMANA_14_DEMO_LIVE.md) |
| Teoria L20 + guida telemetria | [LEZIONE_20_STRUCTURED_TELEMETRY.md](LEZIONE_20_STRUCTURED_TELEMETRY.md) |
| Demo live `l20a` / `l20b` | [SETTIMANA_15_DEMO_LIVE.md](SETTIMANA_15_DEMO_LIVE.md) |
| Sequenza completa L15–L20 | `PYTHONPATH=src python3 src/main.py --scenario all` |

```bash
git checkout lesson-20-structured-telemetry
PYTHONPATH=src python3 src/main.py --scenario l19a
PYTHONPATH=src python3 src/main.py --scenario l20a
```
