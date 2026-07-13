"""Breakpoint HITL deterministici — Lezione 19."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

HITL_NOTIFY_PRIORITY = 4


class BreakpointStage(str, Enum):
    PRE_CRITICAL_TOOL = "pre_critical_tool"


@dataclass
class HitlPauseContext:
    """Contesto runtime per serializzare una pausa HITL."""

    session_id: str
    stm_messages: list[Any]
    user_input_excerpt: str
    react_step: int | None = None
    tool_call_id: str | None = None
    react_session_id: str | None = None
    user_input: str | None = None
    manuale: str | None = None
    max_steps: int | None = None
    enable_optimizations: bool = True
    enable_pruning: bool | None = None
    enable_cache: bool | None = None
    enable_compact_output: bool | None = None


@dataclass(frozen=True)
class CriticalAction:
    tool_name: str
    args: dict[str, Any]
    stage: BreakpointStage = BreakpointStage.PRE_CRITICAL_TOOL


def is_hitl_breakpoint(tool_name: str, args: dict[str, Any]) -> bool:
    """True se l'azione richiede approvazione umana prima dell'esecuzione."""
    if tool_name == "isolate_account":
        return True
    if tool_name == "notify_manager":
        priority = int(args.get("priority", 1))
        return priority >= HITL_NOTIFY_PRIORITY
    return False
