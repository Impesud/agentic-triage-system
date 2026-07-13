"""Test CLI HITL — Lezione 19."""

import pytest

from errors import HitlApprovalRequired
from orchestration.hitl_breakpoints import HitlPauseContext
from orchestration.hitl_cli import build_parser, main
from orchestration.hitl_pipeline import invoke_critical_tool_with_hitl
from orchestration.hitl_store import get_ticket_state, list_pending_states
from orchestration.pipeline_cache import PipelineContextCache
from orchestration.tool_policy_gate import ToolPolicyContext
from tools.registry import TOOL_MAP


def test_build_parser_has_subcommands():
    parser = build_parser()
    assert parser.parse_args(["list"]).command == "list"
    args = parser.parse_args(["approve", "hitl-1", "--operator", "op"])
    assert args.command == "approve"
    assert args.session_id == "hitl-1"
    assert args.operator == "op"
    args_rej = parser.parse_args(["reject", "hitl-2", "--operator", "op", "--reason", "no"])
    assert args_rej.command == "reject"
    assert args_rej.reason == "no"


def test_main_list_empty(tmp_path, monkeypatch, capsys):
    import paths as paths_module

    db = tmp_path / "triage.db"
    monkeypatch.setattr(paths_module, "TRIAGE_DB_PATH", db)
    from tools.logger import init_db

    init_db()
    assert main(["list"]) == 0
    assert "Nessuna sessione" in capsys.readouterr().out


def test_main_approve_command(tmp_path, monkeypatch, capsys):
    import paths as paths_module

    db = tmp_path / "triage.db"
    monkeypatch.setattr(paths_module, "TRIAGE_DB_PATH", db)
    from tools.logger import init_db

    init_db()
    cache = PipelineContextCache()
    cache.policy_by_query["test"] = "[RAG] policy ok"
    ctx = ToolPolicyContext(cache=cache, pipeline_categoria="SECURITY", enable_hitl=True)
    session_id = "hitl-cli-approve"
    with pytest.raises(HitlApprovalRequired):
        invoke_critical_tool_with_hitl(
            "isolate_account",
            {"account_name": "ACC", "reason": "cli test"},
            TOOL_MAP["isolate_account"],
            ctx,
            pause_ctx=HitlPauseContext(
                session_id=session_id,
                stm_messages=[{"role": "user", "content": "cli"}],
                user_input_excerpt="cli",
            ),
            db_path=str(db),
        )

    assert main(["approve", session_id, "--operator", "cli.op"]) == 0
    out = capsys.readouterr().out
    assert "APPROVED" in out
    record = get_ticket_state(session_id, db_path=str(db))
    assert record is not None
    assert record.status == "RESUMED"
    assert list_pending_states(db_path=str(db)) == []
