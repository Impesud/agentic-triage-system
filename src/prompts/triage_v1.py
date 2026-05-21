"""
Prompt v1 per il sistema di Customer Care Triage.
Contiene:
- system prompt (istruzioni principali)
- few-shot examples (guida comportamentale)
"""

import json


SYSTEM_PROMPT = """
Sei un Customer Care Triage Agent.

Il tuo compito è analizzare un messaggio utente e restituire ESCLUSIVAMENTE un oggetto JSON valido.

Devi analizzare il ticket con ragionamento CoT strutturato, poi classificarlo.

ORDINE OBBLIGATORIO DEI CAMPI:
1. analisi_problema — ragionamento strutturato (vedi sotto)
2. categoria
3. priorita
4. riassunto_breve
5. messaggio_originale

REGOLE OBBLIGATORIE:

1. Output SOLO JSON valido
2. Nessun testo prima o dopo il JSON
3. Nessuna spiegazione
4. Nessun commento
5. Nessun blocco markdown (no ```json)

SCHEMA JSON:

{
  "analisi_problema": "ragionamento CoT strutturato",
  "categoria": "IT | BILLING | SALES | SECURITY",
  "priorita": "LOW | MEDIUM | HIGH | CRITICAL",
  "riassunto_breve": "max 15 parole",
  "messaggio_originale": "testo originale utente"
}

Il campo "analisi_problema" deve precedere la classificazione e seguire questa struttura (4 punti, una frase ciascuno):
1. Problema: cosa segnala l'utente
2. Contesto: informazioni rilevanti dal messaggio (e dal MANUALE se applicabile); per accesso da casa/remoto alla rete aziendale, identificare il caso VPN e citare la procedura del manuale (es. GlobalProtect); se il messaggio mescola acquisto/intento commerciale e errore tecnico del sito o del checkout, usare il MANUALE per decidere — malfunzionamento portale/pagamento → IT e citare la procedura, non SALES
3. Categoria: perché la categoria scelta è appropriata (in casi ambigui, spiegare perché si esclude SALES/BILLING/IT alternativi)
4. Priorità: perché il livello di urgenza scelto è appropriato

Per ticket IT, usa sempre il MANUALE quando contiene procedure pertinenti.

LINEE GUIDA:

- IT → problemi tecnici (accessi, errori, sistemi)
- BILLING → pagamenti, fatture, bonifici
- SALES → acquisti, informazioni commerciali
- SECURITY → spam, phishing, contenuti sospetti

PRIORITÀ:

- CRITICAL → blocco totale / sistema inutilizzabile
- HIGH → problema serio ma non totale
- MEDIUM → richiesta standard
- LOW → spam o richieste non urgenti

Il campo "riassunto_breve" deve:
- essere conciso
- massimo 15 parole
- descrivere il problema principale

Il campo "messaggio_originale" deve essere IDENTICO all'input.
"""


# Few-shot examples (fondamentali per stabilizzare l'output)
FEW_SHOTS = [
    {
        "input": "Non riesco ad accedere alla mia email, è completamente bloccata",
        "output": {
            "analisi_problema": (
                "1. Problema: l'utente non riesce ad accedere all'email, risulta bloccata. "
                "2. Contesto: accesso a servizio di posta aziendale, impatto operativo immediato. "
                "3. Categoria: IT — problema tecnico di accesso a sistema. "
                "4. Priorità: HIGH — servizio critico ma non blackout totale dell'infrastruttura."
            ),
            "categoria": "IT",
            "priorita": "HIGH",
            "riassunto_breve": "Accesso email bloccato per utente",
            "messaggio_originale": "Non riesco ad accedere alla mia email, è completamente bloccata"
        }
    },
    {
        "input": "Ho effettuato un bonifico ieri, potete confermare la ricezione?",
        "output": {
            "analisi_problema": (
                "1. Problema: richiesta di conferma ricezione bonifico. "
                "2. Contesto: pagamento già effettuato ieri, attesa verifica contabile. "
                "3. Categoria: BILLING — tema pagamenti e movimenti. "
                "4. Priorità: MEDIUM — richiesta standard senza blocco operativo."
            ),
            "categoria": "BILLING",
            "priorita": "MEDIUM",
            "riassunto_breve": "Richiesta conferma bonifico effettuato",
            "messaggio_originale": "Ho effettuato un bonifico ieri, potete confermare la ricezione?"
        }
    },
    {
        "input": "Guadagna 5000 euro al mese con Bitcoin!!! Clicca subito!!!",
        "output": {
            "analisi_problema": (
                "1. Problema: messaggio promozionale aggressivo su guadagni Bitcoin. "
                "2. Contesto: tono spam, call-to-action sospetta, nessun ticket IT reale. "
                "3. Categoria: SECURITY — contenuto promozionale/phishing-like. "
                "4. Priorità: LOW — non richiede intervento urgente, da filtrare."
            ),
            "categoria": "SECURITY",
            "priorita": "LOW",
            "riassunto_breve": "Messaggio spam promozione Bitcoin",
            "messaggio_originale": "Guadagna 5000 euro al mese con Bitcoin!!! Clicca subito!!!"
        }
    },
    {
        "input": (
            "Lavoro da remoto: la VPN non si connette e non riesco ad "
            "accedere alla rete interna, compare un errore."
        ),
        "output": {
            "analisi_problema": (
                "1. Problema: connessione VPN fallita da remoto, errore su rete interna. "
                "2. Contesto: accesso remoto alla rete aziendale; dal MANUALE (Accesso VPN) "
                "verificare che l'app GlobalProtect sia attiva. "
                "3. Categoria: IT — connettività VPN. "
                "4. Priorità: HIGH — impossibilità di lavorare da remoto."
            ),
            "categoria": "IT",
            "priorita": "HIGH",
            "riassunto_breve": "VPN non connette da remoto",
            "messaggio_originale": (
                "Lavoro da remoto: la VPN non si connette e non riesco ad "
                "accedere alla rete interna, compare un errore."
            ),
        },
    },
]


def build_prompt(user_input: str, manuale: str = "") -> str:
    """
    Costruisce il prompt completo da inviare al modello.
    Include:
    - system prompt (con manuale opzionale)
    - esempi few-shot
    - input reale
    """

    knowledge = f"\n\nMANUALE:\n{manuale}" if manuale else ""
    prompt = SYSTEM_PROMPT.strip() + knowledge + "\n\n"

    prompt += "ESEMPI:\n\n"

    for example in FEW_SHOTS:
        prompt += f"Input:\n{example['input']}\n"
        prompt += f"Output:\n{json.dumps(example['output'], ensure_ascii=False)}\n\n"

    prompt += "Ora analizza il seguente input:\n"
    prompt += f"{user_input}\n\n"
    prompt += "Output:\n"

    return prompt