# Manuale demo live — Settimana 15 (Lezione 20)

**Telemetria strutturata** — complementa [SETTIMANA_14_DEMO_LIVE.md](SETTIMANA_14_DEMO_LIVE.md) e [LEZIONE_20_STRUCTURED_TELEMETRY.md](LEZIONE_20_STRUCTURED_TELEMETRY.md).

**Branch:** `lesson-20-structured-telemetry` (**ultimo branch** del percorso lezioni 9–20)

---

## Prerequisiti

1. Checkout branch L20 e venv attivo.
2. `pip install -e ".[test,multiagent]"`
3. `PYTHONPATH=src python3 scripts/init_triage_db.py` (verifica colonne telemetry su `tickets`)
4. **Non serve** `OPENAI_API_KEY` per `l20a`; `l20b` usa mock interno — vedi sotto *Perché senza LLM*.
5. Leggere la [guida pratica telemetria](LEZIONE_20_STRUCTURED_TELEMETRY.md#come-usare-la-telemetria--guida-pratica).

### Perché le demo L20 sono senza LLM

L'obiettivo è insegnare **formula costo**, eventi JSONL e query SQL con numeri **prevedibili**. Con API reale i costi e le latenze variano per rete e modello. Dopo `l20a`/`l20b`, opzionale: un run `react_triage` con API per confrontare `tokens_est` (L17) e `usage` API (L20).

---

## Scenari L20

| Scenario | LLM | Contenuto |
|----------|-----|-----------|
| `l20a` | No | Formula costo, 2 chiamate mock con `usage`, confronto stima L17 |
| `l20b` | No (mock) | ReAct instrumentato → SQLite colonne L20 → query costo medio per `categoria` |
| `all` | Parziale | Sequenza L15–L20; `l20a`/`l20b` sempre eseguibili senza API key |

### Cosa fa ogni scenario (in breve)

**`l20a` — Formula e usage API**

Senza LLM:

1. Stampa tariffe da `data/model_pricing.json` e formula `cost_usd_milli`.
2. Simula due completion (`tool_turn` + `final_json`) con token fittizi.
3. Scrive eventi `llm_call_telemetry` e `triage_telemetry_complete` in `activity.jsonl`.
4. Mostra blocco `TELEMETRY` in `azione_eseguita` e confronto con `tokens_est` L17.

**`l20b` — SQLite e query management**

Con mock ReAct (due ticket IT e SALES):

1. Esegue `react_triage` instrumentato con `response.usage` mock.
2. Persiste su `tickets` con colonne `prompt_tokens`, `cost_usd_milli`, `pipeline`, ecc.
3. Stampa aggregato per `categoria` (query didattica SQL).

```bash
PYTHONPATH=src python3 src/main.py --scenario l20a
PYTHONPATH=src python3 src/main.py --scenario l20b
PYTHONPATH=src python3 src/main.py --scenario all
```

**Report aggregato SQLite:**

```bash
PYTHONPATH=src python3 -m analytics.telemetry_report
```

**KPI JSONL:**

```bash
PYTHONPATH=src python3 -m analytics.log_kpi
```

Report post-run: `logs/week12_demo_report.html` (sezioni L20a/L20b).

---

## Output atteso — `l20a`

```
=== L20a — Telemetria: formula costo e usage API (senza LLM) ===
Tariffe gpt-4.1-mini: input $0.4/M, output $1.6/M
  [tool_turn] usage in=1200 out=340 cost_milli=... latency_ms=450
  [final_json] usage in=800 out=120 ...
azione_eseguita arricchita: notify_manager | TELEMETRY cost_milli=...
```

---

## Output atteso — `l20b`

```
=== L20b — Telemetria: SQLite + query aggregata per categoria ===
  Ticket → IT | cost_milli=... tokens=900+180 ...
  Ticket → SALES | ...
=== TELEMETRIA SQLite (tickets L20) ===
Categoria       Avg USD     Avg ms      N
```

---

## Interazione con HITL (L19)

Le **pause HITL** non generano completion LLM: `llm_calls` in telemetria conta solo step con risposta API. Un run ReAct interrotto da `HitlApprovalRequired` non emette `triage_telemetry_complete` finché non ci sono completion registrate (vedi [LEZIONE_19](LEZIONE_19_HITL_BREAKPOINTS.md)).

---

## Troubleshooting

| Problema | Soluzione |
|----------|-----------|
| Colonne telemetry assenti su `tickets` | `PYTHONPATH=src python3 scripts/init_triage_db.py` |
| `l20b` saltato senza API key | Su branch L20 è in `_NO_LLM_SCENARIOS`; aggiornare `main.py` se manca |
| Query aggregata con una sola categoria | Normale se DB contiene solo ticket di una categoria; `l20b` inserisce IT + SALES |
| `cost_usd_milli` = 0 o 1 con pochi token | Arrotondamento formula didattica; aumentare token in demo o usare API reale |

---

## Checklist fine demo

- [ ] `activity.jsonl` contiene `llm_call_telemetry`
- [ ] `tickets` ha righe con `cost_usd_milli IS NOT NULL`
- [ ] Report HTML sezione L20 compilata
- [ ] Studenti capiscono differenza `tokens_est` (L17) vs `usage` API (L20)

## Documentazione correlata

- [SETTIMANA_14_DEMO_LIVE.md](SETTIMANA_14_DEMO_LIVE.md) — prerequisito HITL (L19)
- [LEZIONE_20_STRUCTURED_TELEMETRY.md](LEZIONE_20_STRUCTURED_TELEMETRY.md)
- [CORSO_LEZIONI.md](CORSO_LEZIONI.md)
- [GESTIONE_ERRORI.md](../GESTIONE_ERRORI.md)
