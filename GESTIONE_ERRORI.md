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

Il codice ha una gestione errori di **livello 1–2**: fail-fast con `ValueError`, boundary in `main.py`, parser con `raise ... from e` su JSON e Pydantic, test su alcuni percorsi di fallimento. Manca ancora una **gerarchia di eccezioni di dominio**.

### Pipeline e punti di fallimento

Ogni ticket attraversa snapshot append-only in `data/tickets.jsonl`:

| Fase | Azione | Errore tipico | Stato su disco se fallisce |
|------|--------|---------------|----------------------------|
| 1 | `OPEN` + `save_ticket` | I/O su JSONL | Nessuna riga (o riga OPEN se save parziale) |
| 2 | `load_it_manual()` | `FileNotFoundError` | Riga **OPEN** già scritta |
| 3 | `call_llm()` | API key, rete, SDK OpenAI | Riga **OPEN** |
| 4 | `parse_llm_output()` | JSON assente/invalido, schema Pydantic | Riga **OPEN** |
| 5 | `enrich_priority()` | Ticket senza `priorita` | Riga **OPEN** (campi triage solo in memoria) |
| 6 | `TRIAGED` + `save_ticket` | Validazione `Ticket` incompleto | Riga **OPEN** |
| 7 | `assign_to_team()` + `save_ticket` | Categoria assente | Riga **TRIAGED** senza `team` |

```mermaid
flowchart TD
    A[user_input] --> B[OPEN save]
    B --> C{manuale + LLM + parse}
    C -->|errore| X[log + return None]
    C -->|ok| D[enrichment]
    D --> E[TRIAGED save]
    E --> F[routing + save team]
    F --> G[Ticket completo]
    B --> H[(tickets.jsonl)]
    E --> H
    F --> H
```

**Caso didattico importante:** se la chiamata LLM fallisce dopo il save `OPEN`, il ticket resta in JSONL senza classificazione. È uno **stato parziale** da discutere (rollback, flag `FAILED`, retry manuale).

**Scenario E (ambiguo SALES vs IT, RAG):** il ticket «acquistare il corso + pagina pagamento non carica» può essere classificato **SALES** dall’LLM se ignora il manuale. In quel caso il ticket resta comunque `OPEN` o viene salvato `TRIAGED` con categoria errata — utile in classe per confrontare output con e senza voce «Portale pagamenti» in `data/manuale_it.txt`. Criterio di successo: `categoria` IT e `analisi_problema` che cita il MANUALE ed esclude SALES (vedi [README.md](README.md)).

### Cosa esiste oggi

| Cosa | Dove | Note |
|------|------|------|
| `raise ValueError(...)` | `client.py`, `parser.py`, `enrichment.py`, `router.py`, `schemas/ticket.py` | Messaggi in italiano |
| `raise ... from e` | `parser.py` — `JSONDecodeError`, `ValidationError` | Catena traceback preservata |
| Boundary tipizzato | `main.py` — `except (FileNotFoundError, ValueError, OSError)` | Non più `except Exception` generico |
| Percorsi felici + fallimenti | `tests/` — 18 test, alcuni `pytest.raises` | Parser, store, enrichment, router |
| Percorsi centralizzati | `paths.py` | Log e dati non dipendono dalla CWD |
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
| `ValueError` | `client`, `parser`, Pydantic, enrichment, router | API key mancante, JSON invalido |
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
- Nessun test su `main.py` / `client.py` (solo moduli puri).

### Flusso oggi vs obiettivo

