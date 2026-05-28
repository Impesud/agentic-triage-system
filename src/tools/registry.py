from tools.history_tools import search_long_term_history
from tools.office_tools import notify_manager, search_policy

TOOL_MAP = {
    "notify_manager": notify_manager,
    "search_policy": search_policy,
    "search_long_term_history": search_long_term_history,
}

TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "notify_manager",
            "description": (
                "Invia escalation immediata al manager di turno. Obbligatorio per "
                "richieste SALES con budget dichiarato superiore a 10.000€, sentiment "
                "ARRABBIATO, o cliente con >=4 ticket IT ARRABBIATO nelle ultime 24h."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Il messaggio di sintesi del problema da inviare al manager.",
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Livello di urgenza da 1 (basso) a 4 (critico).",
                    },
                },
                "required": ["message", "priority"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": (
                "Cerca in data/policy.txt: sconti, budget, rimborsi, escalation, sentiment ARRABBIATO."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La chiave di ricerca (es. 'regole sconti', 'termini rimborso').",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_long_term_history",
            "description": (
                "Cerca nello storico audit (logs/activity.jsonl) i ticket passati dello stesso "
                "cliente. Usare PRIMA del triage finale se il messaggio identifica un nome cliente "
                "o azienda (es. 'sono Marco'). Se >=4 ticket IT con sentiment ARRABBIATO nelle "
                "ultime 24h: elevare priorità e invocare notify_manager con priority 4."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_nome": {
                        "type": "string",
                        "description": "Nome cliente o ragione sociale estratto dal messaggio.",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Finestra temporale in ore (default 24).",
                    },
                },
                "required": ["cliente_nome"],
            },
        },
    },
]
