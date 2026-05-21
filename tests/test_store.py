import json

import pytest

from schemas.ticket import Ticket
from storage import store


def test_triaged_requires_analisi_problema():
    with pytest.raises(ValueError, match="analisi_problema"):
        Ticket(
            id=1,
            status="TRIAGED",
            messaggio_originale="help",
            categoria="IT",
            priorita="HIGH",
            riassunto_breve="Email bloccata",
        )


def test_next_ticket_id_starts_at_one():
    assert store.next_ticket_id() == 1


def test_save_ticket_append_jsonl():
    ticket = Ticket(id=1, status="OPEN", messaggio_originale="ciao")
    store.save_ticket(ticket)

    lines = store.TICKETS_PATH.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["status"] == "OPEN"


def test_current_state_is_last_snapshot():
    open_ticket = Ticket(id=1, status="OPEN", messaggio_originale="help")
    triaged_ticket = Ticket(
        id=1,
        status="TRIAGED",
        messaggio_originale="help",
        analisi_problema=(
            "1. Problema: email bloccata. 2. Contesto: accesso IT. "
            "3. Categoria: IT. 4. Priorità: HIGH."
        ),
        categoria="IT",
        priorita="HIGH",
        riassunto_breve="Email bloccata",
    )
    store.save_ticket(open_ticket)
    store.save_ticket(triaged_ticket)

    current = store.get_current_ticket(1)
    assert current["status"] == "TRIAGED"
    assert current["analisi_problema"]


def test_routed_snapshot_persists_team(triaged_ticket):
    from tools.router import assign_to_team

    ticket = triaged_ticket(categoria="IT")
    store.save_ticket(ticket)
    routed = assign_to_team(ticket)
    store.save_ticket(routed)

    current = store.get_current_ticket(1)
    assert current["team"] == "team_tecnico"
