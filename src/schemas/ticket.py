from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Category = Literal["IT", "BILLING", "SALES", "SECURITY"]
Priority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
TicketStatus = Literal["OPEN", "TRIAGED"]

_TRIAGED_REQUIRED = ("categoria", "priorita", "analisi_problema", "riassunto_breve")


def _non_empty_str(value: str, field_label: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_label} non può essere vuoto")
    return value.strip()


class TriageResult(BaseModel):
    """Output strutturato dell'LLM (Parte 1)."""

    analisi_problema: str = Field(
        ...,
        description="Ragionamento CoT strutturato prima della classificazione",
    )
    categoria: Category
    priorita: Priority
    riassunto_breve: str
    messaggio_originale: str

    @field_validator("analisi_problema")
    @classmethod
    def validate_analisi(cls, value: str) -> str:
        return _non_empty_str(value, "L'analisi del problema")

    @field_validator("riassunto_breve")
    @classmethod
    def validate_riassunto_length(cls, value: str) -> str:
        word_count = len(value.strip().split())
        if word_count > 15:
            raise ValueError(
                f"Il riassunto supera il limite di 15 parole ({word_count})"
            )
        return value

    @field_validator("messaggio_originale")
    @classmethod
    def validate_messaggio(cls, value: str) -> str:
        return _non_empty_str(value, "Il messaggio originale")


class Ticket(BaseModel):
    """Ticket persistente con ciclo di vita (Parte 2)."""

    id: int
    status: TicketStatus
    messaggio_originale: str
    analisi_problema: str | None = None
    categoria: Category | None = None
    priorita: Priority | None = None
    riassunto_breve: str | None = None
    team: str | None = None

    @field_validator("messaggio_originale")
    @classmethod
    def validate_messaggio(cls, value: str) -> str:
        return _non_empty_str(value, "Il messaggio originale")

    @model_validator(mode="after")
    def validate_triaged_fields(self) -> "Ticket":
        if self.status != "TRIAGED":
            return self

        missing = [
            name
            for name in _TRIAGED_REQUIRED
            if getattr(self, name) in (None, "")
        ]
        if missing:
            raise ValueError(
                f"Ticket TRIAGED incompleto: campi mancanti {', '.join(missing)}"
            )
        return self
