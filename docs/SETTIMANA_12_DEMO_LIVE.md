# Settimana 12 — Guida alla demo live (Lezioni 15, 16 e 17)

Manuale operativo per docenti e studenti: **come eseguire le demo L15–L17** dal branch corrente.

> **Branch `lesson-19-hitl-breakpoints`:** include anche la **Lezione 19** (`l19a`, `l19b`). Vedi [SETTIMANA_14_DEMO_LIVE.md](SETTIMANA_14_DEMO_LIVE.md). Con `--scenario all` vengono eseguiti **sempre** L18a/L18b e L19a/L19b anche senza API key.

Guide teoriche per singola lezione:

- [LEZIONE_15_MULTI_AGENT_COORDINATION.md](LEZIONE_15_MULTI_AGENT_COORDINATION.md) — topologie e Blackboard
- [LEZIONE_16_CREW_AUTOGEN.md](LEZIONE_16_CREW_AUTOGEN.md) — CrewAI e AutoGen
- [LEZIONE_17_MULTI_AGENT_PERFORMANCE.md](LEZIONE_17_MULTI_AGENT_PERFORMANCE.md) — pruning, cache, benchmark

Indice corso: [CORSO_LEZIONI.md](CORSO_LEZIONI.md).

---

## Cosa fa `main.py` su questo branch

Su `lesson-17-multi-agent-performance`, [`src/main.py`](../src/main.py) espone la Settimana 12:

| Scenario | Lezione | Funzione | API OpenAI |
|----------|---------|----------|------------|
| `l15` | 15 | Topologie + hand-off Blackboard | **No** |
| `l16a` | 16 | CrewAI pipeline sequenziale | **Sì** |
| `l16b` | 16 | AutoGen GroupChat | **Sì** |
| `l17a` | 17 | ReAct: baseline vs compact/cache vs full opt | **Sì** |
| `l17b` | 17 | Benchmark latenza multi-pipeline | **Sì** |
| `all` | 15→17 | Sequenza L15–L17 (L16/L17 saltati senza API key) | misto |

Su **`lesson-18-multi-agent-security`** aggiungere: `l18a`, `l18b` (no LLM) e `all` esteso a L15→L18.

**Demo storiche** (M1–M3, `l10`–`l14`, `process_ticket`): disponibili sui branch `main` … `lesson-14-*`, non su questo branch.

---

## Prerequisiti (prima di entrare in aula)

```bash
git checkout lesson-17-multi-agent-performance
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
4. **Verifica test** (opzionale): `PYTHONPATH=src pytest tests/ -q` (~106 su L17, ~150 su L18, **174** su L19).

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

# Intera Settimana 12 in sequenza
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

- **Riepilogo** di tutti gli scenari L15–L18 e stato (Eseguito / Saltato / Non eseguito)
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
| `python3 src/main.py --scenario all` | Esegue **L15 → L16a → L16b → L17a → L17b** |

Per la demo live dell'intera settimana usare esplicitamente `--scenario all`.

---

## Guardrail API key (`api_guard`)

Se `OPENAI_API_KEY` manca in `.env`:

| Scenario | Comportamento |
|----------|---------------|
| `l15` | Funziona normalmente |
| `l16a`, `l16b`, `l17a`, `l17b` | Messaggio `[SKIP]`, exit 0 |
| `l18a`, `l18b` | Funzionano **senza** API key |
| `all` | Esegue `l15`, poi salta blocchi LLM con `[SKIP]`; su L18 esegue sempre `l18a`/`l18b` |

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

### `all` (~60–90 min)

Ordine: `L15 → L16a → L16b → L17a → L17b` (vedi `run_week12_all()`).

---

## Timeline suggerita (3 sessioni da 2 ore)

| Sessione | Demo |
|----------|------|
| 1 — L15 | `--scenario l15` |
| 2 — L16 | `l16a` + `l16b` |
| 3 — L17 | `l17a` + `l17b` |

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

---

## Troubleshooting

| Problema | Soluzione |
|----------|-----------|
| `ModuleNotFoundError` | `export PYTHONPATH=src` |
| `[SKIP] OPENAI_API_KEY assente` | `.env` con chiave valida |
| `ImportError` CrewAI/AutoGen | `pip install -e ".[multiagent]"` |
| Demo `l10`–`l14` assenti | branch `lesson-13-*` … `lesson-14-*` |
