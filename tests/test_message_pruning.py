"""Test Message Pruning — Lezione 17."""

from orchestration.message_pruning import (
    compact_tool_observation,
    compact_tool_output,
    estimate_conversation_tokens,
    estimate_tokens,
    prune_conversation,
)


def test_estimate_tokens_monotonic():
    assert estimate_tokens("a") < estimate_tokens("a" * 100)


def test_prune_preserves_system_and_user():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "ticket"},
        {"role": "tool", "name": "search_policy", "content": "x" * 500},
    ]
    pruned, saved = prune_conversation(messages, keep_last_tool_results=0)
    assert pruned[0]["content"] == "sys"
    assert pruned[1]["content"] == "ticket"
    assert "[PRUNED]" in pruned[2]["content"]
    assert saved > 0


def test_prune_drops_old_tool_observations():
    long_a = "A" * 300
    long_b = "B" * 300
    messages = [
        {"role": "system", "content": "s"},
        {"role": "tool", "name": "search_policy", "content": long_a},
        {"role": "tool", "name": "search_policy", "content": long_b},
    ]
    pruned, _ = prune_conversation(messages, keep_last_tool_results=1)
    assert pruned[-1]["content"] == long_b
    assert "[PRUNED]" in pruned[1]["content"]


def test_compact_tool_output_truncates():
    out = compact_tool_output("z" * 1000, max_chars=100)
    assert "[COMPACT]" in out
    assert len(out) < 1000


def test_compact_tool_observation_short_unchanged():
    text = "short"
    assert compact_tool_observation("search_policy", text) == text


def test_estimate_conversation_tokens_sums():
    messages = [
        {"role": "user", "content": "abcd"},
        {"role": "tool", "content": "efgh"},
    ]
    assert estimate_conversation_tokens(messages) == estimate_tokens("abcd") + estimate_tokens("efgh")
