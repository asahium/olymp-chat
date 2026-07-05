#!/usr/bin/env python3
"""Admin CLI for the AIOI contest chat.

Examples:
    python manage.py generate-participants --count 50 --team-prefix team
    python manage.py list-participants
    python manage.py disable-participant p017
    python manage.py reset-quota p017
    python manage.py export-logs --output logs.jsonl
    python manage.py usage-summary
    python manage.py clear-sessions
"""
import argparse
import sys

from app import auth, database, logging_service, provisioning


def cmd_generate(args: argparse.Namespace) -> None:
    database.init_db()
    created = provisioning.generate_participants(args.count, args.team_prefix)
    print("participant_id,display_name,team_id,login_code")
    for p in created:
        print(f"{p['participant_id']},{p['display_name']},{p['team_id']},{p['login_code']}")


def cmd_list(args: argparse.Namespace) -> None:
    database.init_db()
    rows = database.list_participants()
    if not rows:
        print("(no participants)")
        return
    print(f"{'id':<8} {'active':<7} {'team':<12} {'code':<12} display_name")
    for p in rows:
        print(f"{p['participant_id']:<8} {bool(p['is_active'])!s:<7} "
              f"{(p['team_id'] or ''):<12} {p['login_code']:<12} {p['display_name']}")


def cmd_set_name(args: argparse.Namespace) -> None:
    database.init_db()
    # Resolve by participant_id, or fall back to login_code.
    pid = args.participant
    if not database.get_participant_by_id(pid):
        p = database.get_participant_by_code(pid)
        pid = p["participant_id"] if p else pid
    ok = database.set_display_name(pid, args.name)
    print(f"renamed {pid} -> {args.name}" if ok else f"unknown participant {args.participant}")


def _resolve_pid(ref: str) -> str:
    if database.get_participant_by_id(ref):
        return ref
    p = database.get_participant_by_code(ref)
    return p["participant_id"] if p else ref


def cmd_clear_logs(args: argparse.Namespace) -> None:
    database.init_db()
    pid = _resolve_pid(args.participant)
    n = database.delete_logs_for(pid)
    print(f"cleared {n} log row(s) for {pid}")


def cmd_disable(args: argparse.Namespace) -> None:
    database.init_db()
    ok = database.set_active(args.participant_id, False)
    print(f"disabled {args.participant_id}" if ok else f"unknown participant {args.participant_id}")


def cmd_reset_quota(args: argparse.Namespace) -> None:
    database.init_db()
    ok = database.reset_quota(args.participant_id)
    print(f"quota reset for {args.participant_id}" if ok else f"unknown participant {args.participant_id}")


def cmd_export_logs(args: argparse.Namespace) -> None:
    database.init_db()
    with open(args.output, "w", encoding="utf-8", newline="") as fp:
        if args.output.endswith(".csv"):
            n = logging_service.export_csv(fp)
        else:
            n = logging_service.export_jsonl(fp)
    print(f"exported {n} log rows to {args.output}")


def cmd_usage(args: argparse.Namespace) -> None:
    database.init_db()
    summary = logging_service.usage_summary()
    t = summary["totals"]
    print(f"{'participant':<14}{'requests':>10}{'prompt_tok':>12}{'compl_tok':>12}{'total_tok':>12}")
    for r in summary["per_participant"]:
        print(f"{r['participant_id']:<14}{r['requests']:>10}{r['prompt_tokens']:>12}"
              f"{r['completion_tokens']:>12}{r['total_tokens']:>12}")
    print("-" * 60)
    print(f"{'TOTAL':<14}{t['requests']:>10}{t['prompt_tokens']:>12}"
          f"{t['completion_tokens']:>12}{t['total_tokens']:>12}")


def cmd_clear_sessions(args: argparse.Namespace) -> None:
    database.init_db()
    auth.clear_all_sessions()
    print("all sessions invalidated; participants must log in again")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AIOI contest chat admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("generate-participants", help="create N participants")
    p.add_argument("--count", type=int, required=True)
    p.add_argument("--team-prefix", default="team")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("list-participants", help="list all participants")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("set-name", help="set a participant's display name (by id or code)")
    p.add_argument("participant", help="participant_id or login_code")
    p.add_argument("name")
    p.set_defaults(func=cmd_set_name)

    p = sub.add_parser("clear-logs", help="delete all chat logs for a participant (by id or code)")
    p.add_argument("participant", help="participant_id or login_code")
    p.set_defaults(func=cmd_clear_logs)

    p = sub.add_parser("disable-participant", help="disable a participant")
    p.add_argument("participant_id")
    p.set_defaults(func=cmd_disable)

    p = sub.add_parser("reset-quota", help="reset a participant's contest quota")
    p.add_argument("participant_id")
    p.set_defaults(func=cmd_reset_quota)

    p = sub.add_parser("export-logs", help="export chat logs (.jsonl or .csv)")
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_export_logs)

    p = sub.add_parser("usage-summary", help="print token usage summary")
    p.set_defaults(func=cmd_usage)

    p = sub.add_parser("clear-sessions", help="invalidate all issued session tokens")
    p.set_defaults(func=cmd_clear_sessions)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
