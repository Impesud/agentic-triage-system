import chromadb
import pytest

from rag.chroma_store import reset_policy_store, set_chroma_client
from schemas.ticket import Ticket

ANALISI_FIXTURE = (
    "1. Problema: test. 2. Contesto: test. "
    "3. Categoria: IT. 4. Priorità: HIGH."
)


@pytest.fixture
def triaged_ticket():
    """Factory per ticket TRIAGED validi nei test."""

    def _make(
        *,
        ticket_id: int = 1,
        messaggio: str = "x",
        categoria: str = "IT",
        priorita: str = "HIGH",
        team: str | None = None,
    ) -> Ticket:
        return Ticket(
            id=ticket_id,
            status="TRIAGED",
            messaggio_originale=messaggio,
            analisi_problema=ANALISI_FIXTURE,
            categoria=categoria,
            priorita=priorita,
            riassunto_breve="test",
            team=team,
        )

    return _make


@pytest.fixture(autouse=True)
def isolated_chroma_store():
    """ChromaDB in-memory per tutti i test (no data/chroma/ condivisa)."""
    reset_policy_store()
    set_chroma_client(chromadb.EphemeralClient())
    yield
    reset_policy_store()
    set_chroma_client(None)


@pytest.fixture(autouse=True)
def isolated_tickets_file(tmp_path, monkeypatch):
    tickets_file = tmp_path / "tickets.jsonl"
    monkeypatch.setattr("storage.store.TICKETS_PATH", tickets_file)
    yield tickets_file
