"""Save the coordinator's complete answer, including honest partial outcomes."""
from __future__ import annotations
import json
try:
    from .gates import evaluate_gate
    from .planner import require_active_run
except ImportError:
    from gates import evaluate_gate
    from planner import require_active_run


def saved_final_report(store, run: dict) -> dict | None:
    if run["status"] not in {"completed", "partial"} or not run.get("final_report_md"):
        return None
    directory = store.run_dir(run["run_id"])
    names = ("final.md", "task_board.json", "reports.json", "graph.json", "verdicts.json", "pool_status.json")
    return {"run_id": run["run_id"], "status": "final" if run["status"] == "completed" else "partial",
            "final_report_md": run["final_report_md"], "idempotent": True,
            "artifact_paths": {name: str(directory / name) for name in names if (directory / name).exists()}}


def render_final_report(store, run_id: str, draft: str, *, partial: bool = False, reason: str = "") -> dict:
    run = store.get_run(run_id)
    if not run:
        raise ValueError(f"unknown run_id: {run_id}")
    saved = saved_final_report(store, run)
    if saved:
        return saved
    require_active_run(store, run_id)
    if not isinstance(draft, str) or not draft.strip():
        raise ValueError("finalize requires a complete, nonempty draft")
    if partial and not reason.strip():
        raise ValueError("partial completion requires a reason")
    gate = evaluate_gate(store, run_id)
    if not partial and not gate["pass"]:
        raise ValueError("research task board has unresolved questions; resolve, cancel with reason or save --partial")
    if partial:
        draft += f"\n\n## Partial result\nReason: {reason}\n"
        if gate["pending_tasks"]:
            draft += "\nUnresolved questions:\n" + "\n".join(f"- {x['description']} ({x['resolution']})" for x in gate["pending_tasks"]) + "\n"
    directory = store.run_dir(run_id)
    directory.mkdir(parents=True, exist_ok=True)
    artifacts = {"final.md": draft, "task_board.json": json.dumps(gate["task_board"], ensure_ascii=False, indent=2),
                 "reports.json": json.dumps(store.list_rows("reports", run_id), ensure_ascii=False, indent=2)}
    for name, content in artifacts.items():
        (directory / name).write_text(content)
    store.update_final_report(run_id, draft, status="partial" if partial else "completed")
    store.append_event(run_id, "run_finalized", {"partial": partial, "reason": reason})
    return {"run_id": run_id, "status": "partial" if partial else "final", "final_report_md": draft,
            "artifact_paths": {name: str(directory / name) for name in artifacts}}
