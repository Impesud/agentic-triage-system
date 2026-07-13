"""Test HITL pipeline — Lezione 19."""

import json
from unittest.mock import MagicMock, patch

import pytest

from errors import HitlApprovalRequired
from orchestration.hitl_breakpoints import HitlPauseContext
from orchestration.hitl_pipeline import (
    approve_session,
    invoke_critical_tool_with_hitl,
    reject_session,
    resume_session,
)
from orchestration.hitl_store import get_ticket_state, list_pending_states
from orchestration.pipeline_cache import PipelineContextCache
from orchestration.tool_policy_gate import ToolPolicyContext
from tools.registry import TOOL_MAP


def _completion(content=None, tool_calls=None):
    msg = MagicMock(tool_calls=tool_calls, content=content)
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    return resp


def _ctx_with_policy() -> ToolPolicyContext:
    cache = PipelineContextCache()
    cache.policy_by_query["test"] = "[RAG] policy ok"
    return ToolPolicyContext(cache=cache, pipeline_categoria="SECURITY", enable_hitl=True)


def test_pause_on_isolate_account(tmp_path):
    db = tmp_path / "hitl.db"
    ctx = _ctx_with_policy()
    pause_ctx = HitlPauseContext(
        session_id="hitl-pause-1",
        stm_messages=[{"role": "user", "content": "soc"}],
        user_input_excerpt="soc incident",
    )
    with pytest.raises(HitlApprovalRequired) as exc_info:
        invoke_critical_tool_with_hitl(
            "isolate_account",
            {"account_name": "FIN-1", "reason": "malware"},
            TOOL_MAP["isolate_account"],
            ctx,
            pause_ctx=pause_ctx,
            db_path=str(db),
        )
    assert exc_info.value.session_id == "hitl-pause-1"
    record = get_ticket_state("hitl-pause-1", db_path=str(db))
    assert record is not None
    assert record.status == "PENDING_APPROVAL"


def test_notify_p4_pauses(tmp_path):
    db = tmp_path / "hitl.db"
    ctx = _ctx_with_policy()
    with pytest.raises(HitlApprovalRequired):
        invoke_critical_tool_with_hitl(
            "notify_manager",
            {"message": "mass escalation", "priority": 4},
            TOOL_MAP["notify_manager"],
            ctx,
            pause_ctx=HitlPauseContext(
                session_id="hitl-pause-2",
                stm_messages=[],
                user_input_excerpt="escalation",
            ),
            db_path=str(db),
        )


def test_notify_p3_executes_without_pause():
    ctx = _ctx_with_policy()
    out = invoke_critical_tool_with_hitl(
        "notify_manager",
        {"message": "standard", "priority": 3},
        TOOL_MAP["notify_manager"],
        ctx,
        pause_ctx=HitlPauseContext(session_id="x", stm_messages=[], user_input_excerpt=""),
    )
    assert "Notifica inviata" in out or "manager" in out.lower()


def test_approve_resumes_and_executes_tool(tmp_path):
    db = tmp_path / "hitl.db"
    ctx = _ctx_with_policy()
    session_id = "hitl-approve-1"
    with pytest.raises(HitlApprovalRequired):
        invoke_critical_tool_with_hitl(
            "isolate_account",
            {"account_name": "ACC", "reason": "test"},
            TOOL_MAP["isolate_account"],
            ctx,
            pause_ctx=HitlPauseContext(
                session_id=session_id,
                stm_messages=[{"role": "user", "content": "t"}],
                user_input_excerpt="t",
            ),
            db_path=str(db),
        )
    output = approve_session(session_id, "operator.test", db_path=str(db))
    assert output
    record = get_ticket_state(session_id, db_path=str(db))
    assert record is not None
    assert record.status == "RESUMED"


def test_reject_does_not_execute_tool(tmp_path):
    db = tmp_path / "hitl.db"
    ctx = _ctx_with_policy()
    session_id = "hitl-reject-1"
    with pytest.raises(HitlApprovalRequired):
        invoke_critical_tool_with_hitl(
            "isolate_account",
            {"account_name": "ACC", "reason": "test"},
            TOOL_MAP["isolate_account"],
            ctx,
            pause_ctx=HitlPauseContext(
                session_id=session_id,
                stm_messages=[],
                user_input_excerpt="t",
            ),
            db_path=str(db),
        )
    msg = reject_session(session_id, "operator.test", reason="no", db_path=str(db))
    assert "[HITL REJECTED]" in msg
    record = get_ticket_state(session_id, db_path=str(db))
    assert record is not None
    assert record.status == "REJECTED"
    assert list_pending_states(db_path=str(db)) == []


