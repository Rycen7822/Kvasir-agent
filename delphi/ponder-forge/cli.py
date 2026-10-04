from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, NoReturn

try:
    from .delegation import prepare_delegations
    from .gates import evaluate_gate, supported_critical_assertion_ids
    from .planner import plan_run
    from .profiles import list_profiles, select_profile
    from .reconcile import reconcile_run
    from .renderer import render_final_report
    from .report_ingest import ingest_report
    from .store import PonderForgeStore
    from .swarm import normalize_swarm_budget, swarm_progress_status
    from .verifier import verify_run
except ImportError:
    from delegation import prepare_delegations
    from gates import evaluate_gate, supported_critical_assertion_ids
    from planner import plan_run
    from profiles import list_profiles, select_profile
    from reconcile import reconcile_run
    from renderer import render_final_report
    from report_ingest import ingest_report
    from store import PonderForgeStore
    from swarm import normalize_swarm_budget, swarm_progress_status
    from verifier import verify_run

JsonDict = dict[str, Any]
COMMAND_NAMES = ("start", "plan", "delegations", "submit-report", "status", "verify", "gate", "finalize", "reconcile")


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def _json(payload: JsonDict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _ok(payload: JsonDict | None = None) -> JsonDict:
    return {"success": True, **(payload or {})}


def _err(message: str, *, hint: str | None = None, **extra: Any) -> JsonDict:
    payload = {"success": False, "error": message, **extra}
    if hint:
        payload["hint"] = hint
    return payload


def _emit(payload: JsonDict) -> int:
    print(_json(payload))
    return 0 if payload.get("success") is True else 1


def _store() -> PonderForgeStore:
    store = PonderForgeStore()
    store.initialize()
    return store


def _hint_for_error(message: str) -> str:
    profiles = ", ".join(("auto", *list_profiles()))
    if "arguments are required: command" in message or "argument command: invalid choice" in message:
        return f"Use one subcommand: {', '.join(COMMAND_NAMES)}."
    if "arguments are required: --file" in message:
        return "Use `submit-report --file report.json` or `submit-report --file -` for stdin."
    if "arguments are required: --goal" in message:
        return "Use `start --goal \"...\"`; keep `--profile auto` unless a specific profile is needed."
    if "arguments are required: --run-id" in message:
        return "Use `--run-id pf_run_...` from the previous `start` output."
    if "argument --mode: invalid choice" in message:
        return "Use `--mode precheck` or `--mode independent_review`."
    if "argument --verdict: invalid choice" in message:
        return "Use `--verdict accept`, `reject`, or `revise`."
    if "argument --stale-after-seconds: invalid int value" in message:
        return "Pass integer seconds, e.g. `--stale-after-seconds 1800`."
    if "unknown Ponder-Forge profile" in message:
        return f"Use `--profile` one of: {profiles}."
    if "budget" in message or "max_tasks_per_wave" in message or "subagents_per_run" in message:
        return "Use --budget-json with positive integer top_level_runs and child_concurrency_per_lane, e.g. '{\"top_level_runs\": 8, \"child_concurrency_per_lane\": 4}'."
    if "--budget-json" in message:
        return "Pass a JSON object, e.g. `--budget-json '{\"max_rounds\": 2}'`, or omit it."
    if "JSON report file was not found" in message:
        return "Check the path or use `--file -` to read the report JSON from stdin."
    if "invalid JSON" in message:
        return "Fix the JSON object; check quotes/commas, or pass valid JSON with `--file -`."
    if "JSON payload must be an object" in message or "must decode to a JSON object" in message:
        return "Use a top-level JSON object `{...}`, not a list or scalar."
    if "report JSON must include run_id" in message:
        return "Include run_id from `start`; include task_id from `plan`/`delegations` when available."
    if "artifacts must be a JSON array" in message:
        return 'Use "artifacts": [] for none, or a list like [{"artifact_type":"report","path":"...","summary":"..."}].'
    if "unknown run_id" in message:
        return "Use a `run_id` returned by `start`; rerun `start` if you lost it."
    if "target_id is required for independent verdict" in message:
        return "Pass `--target-id pf_assertion_...` before recording an independent verdict."
    if "unknown target assertion" in message:
        return "Use a target assertion id from `submit-report`, `gate`, or the same run."
    return "Run the same command with `--help` for accepted arguments."


def _load_json_object_text(raw: str, source: str) -> JsonDict:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {source}: line {exc.lineno} column {exc.colno}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{source} must decode to a JSON object")
    return payload


def _load_json_file(path: str) -> JsonDict:
    source = "stdin" if path == "-" else "--file"
    if path == "-":
        raw = sys.stdin.read()
    else:
        expanded = Path(path).expanduser()
        try:
            raw = expanded.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ValueError(f"JSON report file was not found: {expanded}") from exc
        except OSError as exc:
            raise ValueError(f"could not read JSON report file: {expanded}: {exc.strerror or exc}") from exc
    return _load_json_object_text(raw, source)


def _final_artifact_paths(store: PonderForgeStore, run_id: str) -> JsonDict:
    run_dir = store.run_dir(run_id)
    return {
        "final_md": str(run_dir / "final.md"),
        "graph_json": str(run_dir / "graph.json"),
        "verdicts_json": str(run_dir / "verdicts.json"),
        "pool_status_json": str(run_dir / "pool_status.json"),
    }


def _completed_final_payload(store: PonderForgeStore, run: JsonDict) -> JsonDict | None:
    if run.get("status") != "completed" or not run.get("final_report_md"):
        return None
    run_id = str(run["run_id"])
    return {
        "status": "final",
        "run_id": run_id,
        "final_report_markdown": str(run["final_report_md"]),
        "artifact_paths": _final_artifact_paths(store, run_id),
        "idempotent": True,
    }


def start_run(
    goal: str,
    *,
    profile: str = "auto",
    constraints: list[str] | None = None,
    budget: JsonDict | None = None,
    parent_session_id: str | None = None,
) -> JsonDict:
    selected = select_profile(goal, requested=profile or "auto")
    normalized_budget = normalize_swarm_budget(budget).as_dict()
    run = _store().create_run(
        goal=goal,
        profile=selected,
        budget=normalized_budget,
        config={"constraints": constraints or []},
        parent_session_id=parent_session_id,
    )
    return {
        "ok": True,
        "run_id": run["run_id"],
        "profile": selected,
        "status": run["status"],
        "next_command": "plan",
    }


def cmd_start(args: argparse.Namespace) -> JsonDict:
    budget = _load_json_object_text(args.budget_json, "--budget-json") if args.budget_json else {}
    return _ok(
        start_run(
            args.goal,
            profile=args.profile,
            constraints=args.constraint,
            budget=budget,
            parent_session_id=args.parent_session_id,
        )
    )


def cmd_plan(args: argparse.Namespace) -> JsonDict:
    return _ok(plan_run(_store(), args.run_id))


def cmd_delegations(args: argparse.Namespace) -> JsonDict:
    return _ok(prepare_delegations(_store(), args.run_id))


def cmd_submit_report(args: argparse.Namespace) -> JsonDict:
    payload = _load_json_file(args.file)
    run_id = str(payload.get("run_id") or "")
    if not run_id:
        raise ValueError("report JSON must include run_id")
    store = _store()
    run = store.get_run(run_id)
    if run and run.get("status") == "completed":
        return _err("run is already completed; report submission is closed", run_id=run_id, status="completed")
    result = ingest_report(store, payload)
    task_id = payload.get("task_id")
    if task_id:
        store.update_task_status(str(task_id), "finished")
    return _ok(result)


def cmd_status(args: argparse.Namespace) -> JsonDict:
    store = _store()
    tasks = store.list_rows("agent_tasks", args.run_id)
    counts = {
        "agent_tasks": len(tasks),
        **{table: len(store.list_rows(table, args.run_id)) for table in ("reports", "assertions", "evidence_items", "artifacts")},
    }
    gate = evaluate_gate(store, args.run_id)
    run = store.get_run(args.run_id)
    run_status = str(run.get("status") or "unknown") if run else "unknown"
    final_report_present = bool(run and run.get("final_report_md"))
    budget = json.loads(run.get("budget_json") or "{}") if run else {}
    swarm = swarm_progress_status(tasks, budget)
    queued_tasks = [task for task in tasks if task.get("status") == "queued"]
    if run_status == "completed" and final_report_present:
        next_action = "complete"
    elif queued_tasks:
        next_action = "delegations"
    elif swarm["is_swarm_run"] and swarm["incomplete_task_count"]:
        next_action = "submit-report"
    else:
        next_action = "finalize" if gate["finalize_allowed"] else "verify"
    return _ok(
        {
            "run_id": args.run_id,
            "run_status": run_status,
            "counts": counts,
            "swarm": swarm,
            "gate_status": gate["status"],
            "next_required_action": next_action,
        }
    )


def cmd_verify(args: argparse.Namespace) -> JsonDict:
    payload = _load_json_file(args.file) if args.file else {}
    payload["run_id"] = args.run_id
    payload["mode"] = args.mode
    for key in (
        "target_id",
        "reviewer_task_id",
        "reviewer_role",
        "independent_from_task_id",
        "verdict",
        "rationale",
    ):
        value = getattr(args, key)
        if value is not None:
            payload[key] = value
    if args.confidence is not None:
        payload["confidence"] = args.confidence
    return _ok(verify_run(_store(), args.run_id, payload))


def cmd_gate(args: argparse.Namespace) -> JsonDict:
    return _ok(evaluate_gate(_store(), args.run_id))


def cmd_finalize(args: argparse.Namespace) -> JsonDict:
    store = _store()
    run = store.get_run(args.run_id)
    if run:
        completed = _completed_final_payload(store, run)
        if completed:
            return _ok(completed)
    gate = evaluate_gate(store, args.run_id)
    if not gate["finalize_allowed"]:
        return _ok({"status": "blocked", "reason": "profile_gate_failed", "gaps": gate["gaps"], "instruction": "Continue Ponder-Forge. Do not produce final answer."})
    for assertion_id in supported_critical_assertion_ids(store, args.run_id):
        store.update_assertion_status(assertion_id, "accepted")
    return _ok(render_final_report(store, args.run_id))


def cmd_reconcile(args: argparse.Namespace) -> JsonDict:
    return _ok(reconcile_run(_store(), args.run_id, stale_after_seconds=args.stale_after_seconds))


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(description="Ponder-Forge CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Create a Ponder-Forge run")
    start.add_argument("--goal", required=True)
    start.add_argument("--profile", default="auto")
    start.add_argument("--constraint", action="append", default=[])
    start.add_argument("--budget-json", default="")
    start.add_argument("--parent-session-id", default=None)
    start.set_defaults(func=cmd_start)

    plan = subparsers.add_parser("plan", help="Plan workflow tasks")
    plan.add_argument("--run-id", required=True)
    plan.set_defaults(func=cmd_plan)

    delegations = subparsers.add_parser("delegations", help="Return native delegate_task payload")
    delegations.add_argument("--run-id", required=True)
    delegations.set_defaults(func=cmd_delegations)

    submit = subparsers.add_parser("submit-report", help="Ingest a structured JSON report")
    submit.add_argument("--file", required=True, help="JSON report path, or '-' for stdin")
    submit.set_defaults(func=cmd_submit_report)

    status = subparsers.add_parser("status", help="Return compact run status")
    status.add_argument("--run-id", required=True)
    status.set_defaults(func=cmd_status)

    verify = subparsers.add_parser("verify", help="Run verifier precheck or record independent verdict")
    verify.add_argument("--run-id", required=True)
    verify.add_argument("--mode", default="precheck", choices=("precheck", "independent_review"))
    verify.add_argument("--file", default="", help="Optional JSON payload to merge with CLI args")
    verify.add_argument("--target-id", default=None)
    verify.add_argument("--reviewer-task-id", default=None)
    verify.add_argument("--reviewer-role", default=None)
    verify.add_argument("--independent-from-task-id", default=None)
    verify.add_argument("--verdict", default=None, choices=("accept", "reject", "revise"))
    verify.add_argument("--confidence", type=float, default=None)
    verify.add_argument("--rationale", default=None)
    verify.set_defaults(func=cmd_verify)

    gate = subparsers.add_parser("gate", help="Evaluate profile gate")
    gate.add_argument("--run-id", required=True)
    gate.set_defaults(func=cmd_gate)

    finalize = subparsers.add_parser("finalize", help="Render final report when gate allows")
    finalize.add_argument("--run-id", required=True)
    finalize.set_defaults(func=cmd_finalize)

    reconcile = subparsers.add_parser("reconcile", help="Recover stale or orphaned tasks")
    reconcile.add_argument("--run-id", required=True)
    reconcile.add_argument("--stale-after-seconds", type=int, default=1800)
    reconcile.set_defaults(func=cmd_reconcile)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        return _emit(args.func(args))
    except Exception as exc:
        message = str(exc)
        return _emit(_err(message, hint=_hint_for_error(message)))


if __name__ == "__main__":
    raise SystemExit(main())
