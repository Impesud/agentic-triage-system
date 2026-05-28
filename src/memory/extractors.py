"""Estrazione metadati per long-term memory dai messaggi ticket."""

import re

_SENTIMENT_ARRABBIATO_TERMS = (
    "avvocato",
    "denuncio",
    "querela",
    "inaccettabile",
    "deluso",
    "furioso",
)

_CLIENTE_PATTERNS = [
    re.compile(r"\bsono\s+l['']?(?:ing\.|dr\.|dott\.)\s+([A-Za-zÀ-ÿ][\wÀ-ÿ.-]*)", re.I),
    re.compile(r"\bsono\s+([A-Za-zÀ-ÿ][\wÀ-ÿ.-]*)", re.I),
    re.compile(r"\bsiamo\s+la\s+società\s+([A-Za-zÀ-ÿ][\wÀ-ÿ\s&.-]+)", re.I),
    re.compile(r"\bsocietà\s+([A-Za-zÀ-ÿ][\wÀ-ÿ\s&.-]+)", re.I),
]


def extract_cliente_nome(text: str) -> str | None:
    for pattern in _CLIENTE_PATTERNS:
        match = pattern.search(text)
        if match:
            name = match.group(1).strip().rstrip(".,;")
            if len(name) >= 2:
                return name
    return None


def detect_sentiment_label(text: str) -> str:
    lower = text.lower()
    caps_words = sum(
        1 for word in text.split() if len(word) > 3 and word.isalpha() and word.isupper()
    )
    angry_signals = sum(term in lower for term in _SENTIMENT_ARRABBIATO_TERMS)
    angry_signals += int(caps_words >= 2)
    angry_signals += int("estremamente" in lower and "deluso" in lower)
    return "ARRABBIATO" if angry_signals >= 2 else "NEUTRO"
