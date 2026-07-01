"""Prompt di sistema per agenti specializzati (Lezione 16)."""

from prompts.agents.security_resolver import build_resolver_system_message
from prompts.agents.triage_analyst import build_analyst_system_message

__all__ = ["build_analyst_system_message", "build_resolver_system_message"]
