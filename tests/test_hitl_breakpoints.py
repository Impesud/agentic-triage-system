"""Test HITL Breakpoints — Lezione 19."""

from orchestration.hitl_breakpoints import is_hitl_breakpoint


def test_isolate_account_always_breakpoint():
    assert is_hitl_breakpoint("isolate_account", {"account_name": "x", "reason": "y"})


def test_notify_priority_3_not_breakpoint():
    assert not is_hitl_breakpoint("notify_manager", {"message": "m", "priority": 3})


def test_notify_priority_4_is_breakpoint():
    assert is_hitl_breakpoint("notify_manager", {"message": "m", "priority": 4})


def test_other_tools_not_breakpoint():
    assert not is_hitl_breakpoint("search_policy", {"query": "q"})
