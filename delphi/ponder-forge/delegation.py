from __future__ import annotations

import json

try:
    from .profiles import get_profile
    from .store import PonderForgeStore
    from .swarm import normalize_swarm_budget, task_kind, task_swarm
except ImportError:
    from profiles import get_profile
    from store import PonderForgeStore
    from swarm import normalize_swarm_budget, task_kind, task_swarm


def _required_evidence_line(profile) -> str:
    return f"Required evidence types: {', '.join(profile.required_evidence_types)}."


def _critical_assertion_type(profile) -> str:
    return str(profile.critical_assertion_types[0]) if profile.critical_assertion_types else "claim"


def _render_required_groups(profile) -> str:
    rendered = []
    for group in profile.required_evidence_groups:
        rendered.append("(" + " OR ".join(group) + ")" if len(group) > 1 else group[0])
    return " AND ".join(rendered)


def _profile_gate_guidance(profile) -> list[str]:
    assertion_type = _critical_assertion_type(profile)
    lines = [
        f"Profile gate detail: material claims should use assertion_type=\"{assertion_type}\" with importance>=0.8 or critical=true.",
        f"Gate-required evidence groups: {_render_required_groups(profile)}.",
    ]
    if profile.profile_id == "analysis":
        lines.append("Analysis evidence detail: at least one metric_output evidence item must include a non-empty command and exit_code=0.")
    if profile.profile_id == "coding":
        lines.append("Coding evidence detail: include root_cause_trace plus successful execution evidence such as passing_test or execution_log with exit_code=0.")
    if profile.profile_id == "math":
        lines.append("Math evidence detail: include proof_step plus critique or proof_check; only positive/unresolved counterexample evidence blocks the gate.")
    return lines


_ROLE_DUTIES = {
    "analysis": {
        "data_inspector": "Role duty: inventory datasets, artifacts, row counts, hashes, and data-boundary anomalies.",
        "metric_analyst": "Role duty: recompute or extract key metrics and include metric_output evidence with command and exit_code=0.",
        "reproduction_runner": "Role duty: run or describe read-only reproduction commands and preserve exact command outputs.",
        "sanity_reviewer": "Role duty: challenge metric consistency, gate boundaries, and overclaim risks.",
        "narrative_reviewer": "Role duty: synthesize evidence-backed conclusions and next-step recommendations without overclaiming.",
    }
}


def _role_guidance(profile_id: str, role: str) -> list[str]:
    duty = _ROLE_DUTIES.get(profile_id, {}).get(role)
    return [duty] if duty else []


_PREFERRED_EXAMPLE_EVIDENCE = {
    "research": ("source_quote",),
    "coding": ("root_cause_trace", "passing_test"),
    "design": ("constraint", "existing_owner_seam", "decision_reason"),
    "analysis": ("metric_output", "transform_script", "sanity_check"),
    "math": ("proof_step", "critique"),
}


def _example_evidence_item(evidence_type: str) -> dict[str, object]:
    item: dict[str, object] = {
        "evidence_type": evidence_type,
        "source_ref": "path or command",
        "quote_or_observation": "observed value",
    }
    if evidence_type in {"metric_output", "execution_log", "passing_test"}:
        item["command"] = "exact command if applicable"
        item["exit_code"] = 0
    return item


def _example_evidence(profile) -> list[dict]:
    evidence_types = _PREFERRED_EXAMPLE_EVIDENCE.get(profile.profile_id)
    if evidence_types is None:
        evidence_types = tuple(group[0] for group in profile.required_evidence_groups)
    return [_example_evidence_item(kind) for kind in evidence_types]


def _report_contract(profile) -> list[str]:
    assertion_shape = {
        "assertion_type": _critical_assertion_type(profile),
        "text": "evidence-backed claim",
        "importance": 0.9,
        "critical": True,
        "confidence": 0.8,
        "evidence": _example_evidence(profile),
    }
    return [
        "Child report JSON contract:",
        "Final response must contain a single valid JSON object matching this schema, with no Markdown wrapper. If you also write a human-readable note, list it in artifacts[]. Do not call the Ponder-Forge CLI.",
        "Required top-level keys: \"run_id\", \"task_id\", \"role\", \"summary\", \"assertions\", \"artifacts\".",
        f"Minimal assertion shape: {json.dumps(assertion_shape, ensure_ascii=False)}",
        "Artifact shape: {\"artifact_type\": \"report\", \"path\": \"path/to/artifact\", \"summary\": \"what it contains\"}.",
        "If you use top-level evidence instead of nested assertion evidence, every evidence item needs an id and each assertion must reference it with evidence_refs.",
    ]


def _task_context_lines(task_context: object, required_line: str) -> list[str]:
    text = str(task_context or "").strip()
    if not text or text == required_line:
        return []
    return [text]


def _constraint_lines(run: dict) -> list[str]:
    config = json.loads(run.get("config_json") or "{}")
    constraints = config.get("constraints") if isinstance(config, dict) else None
    if isinstance(constraints, list) and constraints:
        return ["Ponder-Forge constraints:", *[f"- {constraint}" for constraint in constraints]]
    return []


def build_child_context(run: dict, profile, task: dict, *, retry: bool = False) -> str:
    required_line = _required_evidence_line(profile)
    retry_lines = ["Retry context: this task was orphaned or stale; return a fresh child report for the same assigned task."] if retry else []
    return "\n".join(
        [
            f"[PONDER_FORGE_PROFILE={profile.profile_id}]",
            f"Ponder-Forge run goal: {run['user_goal']}",
            *_constraint_lines(run),
            *retry_lines,
            "You are a Ponder-Forge child agent. Work only on the assigned task.",
            "Return a structured JSON report to the parent/controller with run_id, task_id, role, summary, assertions, evidence, and artifacts where applicable.",
            "Do not mutate Ponder-Forge state or finalize the run; the parent/controller submits your JSON report with the Ponder-Forge CLI.",
            required_line,
            *_profile_gate_guidance(profile),
            *_role_guidance(profile.profile_id, str(task.get("role") or "")),
            *_report_contract(profile),
            *_task_context_lines(task.get("context"), required_line),
        ]
    )