def test_pause_persists_react_resume_metadata(tmp_path):
    db = tmp_path / "hitl.db"
    ctx = _ctx_with_policy()
    react_session = "react-meta-1"
    with pytest.raises(HitlApprovalRequired):
        invoke_critical_tool_with_hitl(
            "isolate_account",
            {"account_name": "ACC", "reason": "test"},
            TOOL_MAP["isolate_account"],
            ctx,
            pause_ctx=HitlPauseContext(
                session_id="hitl-meta-1",
                stm_messages=[{"role": "user", "content": "t"}],
                user_input_excerpt="ticket test",
                react_step=2,
                tool_call_id="tc-1",
                react_session_id=react_session,
                user_input="ticket test completo",
                manuale="Manuale IT",
                max_steps=4,
            ),
            db_path=str(db),
        )
    record = get_ticket_state("hitl-meta-1", db_path=str(db))
    assert record is not None
    pipeline = json.loads(record.pipeline_context_json or "{}")
    react_resume = pipeline["react_resume"]
    assert react_resume["react_session_id"] == react_session
    assert react_resume["from_step"] == 2
    assert react_resume["tool_call_id"] == "tc-1"
    assert react_resume["user_input"] == "ticket test completo"


def test_resume_session_alias():
    assert resume_session is approve_session


def test_approve_skips_react_resume_when_disabled(tmp_path):
    db = tmp_path / "hitl.db"
    ctx = _ctx_with_policy()
    session_id = "hitl-no-resume"
    with pytest.raises(HitlApprovalRequired):
        invoke_critical_tool_with_hitl(
            "isolate_account",
            {"account_name": "ACC", "reason": "test"},
            TOOL_MAP["isolate_account"],
            ctx,
            pause_ctx=HitlPauseContext(
                session_id=session_id,
                stm_messages=[],
                user_input_excerpt="t",
                react_session_id="react-should-not-run",
            ),
            db_path=str(db),
        )
    with patch("logic.react_triage_resume") as mock_resume:
        approve_session(session_id, "op", db_path=str(db), resume_react=False)
        mock_resume.assert_not_called()


@patch("logic.get_client")
def test_approve_resumes_react_loop(mock_get_client, tmp_path):
    from logic import _SHORT_TERM_STORE

    db = tmp_path / "hitl.db"
    ctx = _ctx_with_policy()
    react_session = "react-hitl-resume-1"
    tool_call_id = "tc-isolate-1"
    stm = [
        {"role": "user", "content": "ransomware su FIN-042"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": "isolate_account",
                        "arguments": json.dumps(
                            {"account_name": "FIN-042", "reason": "Ransomware"}
                        ),
                    },
                }
            ],
        },
    ]
    hitl_session = "hitl-react-resume-1"
    with pytest.raises(HitlApprovalRequired):
        invoke_critical_tool_with_hitl(
            "isolate_account",
            {"account_name": "FIN-042", "reason": "Ransomware"},
            TOOL_MAP["isolate_account"],
            ctx,
            pause_ctx=HitlPauseContext(
                session_id=hitl_session,
                stm_messages=stm,
                user_input_excerpt="ransomware",
                react_step=1,
                tool_call_id=tool_call_id,
                react_session_id=react_session,
                user_input="ransomware su FIN-042",
                manuale="Manuale IT",
                max_steps=4,
            ),
            db_path=str(db),
        )

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    final = (
        '{"analisi_problema":"1. P. 2. C. 3. SECURITY. 4. CRITICAL.",'
        '"categoria":"SECURITY","priorita":"CRITICAL","riassunto_breve":"Ransomware",'
        '"messaggio_originale":"ransomware su FIN-042"}'
    )
    mock_client.chat.completions.create.return_value = _completion(content=final)

    approve_session(hitl_session, "operator.test", db_path=str(db))

    assert mock_client.chat.completions.create.call_count == 1
    assert react_session in _SHORT_TERM_STORE
    record = get_ticket_state(hitl_session, db_path=str(db))
    assert record is not None
    assert record.status == "RESUMED"
