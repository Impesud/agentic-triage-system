"""Test tool policy gate — Lezione 18."""

from orchestration.pipeline_cache import PipelineContextCache
from orchestration.tool_policy_gate import (
    ToolPolicyContext,
    check_notify_manager,
    invoke_notify_manager,
)


def test_notify_low_priority_always_allowed():
    ctx = ToolPolicyContext()
    verdict = check_notify_manager("info", 2, ctx)
    assert verdict.allowed


def test_notify_high_priority_denied_without_policy():
    ctx = ToolPolicyContext()
    verdict = check_notify_manager("critico", 4, ctx)
    assert not verdict.allowed


def test_notify_high_priority_allowed_with_cache():
    cache = PipelineContextCache()
    cache.policy_by_query["test"] = "policy excerpt"
    ctx = ToolPolicyContext(cache=cache)
    verdict = check_notify_manager("escalation", 4, ctx)
    assert verdict.allowed


def test_invoke_notify_manager_returns_denial_message():
    ctx = ToolPolicyContext()

    def fn(**kwargs):
        return "ok"

    out = invoke_notify_manager("msg", 4, fn, ctx)
    assert "[SECURITY DENIED]" in out
