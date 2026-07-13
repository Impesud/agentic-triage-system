"""Test CLI HITL — Lezione 19."""

from orchestration.hitl_cli import build_parser


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
