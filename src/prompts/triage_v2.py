"""
Prompt v2 — Lezione 12 (ottimizzazione basata sui log).

NON attivo di default: logic.py importa ancora triage_v1.
Per attivare v2 dopo il benchmark, sostituire in logic.py:
  from prompts.triage_v1 import build_chat_messages
con:
  from prompts.triage_v2 import build_chat_messages

Estensioni rispetto a v1 (da applicare copiando/adattando triage_v1.py):
- Richiamo esplicito: «Rispondi SEMPRE in JSON valido dopo i tool»
- Few-shot aggiuntivo ARRABBIATO → search_policy + notify_manager priority 4
"""

# Re-export per comodità didattica; l'esercizio consiste nel completare la migrazione.
from prompts.triage_v1 import FEW_SHOTS, SYSTEM_PROMPT, build_chat_messages

EXTRA_FEW_SHOT_ARRABBIATO = {
    "input": (
        "SONO FURIOSO! Ho perso 20.000 euro per il vostro disservizio. "
        "Vi denuncio e chiamo l'avvocato!"
    ),
    "output": {
        "analisi_problema": (
            "1. Problema: reclamo grave con minaccia legale. "
            "2. Contesto: search_policy su ARRABBIATO; notify_manager priority 4. "
            "3. Categoria: BILLING. 4. Priorità: CRITICAL."
        ),
        "categoria": "BILLING",
        "priorita": "CRITICAL",
        "riassunto_breve": "Cliente furioso minaccia legale",
        "messaggio_originale": (
            "SONO FURIOSO! Ho perso 20.000 euro per il vostro disservizio. "
            "Vi denuncio e chiamo l'avvocato!"
        ),
    },
}

# Lista target per v2 — lo studente la fonde in FEW_SHOTS quando passa a v2
FEW_SHOTS_V2_EXTENSION = [EXTRA_FEW_SHOT_ARRABBIATO]
