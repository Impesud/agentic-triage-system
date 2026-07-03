"""Cache per invocazione pipeline — evita embedding/query ridondanti (Lezione 17)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tools.logger import log_event


@dataclass
class PipelineContextCache:
    """
    Stato condiviso per una singola run di triage (non globale cross-request).

    Memorizza risultati tool già calcolati nella stessa pipeline.
    """

    policy_by_query: dict[str, str] = field(default_factory=dict)
    ltm_by_cliente: dict[str, str] = field(default_factory=dict)
    policy_hits: int = 0
    ltm_hits: int = 0

    def _log_hit(self, tool: str, key_preview: str) -> None:
        log_event(
            "embedding_cache_hit",
            {"tool": tool, "key_preview": key_preview[:120]},
        )

    def get_or_call_policy(self, query: str, fn: Callable[[str], str]) -> str:
        """Ritorna policy in cache o invoca fn(query) una sola volta per query."""
        normalized = query.strip().lower()
        if not normalized:
            return fn(query)

        cached = self.policy_by_query.get(normalized)
        if cached is not None:
            self.policy_hits += 1
            self._log_hit("search_policy", normalized)
            return cached

        result = fn(query)
        self.policy_by_query[normalized] = result
        return result

    def get_or_call_ltm(
        self,
        cliente: str,
        hours: int,
        fn: Callable[[str, int], str],
    ) -> str:
        """Cache LTM per coppia (cliente, hours)."""
        key = f"{cliente.strip().lower()}|{hours}"
        cached = self.ltm_by_cliente.get(key)
        if cached is not None:
            self.ltm_hits += 1
            self._log_hit("search_long_term_history", key)
            return cached

        result = fn(cliente, hours)
        self.ltm_by_cliente[key] = result
        return result

    def first_policy_excerpt(self) -> str | None:
        if not self.policy_by_query:
            return None
        return next(iter(self.policy_by_query.values()))

    def first_ltm_digest(self) -> str | None:
        if not self.ltm_by_cliente:
            return None
        return next(iter(self.ltm_by_cliente.values()))
