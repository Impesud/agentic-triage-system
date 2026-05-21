import pytest

from tools.enrichment import enrich_priority


def test_urgente_raises_to_high(triaged_ticket):
    ticket = triaged_ticket(priorita="LOW", messaggio="È urgente, la mia email è bloccata")
    assert enrich_priority(ticket).priorita == "HIGH"


def test_bloccato_raises_to_high(triaged_ticket):
    ticket = triaged_ticket(priorita="MEDIUM", messaggio="Account bloccato")
    assert enrich_priority(ticket).priorita == "HIGH"


def test_bloccata_raises_to_high(triaged_ticket):
    ticket = triaged_ticket(priorita="LOW", messaggio="La email è bloccata")
    assert enrich_priority(ticket).priorita == "HIGH"


def test_subito_raises_to_at_least_medium(triaged_ticket):
    ticket = triaged_ticket(priorita="LOW", messaggio="Serve subito una risposta")
    assert enrich_priority(ticket).priorita == "MEDIUM"


def test_non_funziona_raises_to_at_least_medium(triaged_ticket):
    ticket = triaged_ticket(priorita="LOW", messaggio="Il portale non funziona")
    assert enrich_priority(ticket).priorita == "MEDIUM"


def test_enrich_without_priorita_raises():
    from schemas.ticket import Ticket

    ticket = Ticket(id=1, status="OPEN", messaggio_originale="x", categoria="IT")
    with pytest.raises(ValueError, match="priorità"):
        enrich_priority(ticket)
