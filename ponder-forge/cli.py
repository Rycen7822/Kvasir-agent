from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .delegation import prepare_delegations
    from .gates import evaluate_gate, supported_critical_assertion_ids
    from .planner import plan_run
    from .profiles import select_profile
    from .reconcile import reconcile_run
    from .renderer import render_final_report
    from .report_ingest import ingest_report
    from .store import PonderForgeStore
    from .verifier import verify_run
except ImportError:
    from delegation import prepare_delegations
    from gates import evaluate_gate, supported_critical_assertion_ids
    from planner import plan_run
    from profiles import select_profile
    from reconcile import reconcile_run
    from renderer import render_final_report
    from report_ingest import ingest_report
    from store import PonderForgeStore
    from verifier import verify_run

JsonDict = dict[str, Any]


def _json(payload: JsonDict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _ok(payload: JsonDict | None = None) -> JsonDict:
    return {"success": True, **(payload or {})}


def _err(message: str, **extra: Any) -> JsonDict:
    return {"success": False, "error": message, **extra}


def _emit(payload: JsonDict) -> int:
    print(_json(payload))
    return 0 if payload.get("success") is True else 1


def _store() -> PonderForgeStore:
    store = PonderForgeStore()
    store.initialize()
    return store


def _load_json_file(path: str) -> JsonDict:
    raw = sys.stdin.read() if path == "-" else Path(path).expanduser().read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")
    return payload


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
    run = _store().create_run(
        goal=goal,
        profile=selected,
        budget=budget or {},
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
    budget = json.loads(args.budget_json) if args.budget_json else {}
    if not isinstance(budget, dict):
        raise ValueError("--budget-json must decode to an object")
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
    counts = {table: len(store.list_rows(table, args.run_id)) for table in ("agent_tasks", "reports", "assertions", "evidence_items", "artifacts")}
    gate = evaluate_gate(store, args.run_id)
    return _ok(
        {
            "run_id": args.run_id,
            "counts": counts,
            "gate_status": gate["status"],
            "next_required_action": "finalize" if gate["finalize_allowed"] else "verify",
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
    parser = argparse.ArgumentParser(description="Ponder-Forge CLI")
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
        return _emit(_err(str(exc)))


if __name__ == "__main__":
    raise SystemExit(main())