```mermaid
flowchart TD
    subgraph today [Oggi]
        A[user_input] --> B[process_ticket]
        B --> C{FileNotFoundError / ValueError / OSError}
        C -->|sì| D[log + print + None]
        C -->|ok| E[Ticket con team]
    end
    subgraph target [Obiettivo]
        F[user_input] --> G[process_ticket]
        G --> H{tipo errore}
        H -->|ConfigError| I[messaggio setup]
        H -->|ParseError| J[messaggio parsing]
        H -->|BusinessRuleError| K[messaggio regole]
        H -->|StorageError| L[messaggio I/O]
        H -->|ok| M[Ticket]
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

Un solo punto (`process_ticket` in `main.py`) decide **cosa mostrare all’utente** e **cosa loggare**, invece di spargere `print` in ogni modulo.

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
| `return None` + messaggio | CLI didattica, `run_demo_scenarios()`: un errore non deve far crashare tutti gli scenari |
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

**File da leggere:** `src/main.py`, `src/paths.py`, `src/parsing/parser.py`, `src/client.py`, `src/storage/store.py`, `src/tools/enrichment.py`, `src/tools/router.py`.

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
4. Aggiungi `tests/test_client.py` con `pytest.raises(ConfigError)`.

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

**Test già presenti / da estendere** in `tests/test_parser.py`:

- JSON valido (presente)
- Markdown fence (presente)
- Senza JSON (presente)
- Da aggiungere: JSON con campi mancanti → `ParseError` dopo migrazione

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
| API OpenAI | `client.py` | Eccezioni SDK → `LLMError(TriageError)` |
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
| `parser.py` | `ValueError` + `from e` | JSON / schema | `ParseError` + `from e` |
| `schemas/ticket.py` | `ValueError` (Pydantic) | Campi vuoti, TRIAGED incompleto | Resta in Pydantic; parser → `ParseError` |
| `main.py` | `FileNotFoundError` | Manuale assente | `ConfigError` o handler dedicato |
| `enrichment.py` | `ValueError` | Senza priorità | `BusinessRuleError` |
| `router.py` | `ValueError` | Senza categoria | `BusinessRuleError` |
| `store.py` | (nessuno) | `json.loads` su riga corrotta | `StorageError` (opz.) |
| `main.py` boundary | `FileNotFoundError`, `ValueError`, `OSError` | Tutti → stesso messaggio | Handler per tipo + `Exception` fallback |

---

## Test e copertura fallimenti

Suite attuale (`pytest tests/ -q`, `pythonpath = src` in `pyproject.toml`):

| Modulo | Test fallimento / edge |
|--------|----------------------|
| `parser.py` | Senza JSON, markdown fence |
| `store.py` | TRIAGED senza `analisi_problema`, persistenza `team` |
| `enrichment.py` | Keyword, senza priorità |
| `router.py` | IT, BILLING, SALES, SECURITY |
| `client.py` | — (da aggiungere, Modulo 2) |
| `main.py` | — (integrazione opzionale con mock LLM) |

Fixture condivise in `tests/conftest.py` (`triaged_ticket`, isolamento `TICKETS_PATH`).

---

## Checklist di completamento

- [ ] So disegnare il flusso di un errore da `call_llm` / `parse_llm_output` fino a `[ERRORE]` in console.
- [ ] So spiegare lo **stato parziale OPEN** in `tickets.jsonl` se fallisce LLM o manuale.
- [ ] Esistono almeno tre eccezioni di dominio sotto `TriageError`.
- [ ] `ParseError` usa `raise ... from e` (già nel parser come `ValueError`; da rinominare).
- [ ] Almeno cinque test con `pytest.raises` su percorsi di fallimento.
- [ ] Boundary in `main.py` con messaggi distinti per tipo.
- [ ] Resta un `except Exception` finale come rete di sicurezza.
- [ ] Nessun pattern superfluo (retry HTTP, middleware) per questa CLI.

---

## Messaggio riassuntivo

> Il progetto ha già boundary tipizzato, parser con `from e`, persistenza a snapshot (OPEN → TRIAGED → routed con `team`) e test sui fallimenti nei moduli core. Non serve rifare tutto né chiedere a Cursor un refactor unico.
>
> Percorso: (1) mappa errori e stati parziali su JSONL, (2) esercizio minimale su `raise from`, (3) `errors.py` e migra un modulo per volta con test, (4) boundary con messaggi per tipo in `main.py`.
>
> Prossimo passo consigliato: **Modulo 2** (`ConfigError` + `test_client.py`).

---

## Collegamenti

- [README.md](README.md) — pipeline, CoT, manuale IT, scenari demo, setup
- `src/main.py` — orchestrazione e boundary
- `src/paths.py` — percorsi assoluti (log, dati, manuale, `.env`)
- `src/parsing/parser.py` — parsing e incapsulamento
- `tests/conftest.py` — fixture condivise
- `tests/` — estendere qui i test sui fallimenti
