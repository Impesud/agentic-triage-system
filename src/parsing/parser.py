import json
import re
from typing import Any

from pydantic import ValidationError

from schemas.ticket import TriageResult


def _extract_json_block(text: str) -> str:
    """
    Estrae il primo oggetto JSON bilanciato da una stringa.
    Gestisce testo extra e blocchi markdown ```json.
    """
    text = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()
    start = text.find("{")
    if start == -1:
        raise ValueError("Nessun JSON trovato nella risposta del modello")

    depth = 0
    for index, char in enumerate(text[start:], start=start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise ValueError("JSON non bilanciato nella risposta del modello")


def _safe_json_load(json_str: str) -> dict[str, Any]:
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON non valido: {e}") from e


def parse_llm_output(raw_output: str) -> TriageResult:
    """Estrae JSON dalla risposta LLM e valida con TriageResult."""
    json_str = _extract_json_block(raw_output)
    data = _safe_json_load(json_str)

    try:
        return TriageResult(**data)
    except ValidationError as e:
        raise ValueError(f"Errore validazione TriageResult: {e}") from e