def _queued_tasks_for_payload(store: PonderForgeStore, run_id: str, budget) -> list[dict]:
    queued = [task for task in store.list_rows("agent_tasks", run_id) if task.get("status") == "queued"]

    def sort_key(task: dict) -> tuple[int, int, str]:
        swarm = task_swarm(task)
        is_lane = 0 if swarm.get("kind") == "lane_coordinator" else 1
        lane_index = int(swarm.get("lane_index") or 0)
        return (is_lane, lane_index, str(task.get("task_id") or ""))

    return sorted(queued, key=sort_key)[: budget.delegate_batch_size]


def lane_child_tasks(store: PonderForgeStore, run_id: str, lane_task: dict) -> list[dict]:
    lane_task_id = lane_task.get("task_id")
    children = [
        task
        for task in store.list_rows("agent_tasks", run_id)
        if task.get("parent_task_id") == lane_task_id and task.get("status") == "planned" and task_kind(task) == "lane_child"
    ]
    return sorted(children, key=lambda task: int(task_swarm(task).get("child_index") or 0))


def _lane_report_contract(profile) -> list[str]:
    child_shape = {
        "task_id": "pf_task_child",
        "role": "child role",
        "summary": "child evidence summary",
        "assertions": [
            {
                "assertion_type": _critical_assertion_type(profile),
                "text": "evidence-backed claim",
                "importance": 0.9,
                "critical": True,
                "confidence": 0.8,
                "evidence": _example_evidence(profile),
            }
        ],
        "artifacts": [],
    }
    return [
        "Lane report JSON contract:",
        "Final lane response must contain a single valid JSON object with no Markdown wrapper.",
        'Required top-level keys: "run_id", "task_id", "role", "summary", "child_reports", "assertions", "artifacts".',
        'Top-level "artifacts" must be a JSON array of artifact metadata objects; use [] when no artifacts were created.',
        f"Each child_reports[] item should match this shape: {json.dumps(child_shape, ensure_ascii=False)}",
    ]


def build_lane_context(run: dict, profile, lane_task: dict, child_tasks: list[dict], *, retry: bool = False) -> str:
    swarm = task_swarm(lane_task)
    child_limit = int(swarm.get("child_concurrency_limit") or 1)
    retry_lines = ["Retry context: this lane coordinator was orphaned or stale; return a fresh lane report for the same assigned lane."] if retry else []
    child_manifest = [
        {
            "task_id": child["task_id"],
            "role": child["role"],
            "goal": child["goal"],
            "required_evidence_types": list(profile.required_evidence_types),
        }
        for child in child_tasks
    ]
    return "\n".join(
        [
            f"[PONDER_FORGE_PROFILE={profile.profile_id}]",
            f"Ponder-Forge run goal: {run['user_goal']}",
            *_constraint_lines(run),
            *retry_lines,
            "You are a Ponder-Forge lane coordinator. Work only on the assigned lane.",
            "Immediately call native delegate_task for the child tasks in this lane.",
            f"Run repeated child waves with at most {child_limit} child subagents in flight; this is a simultaneous concurrency cap, not a total child limit.",
            "After each wave returns JSON, launch the next wave until every planned child task in the manifest has returned.",
            "Do not call the Ponder-Forge CLI, mutate Ponder-Forge state, submit reports, gate, or finalize.",
            _required_evidence_line(profile),
            *_profile_gate_guidance(profile),
            f"Child task manifest: {json.dumps(child_manifest, ensure_ascii=False)}",
            *_lane_report_contract(profile),
            *_task_context_lines(lane_task.get("context"), _required_evidence_line(profile)),
        ]
    )


def _payload_role(task: dict) -> str:
    return "orchestrator" if task_kind(task) == "lane_coordinator" else "leaf"


def prepare_delegations(store: PonderForgeStore, run_id: str) -> dict:
    run = store.get_run(run_id)
    if not run:
        raise ValueError(f"unknown run_id: {run_id}")
    profile = get_profile(str(run["profile"]))
    budget = normalize_swarm_budget(json.loads(run.get("budget_json") or "{}"))
    queued_tasks = [task for task in store.list_rows("agent_tasks", run_id) if task.get("status") == "queued"]
    tasks = _queued_tasks_for_payload(store, run_id, budget)
    payload_tasks = []
    for task in tasks:
        marker = f"[PONDER_FORGE_RUN_ID={run_id}] [PONDER_FORGE_TASK_ID={task['task_id']}] [PONDER_FORGE_ROLE={task['role']}]"
        if task_kind(task) == "lane_coordinator":
            context = build_lane_context(run, profile, task, lane_child_tasks(store, run_id, task))
        else:
            context = build_child_context(run, profile, task)
        payload_tasks.append(
            {
                "goal": f"{marker} {task['goal']}",
                "context": context,
                "role": _payload_role(task),
            }
        )
    return {
        "run_id": run_id,
        "native_tool_to_call_next": "delegate_task",
        "delegate_task_payload": {"tasks": payload_tasks},
        "remaining_queued_tasks": max(0, len(queued_tasks) - len(tasks)),
        "instruction": "Immediately call native delegate_task with delegate_task_payload. Do not answer finally before CLI finalize returns a final report.",
    }
