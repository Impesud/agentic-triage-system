# Settimana 12–15 — Guida alla demo live (Lezioni 15–20)

Manuale operativo per docenti e studenti: **come eseguire le demo L15–L20** sul branch corrente **`lesson-20-structured-telemetry`**. Checkpoint storico L19: `lesson-19-hitl-breakpoints` (senza `l20a`/`l20b`).

> **Branch `lesson-20-structured-telemetry` (corso completo 9–20):** include lezioni **15–20**. Demo L18 in [SETTIMANA_13](SETTIMANA_13_DEMO_LIVE.md), L19 in [SETTIMANA_14](SETTIMANA_14_DEMO_LIVE.md), L20 in [SETTIMANA_15](SETTIMANA_15_DEMO_LIVE.md). Con `--scenario all` vengono eseguiti **sempre** L18a/L18b, L19a/L19b e L20a/L20b anche senza API key.

Guide teoriche per singola lezione:

- [LEZIONE_15_MULTI_AGENT_COORDINATION.md](LEZIONE_15_MULTI_AGENT_COORDINATION.md) — topologie e Blackboard
- [LEZIONE_16_CREW_AUTOGEN.md](LEZIONE_16_CREW_AUTOGEN.md) — CrewAI e AutoGen
- [LEZIONE_17_MULTI_AGENT_PERFORMANCE.md](LEZIONE_17_MULTI_AGENT_PERFORMANCE.md) — pruning, cache, benchmark
- [LEZIONE_19_HITL_BREAKPOINTS.md](LEZIONE_19_HITL_BREAKPOINTS.md) — HITL (dettaglio: [SETTIMANA_14](SETTIMANA_14_DEMO_LIVE.md))
- [LEZIONE_20_STRUCTURED_TELEMETRY.md](LEZIONE_20_STRUCTURED_TELEMETRY.md) — telemetria (dettaglio: [SETTIMANA_15](SETTIMANA_15_DEMO_LIVE.md))

Indice corso: [CORSO_LEZIONI.md](CORSO_LEZIONI.md).

---

## Cosa fa `main.py` su questo branch

Su `lesson-20-structured-telemetry`, [`src/main.py`](../src/main.py) espone la Settimana 12–15:

| Scenario | Lezione | Funzione | API OpenAI |
|----------|---------|----------|------------|
| `l15` | 15 | Topologie + hand-off Blackboard | **No** |
| `l16a` | 16 | CrewAI pipeline sequenziale | **Sì** |
| `l16b` | 16 | AutoGen GroupChat | **Sì** |
| `l17a` | 17 | ReAct: baseline vs compact/cache vs full opt | **Sì** |
| `l17b` | 17 | Benchmark latenza multi-pipeline | **Sì** |
| `l18a` | 18 | Input Guardrail + `security_alerts` | **No** |
| `l18b` | 18 | Hand-off avvelenato + tool gate | **No** |
| `l19a` | 19 | Breakpoint HITL + `ticket_states` | **No** |
| `l19b` | 19 | Approve / reject workflow | **No** |
| `l20a` | 20 | Formula costo + mock `usage` API | **No** |
| `l20b` | 20 | ReAct mock → SQLite telemetry → query | **No** |
| `all` | 15→20 | Sequenza completa (L16/L17 saltati senza API; L18–L20 sempre) | misto |

Su **`lesson-19-hitl-breakpoints`**: stessi scenari fino a `l19b` (`all` → L19). Su **`lesson-18-multi-agent-security`**: `all` fino a L18.

**Demo storiche** (M1–M3, `l10`–`l14`, `process_ticket`): disponibili sui branch `main` … `lesson-14-*`, non su questo branch.

---

## Prerequisiti (prima di entrare in aula)

```bash
git checkout lesson-20-structured-telemetry
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[test,multiagent]"
```

1. **File `.env`** nella root del progetto con `OPENAI_API_KEY=sk-...` (non usare `export` in shell: il client legge da `.env`).
2. **Database SQLite** — creato automaticamente all'avvio di `main.py`, oppure:

```bash
PYTHONPATH=src python3 scripts/init_triage_db.py
ls -la data/triage_system.db
```

3. **Manuale IT** — presente in `data/manuale_it.txt` (caricato da `load_it_manual()`).
4. **Verifica test** (opzionale): `PYTHONPATH=src pytest tests/ -q` (**184** su L20; ~174 su L19).

---

## Comandi essenziali

Sempre con `PYTHONPATH=src` (o `export PYTHONPATH=src` nella sessione):

```bash
# Solo Lezione 15 — DEFAULT se non passi --scenario
PYTHONPATH=src python3 src/main.py
PYTHONPATH=src python3 src/main.py --scenario l15

# Lezione 16 — richiedono API key
PYTHONPATH=src python3 src/main.py --scenario l16a
PYTHONPATH=src python3 src/main.py --scenario l16b

# Lezione 17
PYTHONPATH=src python3 src/main.py --scenario l17a
PYTHONPATH=src python3 src/main.py --scenario l17b

# Lezione 19–20 (no API key)
PYTHONPATH=src python3 src/main.py --scenario l19a
PYTHONPATH=src python3 src/main.py --scenario l20a

# Intera Settimana 12–15 in sequenza
PYTHONPATH=src python3 src/main.py --scenario all

# Benchmark standalone (stesso ticket di l17b)
PYTHONPATH=src python3 src/benchmark_multi_agent.py

# KPI da activity.jsonl
PYTHONPATH=src python3 -m analytics.log_kpi
```

