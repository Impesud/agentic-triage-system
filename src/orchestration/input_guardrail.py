"""Input Guardrail deterministico — Lezione 18."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class AttackVector(str, Enum):
    DIRECT_INJECTION = "direct_injection"
    POLICY_OVERRIDE = "policy_override"
    TOOL_HIJACK = "tool_hijack"
    LOG_SUPPRESSION = "log_suppression"
    ROLE_OVERRIDE = "role_override"


@dataclass(frozen=True)
class PatternMatch:
    pattern: str
    vector: AttackVector
    severity: Severity


@dataclass
class GuardrailResult:
    allowed: bool
    matches: list[PatternMatch] = field(default_factory=list)
    severity: Severity = "LOW"

    @property
    def highest_severity(self) -> Severity:
        order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        if not self.matches:
            return "LOW"
        return max(self.matches, key=lambda m: order[m.severity]).severity


ATTACK_PATTERNS: tuple[tuple[re.Pattern[str], AttackVector, Severity], ...] = (
    (re.compile(r"ignora\s+(le\s+)?(istruzioni|policy|regole)", re.I), AttackVector.POLICY_OVERRIDE, "CRITICAL"),
    (re.compile(r"ignore\s+(all\s+)?(previous\s+)?instructions", re.I), AttackVector.DIRECT_INJECTION, "CRITICAL"),
    (re.compile(r"dichiara\s+il\s+sistema\s+sicuro", re.I), AttackVector.POLICY_OVERRIDE, "HIGH"),
    (re.compile(r"esegui\s+il\s+tool", re.I), AttackVector.TOOL_HIJACK, "CRITICAL"),
    (re.compile(r"chiama\s+isolate_account", re.I), AttackVector.TOOL_HIJACK, "HIGH"),
    (re.compile(r"isolare?\s+l['\u2019]?utente\s+amministratore", re.I), AttackVector.TOOL_HIJACK, "CRITICAL"),
    (re.compile(r"non\s+loggare", re.I), AttackVector.LOG_SUPPRESSION, "HIGH"),
    (re.compile(r"nascondi\s+(le\s+)?tracce", re.I), AttackVector.LOG_SUPPRESSION, "HIGH"),
    (re.compile(r"sei\s+ora\s+un\s+assistente", re.I), AttackVector.ROLE_OVERRIDE, "HIGH"),
    (re.compile(r"system\s+prompt\s+override", re.I), AttackVector.ROLE_OVERRIDE, "MEDIUM"),
    (re.compile(r"rispondi\s+sempre\s+ok", re.I), AttackVector.DIRECT_INJECTION, "MEDIUM"),
)


def scan_ticket_input(text: str) -> GuardrailResult:
    """Analizza il testo del ticket alla ricerca di vettori di attacco noti."""
    if not text or not text.strip():
        return GuardrailResult(allowed=True)

    matches: list[PatternMatch] = []
    for pattern, vector, severity in ATTACK_PATTERNS:
        if pattern.search(text):
            matches.append(
                PatternMatch(
                    pattern=pattern.pattern,
                    vector=vector,
                    severity=severity,
                )
            )

    if matches:
        result = GuardrailResult(allowed=False, matches=matches)
        result.severity = result.highest_severity
        return result
    return GuardrailResult(allowed=True)


def input_excerpt(text: str, *, max_len: int = 200) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3] + "..."
