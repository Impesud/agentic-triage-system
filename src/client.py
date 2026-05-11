from pathlib import Path

from dotenv import dotenv_values
from openai import OpenAI

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _openai_api_key_from_dotenv() -> str | None:
    """Legge OPENAI_API_KEY solo dal file .env (non da os.environ)."""
    values = dotenv_values(_ENV_PATH, interpolate=False)
    raw = values.get("OPENAI_API_KEY")
    if raw is None:
        return None
    key = str(raw).strip()
    return key or None


# Inizializzazione client OpenAI
def get_client() -> OpenAI:
    """
    Crea e restituisce un client OpenAI usando la API key definita nel file .env in root repo.
    """
    api_key = _openai_api_key_from_dotenv()

    if not api_key:
        raise ValueError(f'API key non trovata in "{_ENV_PATH}". Imposta OPENAI_API_KEY nel file.')

    return OpenAI(api_key=api_key)


def call_llm(prompt: str) -> str:
    """
    Invia un prompt al modello e restituisce l'output testuale.

    Requisiti:
    - output deterministico
    - nessun parsing qui (solo testo)
    """

    client = get_client()

    response = client.chat.completions.create(
        model="gpt-4.1-mini",  # modello leggero e stabile
        temperature=0,  # determinismo massimo
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError("Risposta vuota dal modello")

    return content.strip()
