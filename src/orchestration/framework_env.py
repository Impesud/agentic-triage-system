"""Bootstrap variabili d'ambiente per framework multi-agent (Lezione 16)."""

from __future__ import annotations

import os

from client import MODEL, _openai_api_key_from_dotenv


def ensure_framework_env() -> str:
    """
    CrewAI e AutoGen leggono OPENAI_API_KEY da os.environ.
    Il corso usa .env via client.py — sincronizziamo prima dell'orchestrazione.
    """
    api_key = _openai_api_key_from_dotenv()
    if not api_key:
        raise ValueError(
            'API key non trovata. Imposta OPENAI_API_KEY nel file .env in root repo.'
        )
    os.environ.setdefault("OPENAI_API_KEY", api_key)
    os.environ.setdefault("OPENAI_MODEL_NAME", MODEL)
    return api_key
