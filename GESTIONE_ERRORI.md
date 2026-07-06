# Gestione degli errori — Manuale didattico

Manuale per introdurre e migliorare la gestione degli errori nel progetto **Agentic Customer Care Triage System**.  
Complementa il [README.md](README.md): qui trovi il *perché*, il *come* e il *percorso* passo passo; nel README restano setup, pipeline ed esecuzione.

---

## A chi serve

- **Studente:** capire se conviene partire da zero, modificare il progetto prima, o usare Cursor per tutto in una volta.
- **Docente / tutor:** avere una scaletta condivisa per le revisioni e la valutazione.

---

## Risposta breve

**Non serve né rifare tutto da zero senza progetto né chiedere a Cursor l’implementazione completa in una sola sessione.**

Il percorso consigliato è:

1. **Capire cosa c’è già** in questo repository (base didattica valida, già estesa con CoT, manuale IT e test sui fallimenti parziali).
2. **Imparare i concetti** su un esempio minuscolo (10–15 righe), senza LLM né Pydantic.
3. **Estendere il progetto reale a piccoli passi**, ognuno con uno o due test che falliscono e poi passano.
4. **Usare Cursor come tutor mirato** (anche con il piano gratuito), non come “refactor automatico di centinaia di righe”.

L’abbonamento a Cursor **non è necessario** per questo argomento. Conta molto di più **spezzare il lavoro** che avere il modello più potente.

---

## Stato attuale del progetto

Il codice ha una gestione errori di **livello 1–3**: fail-fast con `ValueError`, boundary in `main.py` (pipeline ticket su branch storici; branch L18: demo L15–L18), parser con `raise ... from e`, loop in `logic.py` (`_run_agent_loop` + `_finalize_with_self_correction` — Lezione 11), memoria, RAG + ChromaDB (Lezione 10/10B), self-correction (Lezione 11), benchmark/log KPI (Lezione 12), **ReAct multi-step + SQLite LTM** (Lezioni 13–14), **modelli multi-agente** (Lezione 15), **orchestrazione CrewAI/AutoGen** (Lezione 16), **guardrail sicurezza MAS** (Lezione 18) con [`errors.SecurityGuardrailError`](src/errors.py), suite di **~142 test** su branch `lesson-18-multi-agent-security`. La gerarchia `errors.py` è avviata (L18); restano opzionali i Moduli 2–4 completi.

**Indice corso e branch:** [docs/CORSO_LEZIONI.md](docs/CORSO_LEZIONI.md).

### Nucleo agentico (`logic.py`) — riferimento rapido

