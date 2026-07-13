"""Guardrail API key per demo live (Lezione 17)."""

from __future__ import annotations

from client import _openai_api_key_from_dotenv

_LLM_SCENARIOS = frozenset({"l16a", "l16b", "l17a", "l17b", "all"})


def has_openai_api_key() -> bool:
    return bool(_openai_api_key_from_dotenv())


def require_api_key_for_scenario(scenario: str) -> bool:
    """
    Verifica presenza OPENAI_API_KEY per scenari che chiamano l'LLM.

    Ritorna True se la demo può procedere, False se va saltata.
    """
    if scenario not in _LLM_SCENARIOS:
        return True
    if has_openai_api_key():
        return True
    print(
        "\n[SKIP] OPENAI_API_KEY assente in .env — "
        f"scenario '{scenario}' richiede API live. "
        "Esegui solo l15, l18a, l18b, l19a, l19b o configura .env.\n"
    )
    return False


def skip_llm_block(label: str) -> bool:
    """Messaggio uniforme quando un blocco LLM viene saltato in --scenario all."""
    if has_openai_api_key():
        return False
    print(f"\n[SKIP] {label} — API key mancante.\n")
    return True