Al termine di ogni esecuzione vengono scritti:

| File | Ruolo |
|------|--------|
| **`logs/week12_demo_report.html`** | **Sintesi** per revisione post-lab: tabelle, badge, sezioni `<details>` con dati strutturati |
| **`logs/week12_demo_report.json`** | Stessi dati del builder in JSON (diff tra run, script) |
| **`logs/activity.jsonl`** | **Trace completo** step-by-step (eventi `pipeline_latency_report`, `security_*`, tool, ecc.) — non duplicato nell'HTML |

Contenuto HTML/JSON:

- **Riepilogo** di tutti gli scenari L15–L20 e stato (Eseguito / Saltato / Non eseguito)
- **Sezione per ogni lezione** con tabella sintetica + `<details>` espandibili (ticket, `TriageResult`, metriche ReAct, guardrail)
- Placeholder per scenari non eseguiti in quella run

**Non** include: dump integrale della console né ogni riga ReAct/CrewAI — per quello usare `activity.jsonl` o rivedere l'output terminale durante la demo.

Disabilitare report: `--no-report` · Disabilitare apertura browser: `--no-open`

Dopo ogni run il report si apre nel browser (su WSL usa il browser Windows). In alternativa:

```bash
PYTHONPATH=src python3 scripts/open_report.py
PYTHONPATH=src python3 scripts/open_report.py logs/week12_demo_report.html
```

### Attenzione: default ≠ sequenza completa

| Comando | Effetto |
|---------|---------|
| `python3 src/main.py` | Esegue **solo `l15`** (topologie, senza LLM) |
| `python3 src/main.py --scenario all` | Esegue **L15 → … → L20b** (vedi `run_week12_all()`) |

Per la demo live dell'intera settimana usare esplicitamente `--scenario all`.

---

## Guardrail API key (`api_guard`)

Se `OPENAI_API_KEY` manca in `.env`:

| Scenario | Comportamento |
|----------|---------------|
| `l15` | Funziona normalmente |
| `l16a`, `l16b`, `l17a`, `l17b` | Messaggio `[SKIP]`, exit 0 |
| `l18a`, `l18b`, `l19a`, `l19b`, `l20a`, `l20b` | Funzionano **senza** API key |
| `all` | Esegue `l15`, salta blocchi LLM con `[SKIP]`; L18–L20 sempre eseguiti |

Modulo: [`src/orchestration/api_guard.py`](../src/orchestration/api_guard.py).

---

## Ticket demo condiviso

Tutte le demo LLM usano lo stesso ticket (Marco Rossi, budget 15.000€):

> Sono Marco Rossi. Ho un budget di 15.000€ per un progetto AI e voglio parlare con un manager.

Costante: `L16_TICKET` in [`src/main.py`](../src/main.py). Esito tipico: `SALES` / `HIGH`, escalation VIP per budget > 10.000€.

---

## Cosa mostrare per ogni scenario

### `l15` (~15 min, senza API)

Topologie, squadra Impesud (tool partizionati), JSON `SharedHandoffContext` con `cliente_nome: Marco`.

### `l16a` (~20 min)

CrewAI sequenziale: due `kickoff`, JSON `TriageResult`, SQLite, eventi `crew_triage_complete` / `handoff_enriched_from_cache`.

### `l16b` (~20 min)

AutoGen GroupChat: `[AutoGen] Avvio pipeline...`, JSON finale, `autogen_triage_complete`.

### `l17a` (~25 min)

Tre run ReAct con tabella `Run | ms | tokens`:

| Run | Cosa dimostra |
|-----|----------------|
| baseline | Nessuna ottimizzazione |
| compact + cache | Output tool compatti + dedup embedding |
| full | Pruning + cache + compact |

### `l17b` (~15 min)

Tabella benchmark: `triage_message`, `react_triage`, `multi_agent_triage` (CrewAI/AutoGen).

### `all` (~90–120 min)

Ordine: `L15 → L16a → L16b → L17a → L17b → L18a → L18b → L19a → L19b → L20a → L20b` (vedi `run_week12_all()`).

---

## Timeline suggerita (3 sessioni da 2 ore)

| Sessione | Demo |
|----------|------|
| 1 — L15 | `--scenario l15` |
| 2 — L16 | `l16a` + `l16b` |
| 3 — L17 | `l17a` + `l17b` |
| 4 — L18–L19 | `l18a` + `l18b` + `l19a` + `l19b` |
| 5 — L20 | `l20a` + `l20b` |

Recap: `--scenario all`.

---

## Eventi in `logs/activity.jsonl`

| Evento | Lezione |
|--------|---------|
| `crew_triage_complete` | L16a |
| `autogen_triage_complete` | L16b |
| `handoff_enriched_from_cache` | L16/L17 |
| `embedding_cache_hit` | L17 |
| `message_pruning_applied` | L17 |
| `pipeline_latency_report` | L17b |
| `hitl_breakpoint_reached` | L19 |
| `llm_call_telemetry` | L20 |
| `triage_telemetry_complete` | L20 |

---

## Troubleshooting

| Problema | Soluzione |
|----------|-----------|
| `ModuleNotFoundError` | `export PYTHONPATH=src` |
| `[SKIP] OPENAI_API_KEY assente` | `.env` con chiave valida |
| `ImportError` CrewAI/AutoGen | `pip install -e ".[multiagent]"` |
| Demo `l10`–`l14` assenti | branch `lesson-13-*` … `lesson-14-*` |
