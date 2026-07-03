from __future__ import annotations

import json

try:
    from .profiles import get_profile
    from .store import PonderForgeStore
except ImportError:
    from profiles import get_profile
    from store import PonderForgeStore


def _required_evidence_line(profile) -> str:
    return f"Required evidence types: {', '.join(profile.required_evidence_types)}."


def _profile_gate_guidance(profile_id: str) -> list[str]:
    if profile_id == "analysis":
        return [
            "Analysis gate detail: at least one material claim should use assertion_type=\"data_result\" with importance>=0.8 or critical=true.",
            "Analysis evidence detail: attach metric_output evidence with non-empty command and exit_code, plus transform_script or reproduction_log, plus sanity_check where applicable.",
        ]
    return []


_ROLE_DUTIES = {
    "analysis": {
        "data_inspector": "Role duty: inventory datasets, artifacts, row counts, hashes, and data-boundary anomalies.",
        "metric_analyst": "Role duty: recompute or extract key metrics and include metric_output evidence with command and exit_code.",
        "reproduction_runner": "Role duty: run or describe read-only reproduction commands and preserve exact command outputs.",
        "sanity_reviewer": "Role duty: challenge metric consistency, gate boundaries, and overclaim risks.",
        "narrative_reviewer": "Role duty: synthesize evidence-backed conclusions and next-step recommendations without overclaiming.",
    }
}


def _role_guidance(profile_id: str, role: str) -> list[str]:
    duty = _ROLE_DUTIES.get(profile_id, {}).get(role)
    return [duty] if duty else []


def _report_contract(profile_id: str) -> list[str]:
    assertion_type = "data_result" if profile_id == "analysis" else "<profile_assertion_type>"
    return [
        "Child report JSON contract:",
        "Final response must contain a single valid JSON object matching this schema, with no Markdown wrapper. If you also write a human-readable note, list it in artifacts[]. Do not call the Ponder-Forge CLI.",
        "Required top-level keys: \"run_id\", \"task_id\", \"role\", \"summary\", \"assertions\", \"artifacts\".",
        f"Minimal assertion shape: {{\"assertion_type\": \"{assertion_type}\", \"text\": \"evidence-backed claim\", \"importance\": 0.9, \"critical\": true, \"confidence\": 0.8, \"evidence\": [{{\"evidence_type\": \"metric_output\", \"source_ref\": \"path or command\", \"quote_or_observation\": \"observed value\", \"command\": \"exact command if applicable\", \"exit_code\": 0}}, {{\"evidence_type\": \"sanity_check\", \"source_ref\": \"path\", \"quote_or_observation\": \"consistency check\"}}, {{\"evidence_type\": \"reproduction_log\", \"source_ref\": \"path or command\", \"quote_or_observation\": \"reproduction note\"}}]}}",
        "Artifact shape: {\"artifact_type\": \"report\", \"path\": \"path/to/artifact\", \"summary\": \"what it contains\"}.",
        "If you use top-level evidence instead of nested assertion evidence, every evidence item needs an id and each assertion must reference it with evidence_refs.",
    ]


def _task_context_lines(task_context: object, required_line: str) -> list[str]:
    text = str(task_context or "").strip()
    if not text or text == required_line:
        return []
    return [text]


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
        required_line = _required_evidence_line(profile)
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
                        required_line,
                        *_profile_gate_guidance(profile.profile_id),
                        *_role_guidance(profile.profile_id, str(task.get("role") or "")),
                        *_report_contract(profile.profile_id),
                        *_task_context_lines(task.get("context"), required_line),
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
