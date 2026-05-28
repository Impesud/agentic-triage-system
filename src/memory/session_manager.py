"""Short-term memory: thread multi-turno per ticket_id (in-memory)."""


class SessionManager:
    def __init__(self) -> None:
        self._threads: dict[int, list[dict[str, str]]] = {}

    def get_messages(self, ticket_id: int) -> list[dict[str, str]]:
        return list(self._threads.get(ticket_id, []))

    def append(self, ticket_id: int, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError(f"Ruolo non valido: {role}")
        self._threads.setdefault(ticket_id, []).append({"role": role, "content": content})

    def clear(self, ticket_id: int) -> None:
        self._threads.pop(ticket_id, None)
