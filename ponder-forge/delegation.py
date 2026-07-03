from __future__ import annotations

import json

try:
    from .profiles import get_profile
    from .store import PonderForgeStore
except ImportError:
    from profiles import get_profile
    from store import PonderForgeStore


def _profile_gate_guidance(profile_id: str) -> list[str]:
    if profile_id == "analysis":
        return [
            "Analysis gate detail: at least one metric_output evidence item must include a non-empty command and exit_code.",
        ]
    return []


def prepare_delegations(store: PonderForgeStore, run_id: str) -> dict:
    run = store.get_run(run_id)
    if not run:
        raise ValueError(f"unknown run_id: {run_id}")
    profile = get_profile(str(run["profile"]))
    config = json.loads(run.get("config_json") or "{}")
    constraints = config.get("constraints") if isinstance(config, dict) else None
    constraint_lines = []
    if isinstance(constraints, list) and constraints:
        constraint_lines = ["Ponder-Forge constraints:", *[f"- {constraint}" for constraint in constraints]]
    tasks = [task for task in store.list_rows("agent_tasks", run_id) if task.get("status") == "queued"]
    payload_tasks = []
    for task in tasks:
        marker = f"[PONDER_FORGE_RUN_ID={run_id}] [PONDER_FORGE_TASK_ID={task['task_id']}] [PONDER_FORGE_ROLE={task['role']}]"
        payload_tasks.append(
            {
                "goal": f"{marker} {task['goal']}",
                "context": "\n".join(
                    [
                        f"[PONDER_FORGE_PROFILE={profile.profile_id}]",
                        f"Ponder-Forge run goal: {run['user_goal']}",
                        *constraint_lines,
                        "You are a Ponder-Forge child agent. Work only on the assigned task.",
                        "Return a structured JSON report to the parent/controller with run_id, task_id, role, summary, assertions, evidence, and artifacts where applicable.",
                        "Do not mutate Ponder-Forge state or finalize the run; the parent/controller submits your JSON report with the Ponder-Forge CLI.",
                        f"Required evidence types: {', '.join(profile.required_evidence_types)}.",
                        *_profile_gate_guidance(profile.profile_id),
                        str(task.get("context") or ""),
                    ]
                ),
                "role": "leaf",
            }
        )
    return {
        "run_id": run_id,
        "native_tool_to_call_next": "delegate_task",
        "delegate_task_payload": {"tasks": payload_tasks},
        "instruction": "Immediately call native delegate_task with delegate_task_payload. Do not answer finally before CLI finalize returns a final report.",
    }