Il triage LLM vive in un unico loop (vedi [README — Architettura](README.md#architettura)):

1. `build_chat_messages` — cronologia (`history`) + few-shot + manuale IT  
2. `_call_llm_with_tools` — prima risposta con `TOOLS_DEFINITION`  
3. `_execute_tool_calls` — tool locali (se `tool_calls`)  
4. `_apply_all_fallbacks` — policy (VIP, ARRABBIATO) + long-term (storico cliente)  
5. `_finalize_with_self_correction` — `_request_final_json` + `parse_llm_output` con retry (max 3) e emergency fallback  

**Percorso parallelo (L13–L14):** `react_triage()` — loop ReAct con `max_steps` (4 su L14), self-correction in-loop su JSON invalido, fallback `react_max_steps_fallback`. Non sostituisce `triage_message` usato da benchmark e demo M1–M3.

Se la prima risposta non è JSON e non ci sono tool, `logic` solleva `ClarificationNeeded` (non è un errore fatale: `main` stampa `[CHIARIMENTO]` e il ticket resta `OPEN`).

**Hard error** (API, file): boundary in `main.py` → `log_event` + `return None`. **Soft error** (JSON/schema): self-correction in `logic.py`; se esaurito → `emergency_fallback` (ticket strutturato valido, non `None`).

### Pipeline e punti di fallimento

Ogni ticket attraversa snapshot append-only in `data/tickets.jsonl`:

| Fase | Azione | Errore tipico | Stato su disco se fallisce |
|------|--------|---------------|----------------------------|
| 1 | `OPEN` + `save_ticket` | I/O su JSONL | Nessuna riga (o riga OPEN se save parziale) |
| 2 | `load_it_manual()` | `FileNotFoundError` | Riga **OPEN** già scritta |
| 3 | `logic.triage_message()` (LLM, tool, `parse_llm_output`) | API key, rete, SDK, JSON/schema | Riga **OPEN** |
| 4 | `enrich_priority()` | Ticket senza `priorita` | Riga **OPEN** (triage solo in memoria) |
| 5 | `TRIAGED` + `save_ticket` | Validazione `Ticket` incompleto | Riga **OPEN** |
| 6 | `assign_to_team()` + `save_ticket` | Categoria assente | Riga **TRIAGED** senza `team` |

```mermaid
flowchart TD
    Input[user_input] --> OpenSave["main: OPEN + save_ticket"]
    OpenSave --> LoadManual["main: load_it_manual"]
    LoadManual -->|FileNotFoundError| ErrBoundary["main: except + return None"]
    LoadManual --> Triage["logic: triage_message"]

    subgraph agentErrors [logic.py - _run_agent_loop]
        Triage --> Build["build_chat_messages"]
        Build --> Client["client.get_client"]
        Client -->|API key assente| ErrBoundary
        Client --> Llm1["_call_llm_with_tools"]
        Llm1 --> HasTools{tool_calls?}
        HasTools -->|sì| ExecTools["_execute_tool_calls"]
        HasTools -->|no| Fallback["_apply_all_fallbacks"]
        ExecTools --> Fallback
        Fallback --> Clarify{testo non-JSON?}
        Clarify -->|sì| ClarExc[ClarificationNeeded]
        Clarify -->|no| NeedJson{serve JSON\nfinale?}
        NeedJson -->|sì| FinalJson["_request_final_json"]
        NeedJson -->|no| DirectContent["content prima risposta"]
        FinalJson -->|risposta vuota / JSON invalido| ErrBoundary
        DirectContent -->|vuoto| ErrBoundary
        FinalJson --> Parse["parse_llm_output"]
        DirectContent --> Parse
        Parse -->|ValueError schema| ErrBoundary
    end

    Parse -->|ok| Enrich["main: enrich_priority"]
    Enrich -->|senza priorita| ErrBoundary
    Enrich --> TriagedSave["main: TRIAGED + save"]
    TriagedSave --> Route["main: assign_to_team + save"]
    Route -->|senza categoria| ErrBoundary
    Route --> Done[Ticket completo con team]

    OpenSave --> Jsonl[(tickets.jsonl)]
    TriagedSave --> Jsonl
    Route --> Jsonl
    ErrBoundary --> LogErr["log_event error"]
```

**Caso didattico importante:** se la chiamata LLM fallisce dopo il save `OPEN`, il ticket resta in JSONL senza classificazione. È uno **stato parziale** da discutere (rollback, flag `FAILED`, retry manuale).

**Demo e lezioni:** vedi [README.md](README.md) e [docs/CORSO_LEZIONI.md](docs/CORSO_LEZIONI.md).

**SQLite (L13–L14):** `data/triage_system.db` è gitignored e creato da `init_db()` all'avvio di `main.py` o via `scripts/init_triage_db.py`. Assenza del file dopo clone non è un errore finché non serve LTM.

| Lezione | Errori / resilienza | Documentazione |
|---------|---------------------|----------------|
| 9 | `ClarificationNeeded`, stati OPEN parziali | README — Memoria |
| 10 | RAG + ChromaDB; fallback keyword se RAG/Chroma fallisce | README — RAG, [LEZIONE_10B](docs/LEZIONE_10B_CHROMADB.md) |
| 11 | Self-correction, `emergency_fallback` | [LEZIONE_11_RESILIENZA.md](docs/LEZIONE_11_RESILIENZA.md) |
| 12 | KPI su `triage_json_retry` / benchmark | [LEZIONE_12_PROMPT_OPTIMIZATION.md](docs/LEZIONE_12_PROMPT_OPTIMIZATION.md) |
| 13 | ReAct loop, SQLite LTM, dual-write | [LEZIONE_13_REACT_SQLITE.md](docs/LEZIONE_13_REACT_SQLITE.md) |
| 14 | `max_steps`, STM ReAct, self-correction in-loop | [LEZIONE_14_PLANNING_LOOPS.md](docs/LEZIONE_14_PLANNING_LOOPS.md) |
| 15 | Topologie, hand-off Blackboard (concettuale) | [LEZIONE_15_MULTI_AGENT_COORDINATION.md](docs/LEZIONE_15_MULTI_AGENT_COORDINATION.md) |
| 16 | CrewAI/AutoGen, fallback `multi_agent_fallback` | [LEZIONE_16_CREW_AUTOGEN.md](docs/LEZIONE_16_CREW_AUTOGEN.md) |
| 17 | Pruning, cache pipeline, benchmark latenza | [LEZIONE_17_MULTI_AGENT_PERFORMANCE.md](docs/LEZIONE_17_MULTI_AGENT_PERFORMANCE.md) |
| 18 | Guardrail input, hand-off, tool gate, `security_alerts` | [LEZIONE_18_MULTI_AGENT_SECURITY.md](docs/LEZIONE_18_MULTI_AGENT_SECURITY.md) |

**Lezione 17 — Performance:** eventi `message_pruning_applied`, `embedding_cache_hit`, `pipeline_latency_report` in [`log_kpi.py`](src/analytics/log_kpi.py).

**Lezione 18 — Sicurezza MAS:** eventi `security_input_blocked`, `security_handoff_blocked`, `security_tool_denied`, `handoff_field_redacted`; allerte in tabella SQLite `security_alerts` ([`security_store.py`](src/orchestration/security_store.py)); eccezione [`SecurityGuardrailError`](src/errors.py).

**Lezione 12 — Benchmark e log:** suite in [`src/benchmark.py`](src/benchmark.py), KPI in [`src/analytics/log_kpi.py`](src/analytics/log_kpi.py). Eventi `triage_json_retry`, `emergency_fallback` e (L14) `react_max_steps_fallback` alimentano le metriche.

**Lezione 11:** `_finalize_with_self_correction`, `MAX_TRIAGE_JSON_RETRIES = 3`, `_emergency_triage_result` — non confondere con retry HTTP illimitato.





### Lezione 16 — Orchestrazione multi-agent

| Errore / caso | Comportamento |
|---------------|---------------|
| Dipendenze `[multiagent]` assenti | `ImportError` con hint `pip install -e ".[multiagent]"` |
| JSON Resolver invalido | `multi_agent_fallback` + `TriageResult` emergency |
| CrewAI / AutoGen API failure | Propaga come `ValueError` o errore SDK; boundary `main` cattura su demo |
| Hand-off incompleto | Seed `SharedHandoffContext` + output Analyst nel task Resolver |

Eventi audit: `crew_triage_complete`, `autogen_triage_complete`, `multi_agent_fallback`.

### Lezione 17 — Performance multi-agente

| Evento | Significato |
|--------|-------------|
| `message_pruning_applied` | Observation tool compattate nella history ReAct |
| `embedding_cache_hit` | Query policy/LTM servita da `PipelineContextCache` |
| `pipeline_latency_report` | Misura wall-time da `benchmark_multi_agent.py` |

Flag `enable_optimizations` su `react_triage` e `multi_agent_triage` attiva pruning + cache.

### Lezione 18 — Sicurezza multi-agente

| Evento | Significato |
|--------|-------------|
| `security_input_blocked` | Ticket bloccato da `guard_ticket_input` prima dell'LLM |
| `security_handoff_blocked` | `SharedHandoffContext` contaminato su campi critici |
| `security_tool_denied` | Tool critico negato da `tool_policy_gate` |
| `handoff_field_redacted` | Campo soft del Blackboard ripulito da marker injection |
| `isolate_account_stub` | Stub didattico isolamento AD (no-op auditabile) |

Persistenza: tabella `security_alerts` in SQLite (`alert_type`, `severity`, `blocked_stage`, `input_excerpt`).

Eccezione: `SecurityGuardrailError` in [`src/errors.py`](src/errors.py) — interrompe la pipeline senza chiamata LLM.

**Demo live Settimana 13:** [docs/SETTIMANA_13_DEMO_LIVE.md](docs/SETTIMANA_13_DEMO_LIVE.md) — `l18a`/`l18b` **non** richiedono API key (distinto da `api_guard` L17).

### Lezione 15 — Multi-agent (concettuale)

La Lezione 15 **non introduce nuovi errori runtime**: il package `orchestration/` definisce modelli statici (`AgentSpec`, `SharedHandoffContext`) e la demo `l15` simula un hand-off senza chiamate LLM.

| Aspetto | Comportamento |
|---------|---------------|
| Demo `l15` | Nessuna API key richiesta; stampa topologie e Blackboard serializzato |
| Hand-off Analyst → Resolver | `SharedHandoffContext` in `build_resolver_task_description` / prompt Resolver |
| Retrocompatibilità | `triage_message` e `react_triage` invariati; nessun nuovo evento JSONL |

**Lezione 14 — ReAct:** se il loop esaurisce `max_steps` senza JSON valido, `react_triage` restituisce un `TriageResult` di fallback (non `None`) e logga `react_max_steps_fallback`. La self-correction **in-loop** (JSON invalido senza tool) consuma uno step e reinietta l'errore Pydantic — distinta dalla self-correction L11 post-loop.

**M1** → ticket `OPEN` su chiarimento. **M2** → long-term SQLite + escalation Marco. **L10** → RAG sinonimica. **L13/L14** → `react_triage` (branch storici). **L15** → topologie senza LLM. **L16** → `multi_agent_triage`. Fallback policy/LTM in `_apply_all_fallbacks` (non sono errori).

**Demo live Settimana 12–13:** [docs/SETTIMANA_12_DEMO_LIVE.md](docs/SETTIMANA_12_DEMO_LIVE.md), [docs/SETTIMANA_13_DEMO_LIVE.md](docs/SETTIMANA_13_DEMO_LIVE.md) — `main.py` default = solo `l15`; `--scenario all` = sequenza L15→L18; `api_guard` salta LLM senza API key; L18a/L18b sempre eseguiti.

Il fallback **non è un errore**: è una guardia operativa in `_run_agent_loop` dopo la prima risposta LLM; le observation entrano nel contesto della seconda chiamata. Se un tool solleva eccezione, il boundary in `main.py` cattura `ValueError`/`OSError`.

**RAG `search_policy` (Lezione 10):** percorso **principale** = `semantic_policy_search` (embeddings + soglia 0.38). In condizioni normali l’LLM riceve `[RAG semantica | score=…]` — **non** si usano keyword. **Eccezione:** in `office_tools.py`, errori API key / rete / embeddings (`ValueError`, `OSError`, `RuntimeError`) o score sotto 0.38 non propagano al ticket: `search_policy` ripiega su `_search_policy_keyword` (Lezione 6). La demo L10 invoca `semantic_policy_search` direttamente; il fallback keyword compare solo se la RAG fallisce (messaggio `[NOTA] …` in `main.py`).

**ChromaDB (Lezione 10B):** indice in [`src/rag/chroma_store.py`](src/rag/chroma_store.py), persistenza `data/chroma/`. Errori Chroma/I/O o score &lt; 0.38 → fallback keyword in `search_policy`. Guida: [LEZIONE_10B_CHROMADB.md](docs/LEZIONE_10B_CHROMADB.md).

```mermaid
flowchart TD
    Input[user_input] --> Already{notify_manager\ngià invocato?}
    Already -->|sì| End[Fine]
    Already -->|no| VIP{budget > 10.000€?}
    VIP -->|sì| N1[notify_manager priority 4]
    VIP -->|no| Angry{sentiment ARRABBIATO?}
    Angry -->|sì| SP[search_policy sentiment]
    SP --> N2[notify_manager priority 4]
    Angry -->|no| End
    N1 --> End
    N2 --> End
```

Dettaglio scenari: [README — Demo](README.md#demo-ed-esecuzione), [CORSO_LEZIONI](docs/CORSO_LEZIONI.md).

### Cosa esiste oggi

| Cosa | Dove | Note |
|------|------|------|
| `raise ValueError(...)` | `client.py`, `logic.py`, `parser.py`, `enrichment.py`, `router.py`, `schemas/ticket.py` | Messaggi in italiano |
| `raise ... from e` | `parser.py` — `JSONDecodeError`, `ValidationError` | Catena traceback preservata |
| Boundary tipizzato | `main.py` — `except (FileNotFoundError, ValueError, OSError)` | Cattura errori da tutta la pipeline |
| Suite test essenziale | `tests/` — **~145 test** (branch `lesson-18`), alcuni `pytest.raises` | Vedi tabella sotto |
| Percorsi centralizzati | `paths.py` | Manuale, policy, ticket, log, `.env` |
| Separazione agente / orchestrazione | `logic.py` (`_run_agent_loop`) vs `main.py` | Errori LLM nascono nel nucleo loop, gestiti in `main` |
| Nessuna eccezione di dominio | — | Obiettivo dei moduli 2–4 |

### Boundary attuale (`main.py`)

```python
except (FileNotFoundError, ValueError, OSError) as e:
    log_event("error", {"message": str(e), "input": user_input})
    print("\n[ERRORE]", str(e))
    return None
```

| Tipo catturato | Origine tipica | Esempio |
|----------------|----------------|---------|
| `FileNotFoundError` | `load_it_manual()` | `data/manuale_it.txt` assente |
| `ValueError` | `client`, `logic`, `parser`, Pydantic, enrichment, router | API key, risposta vuota LLM, JSON invalido |
| `OSError` | `save_ticket`, `log_event` | Permessi, disco pieno |

**Non catturato qui:** errori SDK OpenAI non mappati (es. `AuthenticationError`) — possono far crashare `process_ticket` se non derivano da `ValueError`/`OSError`. Modulo 5 opzionale.

### Incapsulamento nel parser (`parsing/parser.py`)

```python
except json.JSONDecodeError as e:
    raise ValueError(f"JSON non valido: {e}") from e

except ValidationError as e:
    raise ValueError(f"Errore validazione TriageResult: {e}") from e
```

Estrazione JSON con **parentesi bilanciate** (non regex greedy): riduce falsi positivi su testo extra.

**Migrazione didattica:** sostituire `ValueError` con `ParseError` mantenendo `from e` (Modulo 3).

### Gap da affrontare gradualmente

- Nessuna gerarchia `TriageError` / `ConfigError` / `ParseError` / `BusinessRuleError`.
- Errori OpenAI SDK non tradotti in tipi applicativi.
- JSONL: nessuna gestione esplicita di righe corrotte in `next_ticket_id()`.
- Boundary non distingue messaggi per tipo (config vs parsing vs regole).
- Stato parziale `OPEN` dopo fallimento LLM non documentato in UI/log dedicato.
- Suite essenziale (40 test): parser, store, enrichment, router, logic, memory, history_tools, tools, main; nessun E2E con API reale.

### Flusso oggi vs obiettivo

```mermaid
flowchart LR
    subgraph today [Boundary storico — main.py branch lesson-9..14]
        direction TB
        T1[user_input] --> T2[process_ticket]
        T2 --> T3[logic.triage_message]
        T3 --> T4{FileNotFoundError\nValueError\nOSError}
        T4 -->|catturato| T5["log_event + print\nreturn None"]
        T4 -->|ok| T6[Ticket con team]
    end
    subgraph l17 [Boundary L17 — main.py --scenario]
        direction TB
        S1[--scenario l15..l17b] --> S2{api_guard}
        S2 -->|no API key| S3["[SKIP] messaggio"]
        S2 -->|ok| S4[demo L15/L16/L17]
    end
    subgraph target [Obiettivo — handler dedicati]
        direction TB
        G1[user_input] --> G2[process_ticket]
        G2 --> G3[logic.triage_message]
        G3 --> G4{tipo errore}
        G4 -->|ConfigError| G5[messaggio setup]
        G4 -->|ParseError| G6[messaggio parsing LLM]
        G4 -->|LLMError| G7[messaggio API/rete]
        G4 -->|BusinessRuleError| G8[messaggio regole]
        G4 -->|StorageError| G9[messaggio I/O JSONL]
        G4 -->|ok| G10[Ticket]
        G4 -->|Exception| G11[fallback imprevisto]
    end
```

---

## Concetti fondamentali

Prima di toccare il progetto, assicurati di distinguere questi ruoli.

### 1. Creare l’errore (`raise`)

Segnala che qualcosa è andato storto **in questo punto** del codice.

```python
if not api_key:
    raise ConfigError('API key non trovata. Imposta OPENAI_API_KEY in ".env".')
```

### 2. Incapsulare / tradurre (catturare e rilanciare)

Un modulo interno (es. parser JSON) conosce dettagli tecnici; il resto dell’app deve vedere errori **del dominio** (es. “risposta LLM non interpretabile”).

```python
except json.JSONDecodeError as e:
    raise ParseError(f"JSON non valido: {e}") from e
```

`from e` collega l’eccezione nuova a quella originale: utile in debug e nelle review.

### 3. Boundary (confine applicazione)

Un solo punto di boundary decide **cosa mostrare all’utente** e **cosa loggare**, invece di spargere `print` in ogni modulo. Su branch storici (`lesson-9` … `lesson-14-*`) il confine è `process_ticket` in `main.py`; sul branch L17 è la CLI `--scenario` con guardrail [`api_guard.py`](src/orchestration/api_guard.py) per scenari LLM.

### 4. Gerarchia di eccezioni

```text
Exception
└── TriageError          # base del dominio
    ├── ConfigError      # setup (.env, API key, manuale)
    ├── ParseError       # output LLM / JSON / schema
    ├── BusinessRuleError  # enrichment, routing
    ├── LLMError         # (opzionale) rete / API OpenAI
    └── StorageError     # (opzionale) file JSONL
```

Vantaggi:

- `except ParseError` senza intercettare errori di configurazione.
- `except TriageError` come rete di sicurezza per tutto il dominio.
- `except Exception` solo come fallback per bug imprevisti.

### 5. `return None` vs far risalire l’eccezione

| Scelta | Quando ha senso |
|--------|------------------|
| `return None` + messaggio | CLI didattica (branch storici): un errore non deve far crashare la demo corrente |
| Eccezione che risale | Librerie riusabili, API HTTP (status 4xx/5xx), test che verificano il tipo esatto |

In questo corso, **`None` + messaggio differenziato** in `main.py` è sufficiente.

---

## Cosa NON fare

| Approccio | Perché sconsigliato |
|-----------|---------------------|
| Prompt unico: *“implementa la gestione errori completa”* | Diff enorme, difficile da rivedere e da spiegare a voce |
| Copiare pattern da progetti enterprise | Retry policy, error codes HTTP, middleware — over-engineering su ~400 righe |
| Refactor + test + logging in una sola sessione | Nessun consolidamento intermedio |

**Regola pratica:** ogni sessione = **un obiettivo**, **al massimo due file**, **almeno un test**.

---

## Percorso in 6 moduli

Durata indicativa: 30 min – 2 ore per modulo.

### Modulo 0 — Inventario (≈ 30 min, senza Cursor)

**Obiettivo:** mappare errori e **stati parziali** nel repo attuale.

1. Cerca tutti i `raise` e tutti i `except` (`rg "raise|except" src/`).
2. Per ciascuno annota: chi **crea**, chi **trasforma**, chi **mostra** all’utente.
3. Traccia due casi:
   - *“L’LLM restituisce testo senza JSON”* → `parse_llm_output` → `main` → `[ERRORE]`
   - *“Manca `manuale_it.txt`”* → dopo save `OPEN` → cosa c’è in `tickets.jsonl`?

**Domande guida:**

- Cosa succede se manca `OPENAI_API_KEY`?
- Cosa succede se manca `data/manuale_it.txt`?
- Perché l’ultimo snapshot può avere `team` valorizzato ma status ancora `TRIAGED`?
- `return None` è sempre la scelta giusta per un’API REST?

**File da leggere:** `src/main.py`, `src/logic.py` (`_run_agent_loop`, `_apply_all_fallbacks`, `ClarificationNeeded`), `src/memory/`, `src/tools/history_tools.py`, `src/client.py`, `src/prompts/triage_v1.py`, `src/parsing/parser.py`, `src/tools/office_tools.py`, `src/tools/registry.py`, `src/storage/store.py`, `src/tools/enrichment.py`, `src/tools/router.py`.

**Output atteso:** schema flusso errori + tabella stati parziali su JSONL.

---

### Modulo 1 — Concetti su esempio minimale (fuori dal progetto)

**Obiettivo:** eccezioni custom e `raise ... from` senza rumore di LLM/Pydantic.

Crea un file temporaneo (es. `esempio_errori.py`, **non** da committare):

```python
class ErroreApp(Exception):
    """Base per tutti gli errori dell'app didattica."""


class ErroreParsing(ErroreApp):
    """Input non interpretabile."""


def parse_numero(s: str) -> int:
    try:
        return int(s)
    except ValueError as e:
        raise ErroreParsing(f"non è un numero: {s!r}") from e


def main() -> None:
    for valore in ("42", "abc"):
        try:
            print(parse_numero(valore))
        except ErroreParsing as e:
            print("Parsing fallito:", e)
        except ErroreApp as e:
            print("Errore app:", e)


if __name__ == "__main__":
    main()
```

**Esercizi:** confronta traceback con e senza `from e`; aggiungi `except Exception` e discuti perché il fallback va limitato al boundary.

---

### Modulo 2 — Gerarchia minima (`src/errors.py` + `client.py`)

**Obiettivo:** primo tipo di dominio + test.

1. Crea `src/errors.py` con `TriageError`, `ConfigError`, `ParseError`, `BusinessRuleError`.
2. In `client.py`, sostituisci `ValueError` (API key) con `ConfigError`.
3. In `main.py`, aggiungi `except ConfigError` **prima** del blocco generico.
4. Aggiungi un test con `pytest.raises(ConfigError)` (es. in `tests/test_logic.py` mockando `get_client`, o file `tests/test_errors.py`).

**Prompt Cursor sicuro:**

> Aggiungi `src/errors.py` con `TriageError` e `ConfigError`. In `client.py` usa `ConfigError` per API key mancante. In `main.py` gestisci `ConfigError` con messaggio dedicato. Un test con `pytest.raises(ConfigError)`.

**Verifica:** `pytest tests/ -q`

---

### Modulo 3 — Parser (`parsing/parser.py`)

**Obiettivo:** `ParseError` al posto di `ValueError` (il `from e` c’è già).

| Situazione | Eccezione target |
|------------|------------------|
| Nessun `{...}` bilanciato | `ParseError` |
| `json.loads` fallisce | `ParseError` con `from e` |
| `TriageResult` non valido | `ParseError` con `from e` da `ValidationError` |

**Test già presenti** in `tests/test_parser.py`:

- JSON valido
- Senza JSON → `ValueError`

**Da aggiungere (opzionale):** JSON con campi mancanti → `ParseError` dopo migrazione; fence markdown se il modello restituisce ` ```json `.

```python
import pytest
from errors import ParseError
from parsing.parser import parse_llm_output


def test_parse_json_senza_campi_obbligatori():
    raw = '{"categoria":"IT"}'
    with pytest.raises(ParseError):
        parse_llm_output(raw)
```

---

### Modulo 4 — Boundary in `main.py`

**Obiettivo:** messaggi differenziati; firma `Ticket | None` invariata.

Sostituire il blocco unico con handler in ordine dal più specifico al più generico:

```python
from errors import BusinessRuleError, ConfigError, ParseError, TriageError

try:
    ...
except ConfigError as e:
    log_event("error", {"type": "config", "message": str(e), "input": user_input})
    print("\n[ERRORE CONFIGURAZIONE]", str(e))
    return None
except ParseError as e:
    log_event("error", {"type": "parse", "message": str(e), "input": user_input})
    print("\n[ERRORE PARSING]", str(e))
    return None
except BusinessRuleError as e:
    log_event("error", {"type": "business", "message": str(e), "input": user_input})
    print("\n[ERRORE REGOLA]", str(e))
    return None
except FileNotFoundError as e:
    log_event("error", {"type": "file", "message": str(e), "input": user_input})
    print("\n[ERRORE FILE]", str(e))
    return None
except TriageError as e:
    ...
except OSError as e:
    ...
except Exception as e:
    log_event("error", {"type": "unexpected", "message": str(e), "input": user_input})
    print("\n[ERRORE IMPREVISTO]", str(e))
    return None
```

Migrare `enrichment.py` e `router.py` da `ValueError` a `BusinessRuleError`.

**Discussione:** perché `FileNotFoundError` per il manuale può diventare `ConfigError` se il manuale è considerato prerequisito di deploy?

---

### Modulo 5 — (Opzionale) OpenAI e storage

| Area | File | Azione |
|------|------|--------|
| API OpenAI | `logic.py` (+ `client.get_client`) | Eccezioni SDK → `LLMError(TriageError)` |
| JSONL | `storage/store.py` | Riga corrotta in `next_ticket_id` → log + `StorageError` o skip documentato |
| Stato parziale | `main.py` | Log evento `ticket_stuck_open` se fallisce post-OPEN; (avanzato) status `FAILED` |

Un concetto per sessione: non mescolare rete, filesystem e parsing nello stesso pomeriggio.

---

## Usare Cursor senza sprecare token

| Uso consigliato | Uso da evitare |
|-----------------|----------------|
| “Spiegami questo `except` in `main.py`” | “Refactora tutta la gestione errori” |
| “Scrivi solo il test per JSON invalido” | “Allinea tutto il progetto alle best practice” |
| “Perché resta OPEN in JSONL se fallisce l’LLM?” | Incollare l’intero `src/` per review totale |

---

## Inventario rapido dei `raise` attuali

Checklist Modulo 0 — aggiornare dopo ogni migrazione.

| File | Tipo attuale | Esempio | Target |
|------|--------------|---------|--------|
| `client.py` | `ValueError` | API key mancante | `ConfigError` |
| `logic.py` | `ValueError` | Risposta vuota nel ciclo ReAct | `LLMError` o `ParseError` |
| `logic.py` | Fallback ReAct | `max_steps` esauriti | `TriageResult` strutturato + `react_max_steps_fallback` (non raise) |
| `logic.py` | `ClarificationNeeded` | `_apply_all_fallbacks` — tool in conversation, non raise | Documentato in README; opz. `BusinessRuleError` se tool fallisce |
| `parser.py` | `ValueError` + `from e` | JSON / schema | `ParseError` + `from e` |
| `schemas/ticket.py` | `ValueError` (Pydantic) | Campi vuoti, TRIAGED incompleto | Resta in Pydantic; parser → `ParseError` |
| `main.py` | `FileNotFoundError` | Manuale assente | `ConfigError` o handler dedicato |
| `enrichment.py` | `ValueError` | Senza priorità | `BusinessRuleError` |
| `router.py` | `ValueError` | Senza categoria | `BusinessRuleError` |
| `store.py` | (nessuno) | `json.loads` su riga corrotta | `StorageError` (opz.) |
| `main.py` boundary | `FileNotFoundError`, `ValueError`, `OSError` | Tutti → stesso messaggio | Handler per tipo + `Exception` fallback |

---

## Test e copertura fallimenti

Suite essenziale: **~142 test** su branch `lesson-18-multi-agent-security` (`pytest tests/ -q`). Nessuna chiamata API reale (mock su LLM e embeddings). Conteggi per branch: [CORSO_LEZIONI](docs/CORSO_LEZIONI.md).

| File test | Cosa copre |
|-----------|------------|
| `test_parser.py` | JSON valido; assenza JSON |
| `test_store.py` | `next_ticket_id`; ultimo snapshot |
| `test_enrichment.py` | Keyword priorità |
| `test_router.py` | Routing 4 categorie |
| `test_logic.py` | Loop mock; fallback policy |
| `test_tools.py` | Tool + registry (mock embeddings per `search_policy`) |
| `test_policy_semantic.py` | Chunking, cosine, RAG sinonimi, fallback keyword (solo eccezione) |
| `test_session_manager.py` | Short-term memory |
| `test_extractors.py` | `cliente_nome`, sentiment |
| `test_history_tools.py` | Long-term memory (SQLite) |
| `test_logger_sqlite.py` | Init DB, insert, query indicizzata (L13) |
| `test_main.py` | Scenari demo M1–M3 |
| `test_benchmark.py` | Report benchmark (L12) |
| `test_log_kpi.py` | KPI JSONL (L12) |
| `test_orchestration.py` | Topologie, hand-off Blackboard (L15) |
| `test_multi_agent.py` | CrewAI/AutoGen mock (L16) |
| `test_week12_report.py` / `test_main_report.py` | Report HTML Settimana 12–13 (L15–L18) |
| `test_input_guardrail.py` / `test_security_pipeline.py` | Guardrail L18 |
| `test_open_html.py` / `test_open_report_script.py` | Apertura report nel browser (WSL) |

Fixture in `tests/conftest.py`: `triaged_ticket`, isolamento `TICKETS_PATH` su file temporaneo.

**Non coperto dai test:** errori SDK OpenAI non mappati, righe JSONL corrotte, E2E con API key reale.

---

## Checklist di completamento

- [ ] So disegnare il flusso di un errore da `logic.triage_message` → `_run_agent_loop` → `parse_llm_output` fino a `[ERRORE]` in console.
- [ ] So spiegare lo **stato parziale OPEN** in `tickets.jsonl` se fallisce LLM o manuale.
- [ ] Esistono almeno tre eccezioni di dominio sotto `TriageError`.
- [ ] `ParseError` usa `raise ... from e` (già nel parser come `ValueError`; da rinominare).
- [ ] Almeno cinque test con `pytest.raises` su percorsi di fallimento (oggi: parser, enrichment, logic — estendere dopo `errors.py`).
- [ ] Boundary in `main.py` con messaggi distinti per tipo.
- [ ] Resta un `except Exception` finale come rete di sicurezza.
- [ ] Nessun pattern superfluo (retry HTTP, middleware) per questa CLI.

---

## Messaggio riassuntivo

> Il progetto ha boundary in `main.py`, self-correction su soft error (L11), emergency fallback validato Pydantic, memoria, RAG, benchmark/log KPI (L12), ReAct + SQLite (L13–L14), modelli multi-agente (L15), orchestrazione L16 e 83 test. Non serve rifare tutto né un refactor unico con Cursor.
>
> Percorso opzionale residuo: gerarchia `errors.py` (Moduli 2–4) per messaggi boundary più granulari — **dopo** L11–L16.
>
> Prossimo passo didattico opzionale: **Modulo 2** (`ConfigError` in `client.py`) oppure ottimizzazione **triage_v2** guidata da benchmark (L12).

---

## Collegamenti

- [README.md](README.md) — architettura, demo, setup
- [docs/CORSO_LEZIONI.md](docs/CORSO_LEZIONI.md) — indice lezioni e branch
- [docs/LEZIONE_11_RESILIENZA.md](docs/LEZIONE_11_RESILIENZA.md) — self-correction e fallback
- [docs/LEZIONE_12_PROMPT_OPTIMIZATION.md](docs/LEZIONE_12_PROMPT_OPTIMIZATION.md) — benchmark e prompt
- [docs/LEZIONE_13_REACT_SQLITE.md](docs/LEZIONE_13_REACT_SQLITE.md) — ReAct e SQLite LTM
- [docs/LEZIONE_14_PLANNING_LOOPS.md](docs/LEZIONE_14_PLANNING_LOOPS.md) — max_steps, STM, self-correction in-loop
- [docs/LEZIONE_15_MULTI_AGENT_COORDINATION.md](docs/LEZIONE_15_MULTI_AGENT_COORDINATION.md) — topologie, Role/Goal/Backstory, Blackboard
- [docs/LEZIONE_16_CREW_AUTOGEN.md](docs/LEZIONE_16_CREW_AUTOGEN.md) — CrewAI, AutoGen, multi_agent_triage
- [`scripts/init_triage_db.py`](scripts/init_triage_db.py) — bootstrap SQLite post-clone
- [`data/schema/triage_system.sql`](data/schema/triage_system.sql) — DDL LTM
- `src/main.py` — orchestrazione e boundary
- `src/logic.py` — nucleo loop agentico (`triage_message`, `react_triage`, tool, fallback)
- `src/tools/logger.py` — audit JSONL + SQLite LTM (`init_db`, `log_triage_to_sqlite`)
- `src/client.py` — connessione OpenAI
- `src/paths.py` — percorsi assoluti (log, dati, `TRIAGE_DB_PATH`, manuale, policy, `.env`)
- `src/parsing/parser.py` — parsing e incapsulamento
- `src/rag/policy_semantic.py` — chunking, embeddings, cosine similarity (Lezione 10)
- `src/tools/office_tools.py` — `search_policy` (RAG principale; keyword in eccezione), `notify_manager`
- `src/tools/history_tools.py` — `search_long_term_history` (delega a SQLite)
- `src/memory/` — `SessionManager`, extractors
- `tests/conftest.py` — fixture condivise
- `tests/test_*.py` — suite essenziale (~142 test su L18); estendere dopo ogni migrazione errori
