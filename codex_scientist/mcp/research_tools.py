"""MCP research primitive wrappers.

Wrappers in this module call CodexScientist Python services or native in-process
handlers. They intentionally do not spawn compatibility command-line entrypoints.
"""
from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from codex_scientist.adapters.cli import normalize_envelope
from codex_scientist.mcp.context import CodexScientistMcpContext
from codex_scientist.profiles import get_profile_tool_names
from codex_scientist.runtime import schemas as native_schemas
from codex_scientist.runtime import tools as native_tools
from codex_scientist.services.manifest import ManifestService
from codex_scientist.services.method_improvement import MethodImprovementService
from codex_scientist.services.queue import QueueService
from codex_scientist.services.runner import RunnerService
from codex_scientist.services.trial import TrialService

_ENV_KEYS = (
    "CODEXSCIENTIST_PROJECT_ROOT",
    "CS_HOME",
    "CS_QUEST_ID",
    "CS_QUEST_ROOT",
    "CS_RUN_ID",
    "CS_ACTIVE_STAGE",
    "CS_CONVERSATION_ID",
    "CS_WORKTREE_ROOT",
)

MCP_ONLY_SCHEMAS: tuple[dict[str, Any], ...] = (
    native_schemas.CS_RECORD_NEGATIVE_RESULT,
    native_schemas.CS_UPDATE_METHOD_SCOREBOARD,
    native_schemas.CS_SELECT_NEXT_IDEA,
    native_schemas.CS_CLAIM_GATE,
)
SCHEMA_BY_NAME: dict[str, dict[str, Any]] = {schema["name"]: schema for schema in [*native_schemas.ALL_SCHEMAS, *MCP_ONLY_SCHEMAS]}
PUBLIC_SCHEMA_BY_NAME: dict[str, dict[str, Any]] = {schema["name"]: schema for schema in native_schemas.PUBLIC_SCHEMAS}
_TRIAL_ID_RE = re.compile(r"^T\d{4}$")


@contextmanager
def mcp_environment(args: dict[str, Any]) -> Iterator[CodexScientistMcpContext]:
    context = CodexScientistMcpContext.from_env(args)
    previous = {key: os.environ.get(key) for key in _ENV_KEYS}
    os.environ["CODEXSCIENTIST_PROJECT_ROOT"] = str(context.require_project_root())
    if context.home:
        os.environ["CS_HOME"] = str(context.home)
    if context.quest_id:
        os.environ["CS_QUEST_ID"] = context.quest_id
    if context.quest_root:
        os.environ["CS_QUEST_ROOT"] = str(context.quest_root)
    if context.run_id:
        os.environ["CS_RUN_ID"] = context.run_id
    if context.active_stage:
        os.environ["CS_ACTIVE_STAGE"] = context.active_stage
    if context.conversation_id:
        os.environ["CS_CONVERSATION_ID"] = context.conversation_id
    if context.worktree_root:
        os.environ["CS_WORKTREE_ROOT"] = str(context.worktree_root)
    try:
        yield context
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _finalize(payload: dict[str, Any], tool_name: str) -> dict[str, Any]:
    payload = normalize_envelope(payload)
    payload["transport"] = "codexscientist-mcp"
    payload["mcp"] = True
    payload["tool"] = tool_name
    return payload


