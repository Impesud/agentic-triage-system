"""Test compattazione prompt Resolver — Lezione 17."""

from orchestration.prompt_compression import compact_manuale_for_resolver
from prompts.agents.security_resolver import build_resolver_system_message

_LONG_MANUALE = "A" * 5000 + " regole budget escalation VIP"


def test_compact_manuale_returns_pointer():
    compact = compact_manuale_for_resolver(_LONG_MANUALE)
    assert "MANUALE IT" in compact
    assert "policy_excerpt" in compact
    assert "AAAA" not in compact


def test_build_resolver_compact_omits_full_manual():
    prompt = build_resolver_system_message(
        _LONG_MANUALE,
        handoff_context='{"policy_excerpt": "chunk policy"}',
        compact_manuale=True,
    )
    assert "AAAA" not in prompt
    assert "policy_excerpt" in prompt
