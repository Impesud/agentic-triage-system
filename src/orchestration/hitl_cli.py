"""CLI operatore HITL — Lezione 19."""

from __future__ import annotations

import argparse
import sys

from orchestration.hitl_pipeline import approve_session, reject_session
from orchestration.hitl_store import list_pending_states
from tools.logger import init_db


def cmd_list(_args: argparse.Namespace) -> int:
    init_db()
    pending = list_pending_states(limit=50)
    if not pending:
        print("Nessuna sessione in PENDING_APPROVAL.")
        return 0
    print(f"{'session_id':<22} {'tool':<18} {'status':<18} excerpt")
    print("-" * 72)
    for row in pending:
        print(
            f"{row.session_id:<22} {row.pending_tool:<18} {row.status:<18} "
            f"{row.user_input_excerpt[:40]}"
        )
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    init_db()
    try:
        output = approve_session(args.session_id, args.operator)
    except ValueError as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1
    print(f"APPROVED session_id={args.session_id}")
    print(f"Tool output: {output[:200]}")
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    init_db()
    try:
        message = reject_session(
            args.session_id,
            args.operator,
            reason=args.reason or "",
        )
    except ValueError as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1
    print(message)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Operatore HITL — approvazione azioni critiche (Lezione 19)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="Elenco sessioni PENDING_APPROVAL")

    approve = sub.add_parser("approve", help="Approva ed esegue il tool pendente")
    approve.add_argument("session_id", help="ID sessione HITL")
    approve.add_argument("--operator", required=True, help="Identificativo operatore")

    reject = sub.add_parser("reject", help="Rifiuta la sessione pendente")
    reject.add_argument("session_id", help="ID sessione HITL")
    reject.add_argument("--operator", required=True, help="Identificativo operatore")
    reject.add_argument("--reason", default="", help="Motivo del rifiuto")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "approve":
        return cmd_approve(args)
    if args.command == "reject":
        return cmd_reject(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
