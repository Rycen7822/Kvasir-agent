"""Diagnostics only: the host owns actual agent and process lifecycle."""
from __future__ import annotations
try:
    from .gates import evaluate_gate
except ImportError:
    from gates import evaluate_gate


def reconcile_run(store, run_id: str) -> dict:
    if not store.get_run(run_id):
        raise ValueError(f"unknown run_id: {run_id}")
    tasks = store.list_rows("agent_tasks", run_id)
    return {"run_id": run_id, "gate": evaluate_gate(store, run_id),
            "queued": [x for x in tasks if x["status"] == "queued"],
            "running": [x for x in tasks if x["status"] == "running"],
            "instruction": "Compare recorded assignments with actual native host state. "
                "No process liveness, retries or repairs are inferred from record age."}
