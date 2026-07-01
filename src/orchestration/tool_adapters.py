"""Adapter tool verso CrewAI e AutoGen (Lezione 16)."""

from __future__ import annotations

from autogen_core.tools import FunctionTool
from crewai.tools import tool

from tools.registry import TOOL_MAP, TOOLS_DEFINITION

_TOOL_DESCRIPTIONS: dict[str, str] = {
    entry["function"]["name"]: entry["function"]["description"]
    for entry in TOOLS_DEFINITION
}


def _tool_names_for_agent(names: tuple[str, ...]) -> None:
    unknown = set(names) - set(TOOL_MAP)
    if unknown:
        raise ValueError(f"Tool sconosciuti: {sorted(unknown)}")


def _crew_search_long_term_history() -> object:
    description = _TOOL_DESCRIPTIONS["search_long_term_history"]

    @tool("search_long_term_history")
    def search_long_term_history(cliente_nome: str, hours: int = 24) -> str:
        """Cerca nello storico SQLite i ticket passati del cliente."""
        return TOOL_MAP["search_long_term_history"](cliente_nome=cliente_nome, hours=hours)

    search_long_term_history.description = description  # type: ignore[attr-defined]
    return search_long_term_history


def _crew_search_policy() -> object:
    description = _TOOL_DESCRIPTIONS["search_policy"]

    @tool("search_policy")
    def search_policy(query: str) -> str:
        """Cerca in policy.txt tramite RAG semantica."""
        return TOOL_MAP["search_policy"](query=query)

    search_policy.description = description  # type: ignore[attr-defined]
    return search_policy


def _crew_notify_manager() -> object:
    description = _TOOL_DESCRIPTIONS["notify_manager"]

    @tool("notify_manager")
    def notify_manager(message: str, priority: int) -> str:
        """Invia escalation al manager di turno."""
        return TOOL_MAP["notify_manager"](message=message, priority=priority)

    notify_manager.description = description  # type: ignore[attr-defined]
    return notify_manager


_CREW_TOOL_BUILDERS = {
    "search_long_term_history": _crew_search_long_term_history,
    "search_policy": _crew_search_policy,
    "notify_manager": _crew_notify_manager,
}


def make_crewai_tools(tool_names: tuple[str, ...]) -> list[object]:
    """Crea tool CrewAI che delegano a TOOL_MAP."""
    _tool_names_for_agent(tool_names)
    return [_CREW_TOOL_BUILDERS[name]() for name in tool_names]


def make_autogen_tools(tool_names: tuple[str, ...]) -> list[FunctionTool]:
    """Crea FunctionTool AutoGen che delegano a TOOL_MAP."""
    _tool_names_for_agent(tool_names)
    return [
        FunctionTool(
            TOOL_MAP[name],
            description=_TOOL_DESCRIPTIONS.get(name, name),
            name=name,
        )
        for name in tool_names
    ]
