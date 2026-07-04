from __future__ import annotations

import json
from typing import Any

try:
    from .profiles import get_profile
    from .store import PonderForgeStore
    from .swarm import normalize_swarm_budget
except ImportError:
    from profiles import get_profile
    from store import PonderForgeStore
    from swarm import normalize_swarm_budget

JsonDict = dict[str, Any]


def _loads(value: str | None) -> JsonDict:
    if not value:
        return {}
    return json.loads(value)


def derive_lane_child_specs(_run: JsonDict, profile: Any, lane_index: int) -> list[JsonDict]:
    return [
        {
            "role": role,
            "goal": (
                f"Lane {lane_index} child work for {role}: gather structured evidence for the "
                f"{profile.profile_id} profile."
            ),
        }
        for role in profile.roles
    ]


def _lane_id(lane_index: int) -> str:
    return f"lane_{lane_index:02d}"


def _child_role(spec: JsonDict, profile: Any, lane_index: int, child_index: int) -> str:
    role = spec.get("role")
    if isinstance(role, str) and role:
        return role
    return profile.roles[(lane_index - 1 + child_index - 1) % len(profile.roles)]


def plan_run(store: PonderForgeStore, run_id: str) -> JsonDict:
    run = store.get_run(run_id)
    if not run:
        raise ValueError(f"unknown run_id: {run_id}")
    budget_data = _loads(run.get("budget_json"))
    existing_tasks = store.list_rows("agent_tasks", run_id)
    if existing_tasks:
        return {
            "run_id": run_id,
            "profile": run["profile"],
            "swarm_budget": normalize_swarm_budget(budget_data).as_dict(),
            "tasks": existing_tasks,
            "workflow_nodes": store.list_rows("workflow_nodes", run_id),
        }

    profile = get_profile(str(run["profile"]))
    budget = normalize_swarm_budget(budget_data)
    tasks: list[JsonDict] = []
    nodes: list[JsonDict] = []
    for lane_index in range(1, budget.top_level_runs + 1):
        lane_id = _lane_id(lane_index)
        node = store.create_workflow_node(
            run_id=run_id,
            profile=profile.profile_id,
            node_type="lane",
            role="swarm_lane_coordinator",
            input_data={
                "lane_id": lane_id,
                "lane_index": lane_index,
                "required_evidence_types": profile.required_evidence_types,
            },
        )
        nodes.append(node)
        child_specs = derive_lane_child_specs(run, profile, lane_index)
        lane_task = store.create_task(
            run_id,
            role="swarm_lane_coordinator",
            goal=(
                f"Coordinate {lane_id} for the {profile.profile_id} profile. Delegate all assigned "
                f"planned child tasks in waves of at most {budget.child_concurrency_per_lane} simultaneous "
                "child subagents, then return one lane report with child_reports."
            ),
            context=(
                f"Lane {lane_id}. Required evidence types: {', '.join(profile.required_evidence_types)}. "
                "Do not call the Ponder-Forge CLI; return JSON to the parent/controller."
            ),
            node_id=node["node_id"],
            raw={
                "profile": profile.profile_id,
                "required_evidence_types": profile.required_evidence_types,
                "swarm": {
                    "kind": "lane_coordinator",
                    "lane_id": lane_id,
                    "lane_index": lane_index,
                    "top_level_runs": budget.top_level_runs,
                    "child_concurrency_limit": budget.child_concurrency_per_lane,
                },
            },
        )
        tasks.append(lane_task)
        for child_index, spec in enumerate(child_specs, start=1):
            role = _child_role(spec, profile, lane_index, child_index)
            child_task = store.create_task(
                run_id,
                role=role,
                goal=str(spec.get("goal") or f"Work as {role} in {lane_id}."),
                context=str(
                    spec.get("context")
                    or f"Required evidence types: {', '.join(profile.required_evidence_types)}."
                ),
                node_id=node["node_id"],
                parent_task_id=lane_task["task_id"],
                status="planned",
                raw={
                    "profile": profile.profile_id,
                    "required_evidence_types": profile.required_evidence_types,
                    "swarm": {
                        "kind": "lane_child",
                        "lane_id": lane_id,
                        "lane_index": lane_index,
                        "child_index": child_index,
                        "child_concurrency_limit": budget.child_concurrency_per_lane,
                        "planned_child_count": len(child_specs),
                    },
                },
            )
            tasks.append(child_task)
    store.update_run_status(run_id, "planning")
    return {
        "run_id": run_id,
        "profile": profile.profile_id,
        "swarm_budget": budget.as_dict(),
        "tasks": tasks,
        "workflow_nodes": nodes,
    }
