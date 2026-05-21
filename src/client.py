from dotenv import dotenv_values
from openai import OpenAI

from paths import ENV_PATH


def _openai_api_key_from_dotenv() -> str | None:
    """Legge OPENAI_API_KEY solo dal file .env (non da os.environ)."""
    values = dotenv_values(ENV_PATH, interpolate=False)
    raw = values.get("OPENAI_API_KEY")
    if raw is None:
        return None
    key = str(raw).strip()
    return key or None


def get_client() -> OpenAI:
    """Client OpenAI con API key da .env in root repo."""
    api_key = _openai_api_key_from_dotenv()
    if not api_key:
        raise ValueError(
            f'API key non trovata in "{ENV_PATH}". Imposta OPENAI_API_KEY nel file.'
        )
    return OpenAI(api_key=api_key)


def call_llm(prompt: str) -> str:
    """Invia un prompt al modello e restituisce l'output testuale (temperature=0)."""
    response = get_client().chat.completions.create(
        model="gpt-4.1-mini",
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Risposta vuota dal modello")

    return content.strip()
