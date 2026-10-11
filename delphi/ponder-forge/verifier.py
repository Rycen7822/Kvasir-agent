"""Prepare Frontier's whole-answer verification and local source arbitration."""
from __future__ import annotations
try:
    from .planner import require_active_run
    from .delegation import prepare_delegations, report_content
except ImportError:
    from planner import require_active_run
    from delegation import prepare_delegations, report_content


def verify_run(store, run_id: str, args: dict, *, allocation_ids: list[str] | None = None) -> dict:
    run = require_active_run(store, run_id)
    mode = args.get("mode", "final")
    if mode == "final":
        draft = args.get("draft")
        if not isinstance(draft, str) or not draft.strip():
            raise ValueError("final verifier requires the complete draft")
        name = "final_verifier"
        prompt = f"Original question:\n{run['user_goal']}\n\nComplete proposed answer:\n{draft}"
    elif mode == "local":
        conflict, ids = args.get("conflict"), args.get("report_ids")
        if not isinstance(conflict, str) or not conflict.strip():
            raise ValueError("local verifier requires a specific conflict")
        if not isinstance(ids, list) or len(set(ids)) < 2:
            raise ValueError("local verifier requires at least two different report_ids")
        reports = [store.get_report(x) for x in ids]
        if any(not x or x["run_id"] != run_id for x in reports):
            raise ValueError("local verifier reports must belong to this run")
        producers = {x["task_id"] for x in reports}
        if len(producers) < 2:
            raise ValueError("local verifier requires reports from different assignments")
        name = "local_verifier"
        prompt = f"Original question:\n{run['user_goal']}\n\nConflict to resolve from sources:\n{conflict}\n"
        for report in reports:
            prompt += f"\nFull report {report['report_id']} ({report['role']}):\n{report_content(report)}\n"
    else:
        raise ValueError("verification mode must be final or local")
    return prepare_delegations(store, run_id, {"tasks": [{"agent": name, "prompt": prompt,
        "system_prompt": "", "task_ids": args.get("task_ids", [])}]}, allocation_ids=allocation_ids)
