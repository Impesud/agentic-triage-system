"""Estrazione metadati per long-term memory dai messaggi ticket."""

import re

_SENTIMENT_ARRABBIATO_TERMS = (
    "avvocato",
    "denuncio",
    "querela",
    "inaccettabile",
    "deluso",
    "furioso",
    "panico",
    "accorrete",
)

_CLIENTE_PATTERNS = [
    # «Sono l'amministratore Luca Verdi» / «Sono l'ingegnere Matteo Neri» (Progetto 2)
    re.compile(
        r"\bsono\s+l['']?(?:amministratore|ingegnere|ing\.)\s+"
        r"([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)*)",
        re.I,
    ),
    re.compile(r"\bsono\s+l['']?(?:ing\.|dr\.|dott\.)\s+([A-Za-zÀ-ÿ][\wÀ-ÿ.-]*)", re.I),
    re.compile(r"\bsono\s+([A-Za-zÀ-ÿ][\wÀ-ÿ.-]*)", re.I),
    re.compile(r"\bsiamo\s+la\s+società\s+([A-Za-zÀ-ÿ][\wÀ-ÿ\s&.-]+)", re.I),
    re.compile(r"\bsocietà\s+([A-Za-zÀ-ÿ][\wÀ-ÿ\s&.-]+)", re.I),
]


def extract_cliente_nome(text: str) -> str | None:
    """
    Estrae il nome cliente o la ragione sociale dal messaggio.

    Gestisce pattern Progetto 2 con titolo professionale prima del nome
    (amministratore, ingegnere) oltre ai pattern base delle lezioni 9–14.
    """
    for pattern in _CLIENTE_PATTERNS:
        match = pattern.search(text)
        if match:
            name = match.group(1).strip().rstrip(".,;")
            if len(name) >= 2:
                return name
    return None


def detect_sentiment_label(text: str) -> str:
    """
    Classifica il sentiment del messaggio come ARRABBIATO o NEUTRO.

    Include segnali Progetto 2: panico, urgenza SOC (maiuscole), «accorrete».
    """
    lower = text.lower()
    caps_words = sum(
        1 for word in text.split() if len(word) > 3 and word.isalpha() and word.isupper()
    )
    angry_signals = sum(term in lower for term in _SENTIMENT_ARRABBIATO_TERMS)
    angry_signals += int(caps_words >= 2)
    angry_signals += int("estremamente" in lower and "deluso" in lower)
    angry_signals += int("panico" in lower and "totale" in lower)
    return "ARRABBIATO" if angry_signals >= 2 else "NEUTRO"
