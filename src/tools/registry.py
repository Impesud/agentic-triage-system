from tools.logger import search_long_term_history_sql
from tools.office_tools import notify_manager, search_policy
from tools.security_tools import isolate_account, verify_sender_identity

TOOL_MAP = {
    "notify_manager": notify_manager,
    "search_policy": search_policy,
    "search_long_term_history": search_long_term_history_sql,
    "isolate_account": isolate_account,
    "verify_sender_identity": verify_sender_identity,
}

TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "notify_manager",
            "description": (
                "Invia escalation immediata al manager di turno. Obbligatorio per "
                "richieste SALES con budget dichiarato superiore a 10.000€, sentiment "
                "ARRABBIATO, ransomware, anomalie login critiche, o cliente con >=4 ticket "
                "IT ARRABBIATO nelle ultime 24h."
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
                "Cerca in data/policy.txt tramite similarità semantica (RAG): sconti, budget, "
                "rimborsi, recesso, escalation, playbook SOC (phishing, esfiltrazione, ransomware, "
                "smarrimento dispositivi, whaling). Usa sinonimi concettuali."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La chiave di ricerca semantica sul tipo di incidente.",
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
                "Cerca nello storico SQLite ticket passati ed eventi access_events del cliente. "
                "Usare PRIMA del triage se il messaggio identifica un nome (es. Luca Verdi). "
                "Include anomalie login (Singapore, tentativi falliti) se presenti nel DB."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_nome": {
                        "type": "string",
                        "description": "Nome completo cliente (es. 'Luca Verdi', 'Matteo Neri').",
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
    {
        "type": "function",
        "function": {
            "name": "isolate_account",
            "description": (
                "Isola un account AD compromesso o a rischio. Obbligatorio dopo phishing con "
                "credenziali inserite, anomalie login confermate, o smarrimento dispositivo con "
                "sessioni VPN/chiavi produzione attive."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Account AD (es. luca.verdi@impesud.it).",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Motivo sintetico dell'isolamento.",
                    },
                },
                "required": ["account_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_sender_identity",
            "description": (
                "Verifica dichiarazione di ruolo elevato (CEO, manager) contro registro "
                "authorized_identities. Obbligatorio prima di qualsiasi richiesta di modifiche "
                "AD o bypass controlli di sicurezza via chat."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claimed_name": {
                        "type": "string",
                        "description": "Nome o titolo dichiarato dal mittente.",
                    },
                    "claimed_role": {
                        "type": "string",
                        "description": "Ruolo dichiarato (es. CEO).",
                    },
                },
                "required": ["claimed_name", "claimed_role"],
            },
        },
    },
]