def native_tool_call(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    with mcp_environment(args):
        handler = getattr(native_tools, tool_name)
        raw = handler(args)
    payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    return _finalize(payload, tool_name)


def _layout(args: dict[str, Any]):
    return CodexScientistMcpContext.from_env(args).resolve_project_layout()


def tool_schema(args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("name") or args.get("tool") or "").strip()
    if not name:
        return {"ok": False, "error": "Missing tool name", "error_type": "missing_argument", "recoverable": True}
    schema = SCHEMA_BY_NAME.get(name)
    if schema is None:
        return {"ok": False, "error": f"Unknown tool schema: {name}", "error_type": "unknown_tool", "recoverable": True}
    return {"ok": True, "schema": schema}


def goal_context(args: dict[str, Any]) -> dict[str, Any]:
    stage = str(args.get("active_stage") or args.get("stage") or os.environ.get("CS_ACTIVE_STAGE") or "scout").strip() or "scout"
    tools = list(get_profile_tool_names("goal", stage=stage))
    context = CodexScientistMcpContext.from_env(args)
    return {
        "ok": True,
        "profile": "goal",
        "active_stage": stage,
        "allowed_tools_for_stage": tools,
        "context": {
            "project_root": str(context.require_project_root()),
            "quest_id": context.quest_id,
            "quest_root": str(context.quest_root) if context.quest_root else None,
            "run_id": context.run_id,
            "conversation_id": context.conversation_id,
        },
    }


def submit_idea(args: dict[str, Any]) -> dict[str, Any]:
    context = CodexScientistMcpContext.from_env(args)
    layout = context.resolve_project_layout()
    service = MethodImprovementService(layout)
    quest_id = str(args.get("quest_id") or context.quest_id or "").strip()
    validation = service.validate_novelty_contract(args.get("novelty_contract"))
    if not validation.get("ok"):
        return validation
    contract = dict(validation["novelty_contract"])
    duplicate = service.duplicate_check(quest_id=quest_id, mechanism=str(contract.get("mechanism") or args.get("mechanism") or "")) if quest_id else {"decision": "allow", "similar_failed_ideas": []}
    if duplicate.get("decision") == "block_duplicate":
        return {
            "ok": False,
            "error": "Idea duplicates a recorded negative-memory mechanism",
            "error_type": "duplicate_negative_memory",
            "recoverable": True,
            "similar_failed_ideas": duplicate.get("similar_failed_ideas") or [],
        }
    call_args = dict(args)
    call_args.setdefault("mechanism", contract.get("mechanism"))
    call_args["selection_scores"] = contract["selection_scores"]
    payload = native_tool_call("cs_submit_idea", call_args)
    payload["novelty_contract"] = contract
    payload["method_scores"] = contract["selection_scores"]
    return payload


def record_main_experiment(args: dict[str, Any]) -> dict[str, Any]:
    payload = native_tool_call("cs_record_main_experiment", args)
    if not payload.get("ok", True):
        return payload
    return payload


def record_negative_result(args: dict[str, Any]) -> dict[str, Any]:
    context = CodexScientistMcpContext.from_env(args)
    quest_id = str(args.get("quest_id") or context.quest_id or "").strip()
    if not quest_id:
        return {"ok": False, "error": "quest_id is required", "error_type": "missing_argument", "recoverable": True}
    return MethodImprovementService(context.resolve_project_layout()).record_negative_result(
        quest_id=quest_id,
        trial_id=str(args.get("trial_id") or ""),
        idea_id=str(args.get("idea_id") or ""),
        failure_reason=str(args.get("failure_reason") or args.get("outcome") or "negative"),
        lesson=str(args.get("lesson") or args.get("mechanism") or "negative outcome"),
        mechanism=str(args.get("mechanism") or ""),
    )


def update_method_scoreboard(args: dict[str, Any]) -> dict[str, Any]:
    context = CodexScientistMcpContext.from_env(args)
    quest_id = str(args.get("quest_id") or context.quest_id or "").strip()
    if not quest_id:
        return {"ok": False, "error": "quest_id is required", "error_type": "missing_argument", "recoverable": True}
    service = MethodImprovementService(context.resolve_project_layout())
    payload = service.update_scoreboard(
        quest_id=quest_id,
        idea_id=str(args.get("idea_id") or args.get("run_id") or "unknown"),
        outcome=str(args.get("outcome") or "unknown"),
        metric_delta=float(args.get("metric_delta") or 0.0),
        lesson=str(args.get("lesson") or ""),
        mechanism=str(args.get("mechanism") or ""),
    )
    return payload


def select_next_idea(args: dict[str, Any]) -> dict[str, Any]:
    context = CodexScientistMcpContext.from_env(args)
    quest_id = str(args.get("quest_id") or context.quest_id or "").strip()
    if not quest_id:
        return {"ok": False, "error": "quest_id is required", "error_type": "missing_argument", "recoverable": True}
    return MethodImprovementService(context.resolve_project_layout()).select_next_idea(quest_id=quest_id)


def claim_gate(args: dict[str, Any]) -> dict[str, Any]:
    context = CodexScientistMcpContext.from_env(args)
    quest_id = str(args.get("quest_id") or context.quest_id or "").strip()
    if not quest_id:
        return {"ok": False, "error": "quest_id is required", "error_type": "missing_argument", "recoverable": True}
    return MethodImprovementService(context.resolve_project_layout()).claim_gate(
        quest_id=quest_id,
        claim_id=str(args.get("claim_id") or "claim"),
        claim_text=str(args.get("claim_text") or args.get("text") or ""),
        baseline_id=str(args.get("baseline_id") or "").strip() or None,
        metric_contract=str(args.get("metric_contract") or "").strip() or None,
        evidence_paths=list(args.get("evidence_paths") or args.get("artifact_paths") or []),
        analysis_slice_ids=list(args.get("analysis_slice_ids") or []),
        seed_count=int(args.get("seed_count") or 0),
    )


def manifest_init(args: dict[str, Any]) -> dict[str, Any]:
    with mcp_environment(args) as context:
        service = ManifestService(context.resolve_project_layout())
        return service.init(
            name=str(args.get("name") or args.get("project_name") or "CodexScientist"),
            goal=str(args.get("goal") or ""),
            overwrite=bool(args.get("overwrite")),
        )


def manifest_record_baseline(args: dict[str, Any]) -> dict[str, Any]:
    with mcp_environment(args) as context:
        service = ManifestService(context.resolve_project_layout())
        return service.record_baseline(
            baseline_id=str(args.get("baseline_id") or "baseline"),
            status=str(args.get("status") or "confirmed"),
            metric_contract=str(args.get("metric_contract") or "primary"),
            waiver_reason=args.get("waiver_reason"),
            artifact_requirements=list(args.get("artifact_requirements") or []),
        )


def queue_submit(args: dict[str, Any]) -> dict[str, Any]:
    with mcp_environment(args) as context:
        return QueueService(context.resolve_project_layout()).submit(
            job_id=str(args.get("job_id") or "job"),
            command=str(args.get("command") or ""),
            max_attempts=int(args.get("max_attempts") or 3),
            retry_policy=str(args.get("retry_policy") or "oom_or_transient"),
            resource=args.get("resource") if isinstance(args.get("resource"), dict) else None,
            quest_id=str(args.get("quest_id") or context.quest_id or "").strip() or None,
        )


def queue_start_attempt(args: dict[str, Any]) -> dict[str, Any]:
    with mcp_environment(args) as context:
        runner = RunnerService(context.resolve_project_layout())
        return QueueService(context.resolve_project_layout()).start_attempt(
            str(args.get("job_id") or ""),
            runner=runner,
            worker_id=str(args.get("worker_id") or "mcp") or None,
            expected_outputs=list(args.get("expected_outputs") or []),
            dry_run=bool(args.get("dry_run")),
        )


def runner_start(args: dict[str, Any]) -> dict[str, Any]:
    with mcp_environment(args) as context:
        return RunnerService(context.resolve_project_layout()).start(
            command=str(args.get("command") or ""),
            job_id=str(args.get("job_id") or "").strip() or None,
            dry_run=bool(args.get("dry_run")),
            quest_id=str(args.get("quest_id") or context.quest_id or "").strip() or None,
        )


def trial_propose(args: dict[str, Any]) -> dict[str, Any]:
    with mcp_environment(args) as context:
        trial = TrialService(context.resolve_project_layout()).propose(
            quest_id=str(args.get("quest_id") or context.quest_id or "Q1"),
            idea_id=str(args.get("idea_id") or "I1"),
            hypothesis=str(args.get("hypothesis") or ""),
            mechanism=str(args.get("mechanism") or ""),
        )
        return {"ok": True, "trial": trial}


def _trial_id_contract_error(error_type: str, trial_id: str = "") -> dict[str, Any]:
    if error_type == "missing_argument":
        return {
            "ok": False,
            "error": "Missing trial_id",
            "error_type": "missing_argument",
            "recoverable": True,
            "missing_context_keys": ["trial_id"],
            "required_context_keys": ["trial_id"],
            "retry_template": {"name": "cs_trial_show", "required_arguments": ["trial_id"], "missing_arguments": ["trial_id"]},
            "suggested_next_action": "Provide trial_id for cs_trial_show, or call cs_trial_propose to create a new trial.",
        }
    if error_type == "invalid_trial_id":
        return {
            "ok": False,
            "error": f"Invalid trial_id: {trial_id}",
            "error_type": "invalid_trial_id",
            "recoverable": True,
            "required_context_keys": ["trial_id"],
            "retry_template": {"name": "cs_trial_show", "required_arguments": ["trial_id"], "missing_arguments": []},
            "suggested_next_action": "Retry cs_trial_show with a trial_id formatted like T0001, or call cs_trial_propose to create a new trial.",
        }
    return {
        "ok": False,
        "error": f"Trial not found: {trial_id}",
        "error_type": "not_found",
        "recoverable": True,
        "required_context_keys": ["trial_id"],
        "retry_template": {
            "name": "cs_trial_propose",
            "required_arguments": ["quest_id", "idea_id", "hypothesis"],
            "missing_arguments": "required_arguments minus keys already present in args",
        },
        "suggested_next_action": "Use cs_trial_show to verify an existing trial_id, or call cs_trial_propose to create a new trial.",
    }


def _validate_trial_id_for_action(args: dict[str, Any], service: TrialService) -> tuple[str, dict[str, Any] | None]:
    trial_id = str(args.get("trial_id") or "").strip()
    if not trial_id:
        return trial_id, _trial_id_contract_error("missing_argument")
    if not _TRIAL_ID_RE.fullmatch(trial_id):
        return trial_id, _trial_id_contract_error("invalid_trial_id", trial_id)
    try:
        service.get(trial_id)
    except FileNotFoundError:
        return trial_id, _trial_id_contract_error("not_found", trial_id)
    return trial_id, None


def _trial_call(args: dict[str, Any], method: str) -> dict[str, Any]:
    with mcp_environment(args) as context:
        service = TrialService(context.resolve_project_layout())
        trial_id, error = _validate_trial_id_for_action(args, service)
        if error is not None:
            return error
        if method == "plan":
            return service.plan(
                trial_id,
                metric_contract_id=str(args.get("metric_contract_id") or "primary"),
                novelty_decision=str(args.get("novelty_decision") or "pending"),
            )
        if method == "ready":
            return service.ready(trial_id)
        if method == "evaluate":
            return service.evaluate(
                trial_id,
                metric_values=dict(args.get("metric_values") or {}),
                artifacts=list(args.get("artifacts") or []),
            )
        if method == "decide":
            return service.decide(
                trial_id,
                decision=str(args.get("decision") or "revert"),
                reviewer_verdict=str(args.get("reviewer_verdict") or "").strip() or None,
            )
    return {"ok": False, "error": f"Unknown trial method: {method}", "error_type": "unknown_method", "recoverable": True}


def trial_plan(args: dict[str, Any]) -> dict[str, Any]:
    return _trial_call(args, "plan")


def trial_ready(args: dict[str, Any]) -> dict[str, Any]:
    return _trial_call(args, "ready")


def trial_evaluate(args: dict[str, Any]) -> dict[str, Any]:
    return _trial_call(args, "evaluate")


def trial_decide(args: dict[str, Any]) -> dict[str, Any]:
    return _trial_call(args, "decide")


def native_handler(tool_name: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    return lambda args: native_tool_call(tool_name, args)
