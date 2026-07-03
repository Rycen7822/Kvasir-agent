from __future__ import annotations

import json
from typing import Any

try:
    from .profiles import get_profile
    from .store import PonderForgeStore
except ImportError:
    from profiles import get_profile
    from store import PonderForgeStore

JsonDict = dict[str, Any]


def _loads(value: str | None) -> JsonDict:
    if not value:
        return {}
    return json.loads(value)


def plan_run(store: PonderForgeStore, run_id: str) -> JsonDict:
    run = store.get_run(run_id)
    if not run:
        raise ValueError(f"unknown run_id: {run_id}")
    existing_tasks = store.list_rows("agent_tasks", run_id)
    if existing_tasks:
        return {"run_id": run_id, "profile": run["profile"], "tasks": existing_tasks, "workflow_nodes": store.list_rows("workflow_nodes", run_id)}

    profile = get_profile(str(run["profile"]))
    budget = _loads(run.get("budget_json"))
    max_tasks = int(budget.get("max_tasks_per_wave", min(3, len(profile.roles))))
    tasks: list[JsonDict] = []
    nodes: list[JsonDict] = []
    for role in profile.roles[:max_tasks]:
        node = store.create_workflow_node(
            run_id=run_id,
            profile=profile.profile_id,
            node_type="explore",
            role=role,
            input_data={"required_evidence_types": profile.required_evidence_types},
        )
        nodes.append(node)
        task = store.create_task(
            run_id,
            role=role,
            goal=f"Work as {role} on the {profile.profile_id} profile task. Produce structured evidence, not a final answer.",
            context=f"Required evidence types: {', '.join(profile.required_evidence_types)}.",
            node_id=node["node_id"],
            raw={"profile": profile.profile_id, "required_evidence_types": profile.required_evidence_types},
        )
        tasks.append(task)
    store.update_run_status(run_id, "planning")
    return {"run_id": run_id, "profile": profile.profile_id, "tasks": tasks, "workflow_nodes": nodes}
