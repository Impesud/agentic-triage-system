"""Test HITL store SQLite — Lezione 19."""

import sqlite3

from orchestration.hitl_store import (
    get_ticket_state,
    init_hitl_tables,
    list_pending_states,
    save_ticket_state,
    update_ticket_state_status,
)


def test_save_and_load_pending(tmp_path):
    db = tmp_path / "hitl.db"
    init_hitl_tables(str(db))
    save_ticket_state(
        session_id="hitl-test-1",
        status="PENDING_APPROVAL",
        breakpoint_stage="pre_critical_tool",
        pending_tool="isolate_account",
        pending_args={"account_name": "A", "reason": "B"},
        stm_messages=[{"role": "user", "content": "ticket"}],
        pipeline_context={"pipeline_categoria": "SECURITY"},
        user_input_excerpt="ticket test",
        db_path=str(db),
    )
    record = get_ticket_state("hitl-test-1", db_path=str(db))
    assert record is not None
    assert record.status == "PENDING_APPROVAL"
    assert record.pending_tool == "isolate_account"
    pending = list_pending_states(db_path=str(db))
    assert len(pending) == 1
    assert pending[0].session_id == "hitl-test-1"


def test_update_status(tmp_path):
    db = tmp_path / "hitl.db"
    save_ticket_state(
        session_id="hitl-test-2",
        status="PENDING_APPROVAL",
        breakpoint_stage="pre_critical_tool",
        pending_tool="notify_manager",
        pending_args={"message": "m", "priority": 4},
        stm_messages=[],
        user_input_excerpt="x",
        db_path=str(db),
    )
    assert update_ticket_state_status(
        "hitl-test-2", status="RESUMED", resolved_by="op", db_path=str(db)
    )
    record = get_ticket_state("hitl-test-2", db_path=str(db))
    assert record is not None
    assert record.status == "RESUMED"
    assert record.resolved_by == "op"


def test_unique_session_id(tmp_path):
    db = tmp_path / "hitl.db"
    init_hitl_tables(str(db))
    kwargs = dict(
        status="PENDING_APPROVAL",
        breakpoint_stage="pre_critical_tool",
        pending_tool="isolate_account",
        pending_args={},
        stm_messages=[],
        user_input_excerpt="x",
        db_path=str(db),
    )
    save_ticket_state(session_id="dup", **kwargs)
    try:
        save_ticket_state(session_id="dup", **kwargs)
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    assert raised


def test_delete_ticket_state_idempotent(tmp_path):
    db = tmp_path / "hitl.db"
    kwargs = dict(
        status="PENDING_APPROVAL",
        breakpoint_stage="pre_critical_tool",
        pending_tool="isolate_account",
        pending_args={},
        stm_messages=[],
        user_input_excerpt="x",
        db_path=str(db),
    )
    save_ticket_state(session_id="dup", **kwargs)
    from orchestration.hitl_store import delete_ticket_state

    assert delete_ticket_state("dup", db_path=str(db)) is True
    assert delete_ticket_state("dup", db_path=str(db)) is False
    assert get_ticket_state("dup", db_path=str(db)) is None
