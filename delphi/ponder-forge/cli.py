"""CLI state bridge for FrontierAgent's high/max strategy on native agent hosts."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

try:
    from .delegation import prepare_delegations, record_dispatch, report_content
    from .gates import evaluate_gate
    from .planner import plan_run, task_board
    from .profiles import select_profile, PROFILE_IDS
    from .reconcile import reconcile_run
    from .renderer import render_final_report, saved_final_report
    from .report_ingest import ingest_report
    from .store import PonderForgeStore
    from .strategy import team_effort
    from .swarm import normalize_swarm_budget
    from .verifier import verify_run
except ImportError:
    from delegation import prepare_delegations, record_dispatch, report_content
    from gates import evaluate_gate
    from planner import plan_run, task_board
    from profiles import select_profile, PROFILE_IDS
    from reconcile import reconcile_run
    from renderer import render_final_report, saved_final_report
    from report_ingest import ingest_report
    from store import PonderForgeStore
    from strategy import team_effort
    from swarm import normalize_swarm_budget
    from verifier import verify_run


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str):
        raise ValueError(message)


def _store():
    store = PonderForgeStore()
    store.initialize()
    return store


def _load_json_file(path: str) -> dict:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("JSON input must be an object")
    return value


def start_run(goal: str, *, profile: str = "auto", constraints: str = "",
              budget: dict | None = None, team_effort: str = "max") -> dict:
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("goal must not be empty")
    if team_effort not in {"high", "max"}:
        raise ValueError("team_effort must be high or max")
    selected = select_profile(goal, requested=profile)
    limits = normalize_swarm_budget(budget)
    store = _store()
    run = store.create_run(goal=goal, profile=selected,
        config={"constraints": constraints, "team_effort": team_effort}, budget=limits.as_dict())
    return {"run_id": run["run_id"], "profile": selected, "team_effort": team_effort,
            "status": run["status"], "next_command": "plan"}


def cmd_start(args):
    budget = json.loads(args.budget) if args.budget is not None else None
    return start_run(args.goal, profile=args.profile, constraints=args.constraints,
                     budget=budget, team_effort=args.team_effort)


def cmd_plan(args):
    return plan_run(_store(), args.run_id, _load_json_file(args.file) if args.file else None)


def cmd_delegations(args):
    store = _store()
    if args.started or args.cancelled:
        return record_dispatch(store, args.run_id, args.started or args.cancelled,
            host_agent_id=args.host_agent_id, cancelled=bool(args.cancelled))
    if args.host_agent_id:
        raise ValueError("--host-agent-id requires --started")
    return prepare_delegations(store, args.run_id, _load_json_file(args.file) if args.file else None)


def cmd_submit_report(args):
    return ingest_report(_store(), _load_json_file(args.file))


def cmd_status(args):
    store = _store()
    run = store.get_run(args.run_id)
    if not run:
        raise ValueError(f"unknown run_id: {args.run_id}")
    tasks = store.list_rows("agent_tasks", args.run_id)
    reports = store.list_rows("reports", args.run_id)
    returned = []
    for row in reports:
        item = {key: row[key] for key in ("report_id", "task_id", "role", "title", "confidence")}
        if args.reports:
            item["content"] = report_content(row)
        returned.append(item)
    return {"run_id": args.run_id, "status": run["status"], "profile": run["profile"],
            "team_effort": team_effort(run), "task_board": task_board(store, args.run_id),
            "assignments": [{"task_id": row["task_id"], "agent": row["role"], "status": row["status"],
                             "host_agent_id": row["hermes_subagent_id"]} for row in tasks],
            "reports": returned, "gate": evaluate_gate(store, args.run_id),
            "saved_final": saved_final_report(store, run)}


def cmd_verify(args):
    if args.mode == "final":
        draft = sys.stdin.read() if args.file == "-" else Path(args.file).read_text()
        payload = {"mode": "final", "draft": draft}
    else:
        payload = {**_load_json_file(args.file), "mode": "local"}
    return verify_run(_store(), args.run_id, payload)


def cmd_gate(args):
    return evaluate_gate(_store(), args.run_id)


def cmd_finalize(args):
    store = _store()
    run = store.get_run(args.run_id)
    if not run:
        raise ValueError(f"unknown run_id: {args.run_id}")
    saved = saved_final_report(store, run)
    if saved:
        return saved
    if not args.file:
        raise ValueError("finalize requires --file with the complete draft")
    if args.reason and not args.partial:
        raise ValueError("--reason requires --partial")
    draft = sys.stdin.read() if args.file == "-" else Path(args.file).read_text()
    return render_final_report(store, args.run_id, draft, partial=args.partial, reason=args.reason or "")


def cmd_reconcile(args):
    return reconcile_run(_store(), args.run_id)


def build_parser():
    parser = JsonArgumentParser(prog="ponder-forge")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)
    p = sub.add_parser("start")
    p.add_argument("--goal", required=True)
    p.add_argument("--profile", choices=("auto", *PROFILE_IDS), default="auto")
    p.add_argument("--team-effort", choices=("high", "max"), default="max")
    p.add_argument("--constraints", default="")
    p.add_argument("--budget", help='JSON object with optional delegate_batch_size (1..20)')
    p.set_defaults(handler=cmd_start)
    for name, handler in (("plan", cmd_plan), ("delegations", cmd_delegations),
                          ("status", cmd_status), ("gate", cmd_gate), ("reconcile", cmd_reconcile)):
        p = sub.add_parser(name)
        p.add_argument("--run-id", required=True)
        if name == "plan":
            p.add_argument("--file", help="coordinator-authored task board JSON")
        elif name == "delegations":
            action = p.add_mutually_exclusive_group()
            action.add_argument("--file", help="coordinator-authored assignments JSON")
            action.add_argument("--started", metavar="TASK_ID", help="record a real host launch")
            action.add_argument("--cancelled", metavar="TASK_ID", help="record a confirmed host cancellation")
            p.add_argument("--host-agent-id")
        elif name == "status":
            p.add_argument("--reports", action="store_true", help="include full returned text")
        p.set_defaults(handler=handler)
    p = sub.add_parser("submit-report")
    p.add_argument("--file", required=True)
    p.set_defaults(handler=cmd_submit_report)
    p = sub.add_parser("verify")
    p.add_argument("--run-id", required=True)
    p.add_argument("--mode", choices=("final", "local"), default="final")
    p.add_argument("--file", required=True)
    p.set_defaults(handler=cmd_verify)
    p = sub.add_parser("finalize")
    p.add_argument("--run-id", required=True)
    p.add_argument("--file")
    p.add_argument("--partial", action="store_true")
    p.add_argument("--reason")
    p.set_defaults(handler=cmd_finalize)
    return parser


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        payload = {"success": True, **args.handler(args)}
    except (ValueError, OSError, TypeError, KeyError) as exc:
        payload = {"success": False, "error": str(exc)}
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
