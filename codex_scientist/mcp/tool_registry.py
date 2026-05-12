"""Curated MCP tool registry for CodexScientist."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from codex_scientist.mcp import goal_context, research_tools
from codex_scientist.mcp.envelope import apply_budget_envelope
from codex_scientist.mcp.skill_index import load_skill, search_skills
from codex_scientist.profiles import (
    DEFAULT_PROFILE_NAME,
    STAGE_ALIASES,
    STAGE_TOOL_ADDITIONS,
    get_profile,
    get_profile_tool_names,
    normalize_stage,
)
from codex_scientist.services.artifacts import ArtifactIndexService
from codex_scientist.services.checkpoint import CheckpointService
from codex_scientist.services.context_pack import ContextPackService
from codex_scientist.services.costs import CostApprovalService
from codex_scientist.services.manifest import ManifestService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.progress_watchdog import ProgressWatchdogService
from codex_scientist.services.queue import QueueService
from codex_scientist.services.research_wiki import ResearchWikiService
from codex_scientist.services.review import ReviewService
from codex_scientist.services.resume import ResumeService
from codex_scientist.services.runner import RunnerService
from codex_scientist.services.soak import SoakService
from codex_scientist.services.trial import TrialService

_TRIAL_ID_RE = re.compile(r"^T\d{4}$")
_RUN_ID_RE = re.compile(r"^R\d{4}$")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    group: str = "core"
    read_only: bool = True
    destructive: bool = False
    idempotent: bool = True
    open_world: bool = False
    required_context_keys: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["required_context_keys"] = list(self.required_context_keys)
        data["inputSchema"] = {"type": "object", "additionalProperties": True}
        data["annotations"] = {
            "readOnlyHint": self.read_only,
            "destructiveHint": self.destructive,
            "idempotentHint": self.idempotent,
            "openWorldHint": self.open_world,
        }
        return data


def _layout(args: dict[str, Any]) -> ProjectLayout:
    project = Path(args.get("project") or ".").expanduser().resolve()
    return ProjectLayout.from_project_root(project)


def _simple_status(args: dict[str, Any]) -> dict[str, Any]:
    project = Path(args.get("project") or ".").resolve()
    state_root = project / "CodexScientist"
    return {
        "ok": True,
        "transport": "codexscientist-mcp",
        "mcp": True,
        "tool": "cs_status",
        "project": str(project),
        "state_root": str(state_root),
        "state_root_exists": state_root.exists(),
    }


def _manifest_validate(args: dict[str, Any]) -> dict[str, Any]:
    payload = ManifestService(_layout(args)).validate()
    payload.pop("manifest", None)
    return payload


def _queue_status(args: dict[str, Any]) -> dict[str, Any]:
    payload = QueueService(_layout(args)).status()
    limit = max(1, min(int(args.get("limit") or 50), 200))
    jobs = payload.get("jobs") if isinstance(payload.get("jobs"), dict) else {}
    if len(jobs) > limit:
        payload["jobs"] = dict(list(jobs.items())[:limit])
        payload["truncated"] = True
    return payload


def _queue_reconcile(args: dict[str, Any]) -> dict[str, Any]:
    return QueueService(_layout(args)).reconcile_expired_leases()


def _runner_status(args: dict[str, Any]) -> dict[str, Any]:
    service = RunnerService(_layout(args))
    run_id = str(args.get("run_id") or "")
    if run_id:
        if not _RUN_ID_RE.fullmatch(run_id):
            return {"ok": False, "error": "Invalid run_id", "error_type": "invalid_run_id", "recoverable": True}
        try:
            return {"ok": True, "run": service.get(run_id)}
        except FileNotFoundError:
            return {"ok": False, "error": f"Run not found: {run_id}", "error_type": "not_found", "recoverable": True}
    return {"ok": True, "runs": service.list_runs()}


def _log_digest(args: dict[str, Any]) -> dict[str, Any]:
    run_id = str(args.get("run_id") or "")
    if not _RUN_ID_RE.fullmatch(run_id):
        return {"ok": False, "error": "Invalid run_id", "error_type": "invalid_run_id", "recoverable": True}
    try:
        return RunnerService(_layout(args)).log_digest(
            run_id,
            max_tail_lines=max(0, min(int(args.get("max_tail_lines") or 40), 200)),
        )
    except FileNotFoundError:
        return {"ok": False, "error": f"Run not found: {run_id}", "error_type": "not_found", "recoverable": True}


def _artifact_index(args: dict[str, Any]) -> dict[str, Any]:
    return ArtifactIndexService(_layout(args)).index(max_items=max(1, min(int(args.get("max_items") or 50), 500)))


def _context_pack(args: dict[str, Any]) -> dict[str, Any]:
    max_chars = max(200, min(int(args.get("max_chars") or 4000), 12000))
    return ContextPackService(_layout(args)).write_context_pack(max_chars=max_chars, quest_id=str(args.get("quest_id") or "").strip() or None)


def _resume_brief(args: dict[str, Any]) -> dict[str, Any]:
    max_chars = max(120, min(int(args.get("max_chars") or 8000), 24000))
    include_recent_events = max(0, min(int(args.get("include_recent_events") or 5), 50))
    include_risks = bool(args.get("include_risks", True))
    return ResumeService(_layout(args)).resume_brief(
        max_chars=max_chars,
        include_recent_events=include_recent_events,
        include_risks=include_risks,
        quest_id=str(args.get("quest_id") or "").strip() or None,
    )


def _checkpoint(args: dict[str, Any]) -> dict[str, Any]:
    layout = _layout(args)
    payload = CheckpointService(layout).create_checkpoint(
        phase=str(args.get("phase") or "unknown"),
        completed=list(args.get("completed") or []),
        decisions=list(args.get("decisions") or []),
        validation=list(args.get("validation") or []),
        next_action=str(args.get("next_action") or ""),
        artifact_refs=list(args.get("artifact_refs") or []),
        risk_flags=list(args.get("risk_flags") or []),
        idempotency_key=args.get("idempotency_key"),
    )
    quest_id = str(args.get("quest_id") or "").strip()
    if quest_id and payload.get("ok"):
        payload.update(ProgressWatchdogService(layout).reset_after_checkpoint(quest_id=quest_id, checkpoint=payload))
    return payload


def _goal_watchdog(args: dict[str, Any]) -> dict[str, Any]:
    quest_id = str(args.get("quest_id") or "").strip()
    if not quest_id:
        return {"ok": False, "error": "quest_id is required", "error_type": "missing_argument", "recoverable": True}
    raw_timeout = args.get("timeout_seconds")
    timeout_seconds = 1800 if raw_timeout in {None, ""} else max(0, min(int(raw_timeout), 604800))
    return ProgressWatchdogService(_layout(args)).reconcile_goal_runtime(quest_id=quest_id, timeout_seconds=timeout_seconds)


def _pack_delta(args: dict[str, Any]) -> dict[str, Any]:
    raw_seq = args.get("since_event_seq")
    since_event_seq = int(raw_seq) if raw_seq not in {None, ""} else None
    return ResumeService(_layout(args)).pack_delta(
        since_event_seq=since_event_seq,
        since_checkpoint_id=args.get("since_checkpoint_id"),
        max_chars=max(120, min(int(args.get("max_chars") or 6000), 24000)),
    )


def _trial_show(args: dict[str, Any]) -> dict[str, Any]:
    trial_id = str(args.get("trial_id") or "")
    if not trial_id:
        return {"ok": False, "error": "Missing trial_id", "error_type": "missing_argument", "recoverable": True}
    if not _TRIAL_ID_RE.fullmatch(trial_id):
        return {"ok": False, "error": "Invalid trial_id", "error_type": "invalid_trial_id", "recoverable": True}
    try:
        return {"ok": True, "trial": TrialService(_layout(args)).get(trial_id)}
    except FileNotFoundError:
        return {"ok": False, "error": f"Trial not found: {trial_id}", "error_type": "not_found", "recoverable": True}


def _wiki_query_pack(args: dict[str, Any]) -> dict[str, Any]:
    max_chars = max(200, min(int(args.get("max_chars") or args.get("limit") or 4000), 12000))
    return ResearchWikiService(_layout(args)).query_pack(max_chars=max_chars)


def _review_status(args: dict[str, Any]) -> dict[str, Any]:
    return ReviewService(_layout(args)).status()


def _cost_status(args: dict[str, Any]) -> dict[str, Any]:
    daily_cap = float(args.get("daily_cap_usd") or 0.0)
    return CostApprovalService(_layout(args), daily_cap_usd=daily_cap).status()


def _soak_accelerated(args: dict[str, Any]) -> dict[str, Any]:
    try:
        days = max(1, min(int(args.get("days") or 10), 30))
    except (TypeError, ValueError):
        return {"ok": False, "error": "days must be an integer", "error_type": "invalid_argument", "recoverable": True}
    return SoakService(_layout(args)).run_accelerated(days=days, inject_failures=bool(args.get("inject_failures")))


def _soak_crash_resume(args: dict[str, Any]) -> dict[str, Any]:
    restart_label = str(args.get("restart_label") or "mcp-restart")
    return SoakService(_layout(args)).crash_resume_smoke(restart_label=restart_label)


def _schema_description(name: str, fallback: str) -> str:
    schema = research_tools.PUBLIC_SCHEMA_BY_NAME.get(name) or research_tools.SCHEMA_BY_NAME.get(name) or {}
    return str(schema.get("description") or fallback)


def _spec(name: str, fallback: str, *, group: str, read_only: bool = True, idempotent: bool = True, required: tuple[str, ...] = ()) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=_schema_description(name, fallback),
        group=group,
        read_only=read_only,
        idempotent=idempotent,
        required_context_keys=required,
    )


_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "cs_doctor": research_tools.native_handler("cs_doctor"),
    "cs_status": _simple_status,
    "cs_goal_context": goal_context.goal_context,
    "cs_goal_state": goal_context.goal_state,
    "cs_goal_next_action": goal_context.goal_next_action,
    "cs_tool_schema": research_tools.tool_schema,
    "cs_get_quest_state": research_tools.native_handler("cs_get_quest_state"),
    "cs_set_active_quest": research_tools.native_handler("cs_set_active_quest"),
    "cs_context_pack": _context_pack,
    "cs_resume_brief": _resume_brief,
    "cs_checkpoint": _checkpoint,
    "cs_goal_watchdog": _goal_watchdog,
    "cs_pack_delta": _pack_delta,
    "cs_manifest_init": research_tools.manifest_init,
    "cs_manifest_record_baseline": research_tools.manifest_record_baseline,
    "cs_manifest_validate": _manifest_validate,
    "cs_queue_submit": research_tools.queue_submit,
    "cs_queue_start_attempt": research_tools.queue_start_attempt,
    "cs_queue_status": _queue_status,
    "cs_queue_reconcile": _queue_reconcile,
    "cs_runner_start": research_tools.runner_start,
    "cs_runner_status": _runner_status,
    "cs_log_digest": _log_digest,
    "cs_artifact_index": _artifact_index,
    "cs_trial_propose": research_tools.trial_propose,
    "cs_trial_plan": research_tools.trial_plan,
    "cs_trial_ready": research_tools.trial_ready,
    "cs_trial_evaluate": research_tools.trial_evaluate,
    "cs_trial_decide": research_tools.trial_decide,
    "cs_trial_show": _trial_show,
    "cs_wiki_query_pack": _wiki_query_pack,
    "cs_review_status": _review_status,
    "cs_cost_status": _cost_status,
    "cs_soak_accelerated": _soak_accelerated,
    "cs_soak_crash_resume": _soak_crash_resume,
    "cs_skill_search": search_skills,
    "cs_skill_load": load_skill,
}

for _native_name in [
    "cs_new_quest",
    "cs_record_user_requirement",
    "cs_memory_search",
    "cs_memory_write",
    "cs_artifact_record",
    "cs_create_local_baseline",
    "cs_confirm_baseline",
    "cs_submit_idea",
    "cs_get_method_scoreboard",
    "cs_get_optimization_frontier",
    "cs_record_main_experiment",
    "cs_create_analysis_campaign",
    "cs_get_analysis_campaign",
    "cs_record_analysis_slice",
    "cs_bash_exec",
    "cs_submit_paper_outline",
    "cs_submit_paper_bundle",
    "cs_refresh_summary",
    "cs_paper_fetch",
]:
    _HANDLERS[_native_name] = research_tools.native_handler(_native_name)

_HANDLERS["cs_submit_idea"] = research_tools.submit_idea
_HANDLERS["cs_record_main_experiment"] = research_tools.record_main_experiment
_HANDLERS["cs_record_negative_result"] = research_tools.record_negative_result
_HANDLERS["cs_update_method_scoreboard"] = research_tools.update_method_scoreboard
_HANDLERS["cs_select_next_idea"] = research_tools.select_next_idea
_HANDLERS["cs_claim_gate"] = research_tools.claim_gate

_SPECS: list[ToolSpec] = [
    _spec("cs_doctor", "Run CodexScientist diagnostics.", group="core", read_only=False),
    _spec("cs_status", "Return a compact CodexScientist project status snapshot.", group="core"),
    _spec("cs_goal_context", "Return active-only Codex goal context for the current quest stage.", group="goal", required=("quest_id",)),
    _spec("cs_goal_state", "Read or update project-local Codex goal loop state.", group="goal", read_only=False, required=("quest_id",)),
    _spec("cs_goal_next_action", "Return the machine-readable next goal gate action.", group="goal", required=("quest_id",)),
    _spec("cs_tool_schema", "Return full schema for one MCP tool on demand.", group="schema"),
    _spec("cs_get_quest_state", "Read compact or full state for a quest.", group="quest", required=("quest_id",)),
    _spec("cs_set_active_quest", "Set the active quest for this session.", group="quest", read_only=False, required=("quest_id",)),
    _spec("cs_context_pack", "Generate or read a bounded context pack.", group="checkpoint", read_only=False),
    _spec("cs_resume_brief", "Return stable low-token recovery anchors for a project.", group="checkpoint"),
    _spec("cs_checkpoint", "Persist a compact project-local recovery checkpoint.", group="checkpoint", read_only=False, idempotent=False),
    _spec("cs_goal_watchdog", "Reconcile goal progress, stuck runners, and checkpoint pressure.", group="checkpoint", read_only=False, required=("quest_id",)),
    _spec("cs_pack_delta", "Return event deltas since an event sequence or checkpoint.", group="checkpoint"),
    _spec("cs_skill_search", "Search local CodexScientist skills and return short candidate cards.", group="skill"),
    _spec("cs_skill_load", "Load a bounded view of one indexed CodexScientist skill.", group="skill"),
    _spec("cs_new_quest", "Create a new quest natively.", group="quest", read_only=False, idempotent=False, required=("goal",)),
    _spec("cs_record_user_requirement", "Record a durable user requirement.", group="quest", read_only=False, idempotent=False, required=("message",)),
    _spec("cs_memory_search", "Search memory cards.", group="memory", required=("query",)),
    _spec("cs_memory_write", "Write a memory card.", group="memory", read_only=False, idempotent=False, required=("title",)),
    _spec("cs_artifact_record", "Record a generic artifact.", group="artifact", read_only=False, idempotent=False, required=("quest_id",)),
    _spec("cs_create_local_baseline", "Create a local baseline stub.", group="baseline", read_only=False, idempotent=False, required=("quest_id", "baseline_id")),
    _spec("cs_confirm_baseline", "Confirm a baseline gate.", group="baseline", read_only=False, idempotent=False, required=("quest_id", "baseline_path")),
    _spec("cs_submit_idea", "Submit or revise an idea candidate with a novelty contract.", group="idea", read_only=False, idempotent=False, required=("quest_id", "title", "novelty_contract")),
    _spec("cs_get_method_scoreboard", "Read or refresh the method scoreboard.", group="idea", read_only=False, required=("quest_id",)),
    _spec("cs_get_optimization_frontier", "Read optimization frontier summary.", group="idea", required=("quest_id",)),
    _spec("cs_record_negative_result", "Record a negative method result into quest method memory.", group="idea", read_only=False, idempotent=False, required=("quest_id", "idea_id")),
    _spec("cs_update_method_scoreboard", "Update method improvement scoreboard and frontier after an experiment.", group="idea", read_only=False, idempotent=False, required=("quest_id", "idea_id")),
    _spec("cs_select_next_idea", "Select the next non-duplicate idea candidate from the frontier.", group="idea", read_only=False, required=("quest_id",)),
    _spec("cs_claim_gate", "Check whether a paper-facing claim has enough baseline, metric, evidence, analysis, and seed support.", group="analysis", read_only=False, idempotent=False, required=("quest_id", "claim_id")),
    _spec("cs_record_main_experiment", "Record a main experiment run.", group="experiment", read_only=False, idempotent=False, required=("quest_id", "run_id")),
    _spec("cs_create_analysis_campaign", "Create an analysis campaign.", group="analysis", read_only=False, idempotent=False, required=("quest_id", "campaign_title", "campaign_goal", "slices")),
    _spec("cs_get_analysis_campaign", "Read analysis campaign state.", group="analysis", required=("quest_id",)),
    _spec("cs_record_analysis_slice", "Record an analysis slice result.", group="analysis", read_only=False, idempotent=False, required=("quest_id", "campaign_id", "slice_id")),
    _spec("cs_bash_exec", "Run/list/read/wait/stop quest-local bash sessions.", group="experiment", read_only=False, idempotent=False, required=("quest_id",)),
    _spec("cs_submit_paper_outline", "Submit/select/revise a paper outline.", group="paper", read_only=False, idempotent=False, required=("quest_id",)),
    _spec("cs_submit_paper_bundle", "Submit a paper bundle manifest.", group="paper", read_only=False, idempotent=False, required=("quest_id",)),
    _spec("cs_refresh_summary", "Refresh SUMMARY.md from recent state.", group="paper", read_only=False, idempotent=False, required=("quest_id",)),
    _spec("cs_paper_fetch", "Fetch official paper PDF into the quest library.", group="paper", read_only=False, idempotent=False, required=("quest_id",)),
    _spec("cs_manifest_init", "Initialize a project-local research manifest.", group="manifest", read_only=False, idempotent=False, required=("name", "goal")),
    _spec("cs_manifest_record_baseline", "Record manifest baseline readiness.", group="manifest", read_only=False, idempotent=False, required=("baseline_id",)),
    _spec("cs_manifest_validate", "Validate the project-local research manifest.", group="manifest", read_only=False),
    _spec("cs_queue_submit", "Submit a local runner queue job.", group="queue", read_only=False, idempotent=False, required=("job_id", "command")),
    _spec("cs_queue_start_attempt", "Start a queued job attempt.", group="queue", read_only=False, idempotent=False, required=("job_id",)),
    _spec("cs_queue_status", "Read queue status.", group="queue"),
    _spec("cs_queue_reconcile", "Reconcile expired queue leases.", group="queue", read_only=False),
    _spec("cs_runner_start", "Start or dry-run a project-local runner record.", group="runner", read_only=False, idempotent=False, required=("command",)),
    _spec("cs_runner_status", "Read one or all runner records.", group="runner"),
    _spec("cs_log_digest", "Return a bounded redacted digest for one runner log.", group="runner", required=("run_id",)),
    _spec("cs_artifact_index", "Return artifact references, hashes, sizes, and types without file content.", group="artifact"),
    _spec("cs_trial_propose", "Propose a trial.", group="trial", read_only=False, idempotent=False, required=("quest_id", "idea_id", "hypothesis")),
    _spec("cs_trial_plan", "Plan a proposed trial.", group="trial", read_only=False, idempotent=False, required=("trial_id",)),
    _spec("cs_trial_ready", "Move a planned trial through readiness gates.", group="trial", read_only=False, idempotent=False, required=("trial_id",)),
    _spec("cs_trial_evaluate", "Evaluate a ready trial against metric contracts.", group="trial", read_only=False, idempotent=False, required=("trial_id",)),
    _spec("cs_trial_decide", "Keep or revert an evaluated trial.", group="trial", read_only=False, idempotent=False, required=("trial_id",)),
    _spec("cs_trial_show", "Read one trial record by id.", group="trial", required=("trial_id",)),
    _spec("cs_wiki_query_pack", "Build a bounded research wiki query pack.", group="wiki"),
    _spec("cs_review_status", "Read review artifact status.", group="review"),
    _spec("cs_cost_status", "Read latest cost and approval gate status.", group="cost"),
    _spec("cs_soak_accelerated", "Run accelerated fake-clock long-run validation.", group="soak", read_only=False, idempotent=False),
    _spec("cs_soak_crash_resume", "Record restart and reconcile expired leases.", group="soak", read_only=False, idempotent=False),
]

_SPECS_BY_NAME = {spec.name: spec for spec in _SPECS}
_STRICT_REQUIRED_ARG_TOOLS = frozenset(
    {
        "cs_manifest_init",
        "cs_manifest_record_baseline",
        "cs_queue_submit",
        "cs_runner_start",
        "cs_trial_propose",
        "cs_trial_plan",
        "cs_trial_ready",
        "cs_trial_evaluate",
        "cs_trial_decide",
        "cs_create_analysis_campaign",
    }
)


def _is_missing_arg(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _known_project_and_quest_args(args: dict[str, Any]) -> dict[str, Any]:
    known: dict[str, Any] = {}
    for key in ("project", "quest_id"):
        value = args.get(key)
        if not _is_missing_arg(value):
            known[key] = value
    return known


def _known_args(args: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: args[key] for key in keys if key in args and not _is_missing_arg(args.get(key))}


def _default_error_action(error_type: str) -> str:
    if error_type == "missing_argument":
        return "Retry the same MCP tool with the listed missing arguments."
    if error_type == "invalid_argument":
        return "Retry the same MCP tool with corrected argument values."
    if error_type == "not_found":
        return "Create or select the missing MCP resource, then retry the same MCP tool."
    if error_type == "unknown_tool":
        return "Call tools/list and choose one of the curated cs_* tools."
    if error_type in {"unknown_profile", "profile_not_registered_for_mcp"}:
        return "Retry tools/list with the core or goal MCP profile."
    if error_type == "unknown_stage":
        return "Retry tools/list with one allowed stage or omit stage for the full goal profile."
    if error_type == "gate_blocked":
        return "Satisfy the reported gate requirements before retrying."
    if error_type == "external_io_failed":
        return "Check the referenced external resource or local file path, then retry."
    return "Inspect the MCP error details and retry after correcting the underlying issue."


def _error_payload(error_type: str, error: str, recoverable: bool, tool_name: str | None = None, **extra: Any) -> dict[str, Any]:
    payload = {"ok": False, "error": str(error), "error_type": error_type, "recoverable": recoverable, **extra}
    if tool_name is not None:
        payload.setdefault("tool", tool_name)
    if error_type == "gate_blocked":
        payload.setdefault("error_family", "gate_blocked")
    if recoverable and not (payload.get("suggested_next_action") or payload.get("next_call") or payload.get("retry_template")):
        payload["suggested_next_action"] = _default_error_action(error_type)
    if not recoverable and not payload.get("suggested_next_action"):
        payload["suggested_next_action"] = "No automatic recovery is available for this MCP error."
    return payload


def _analysis_campaign_retry_template(args: dict[str, Any]) -> dict[str, Any]:
    required = ["quest_id", "campaign_title", "campaign_goal", "slices"]
    return {
        "name": "cs_create_analysis_campaign",
        "required_arguments": required,
        "missing_arguments": [key for key in required if _is_missing_arg(args.get(key))],
        "known_arguments": _known_args(args, required),
    }


def _value_error_type(message: str) -> str:
    lowered = message.lower()
    not_found_markers = ("no active", "not found", "unknown quest", "does not exist", "missing active")
    return "not_found" if any(marker in lowered for marker in not_found_markers) else "invalid_argument"


def _normalized_failure_payload(payload: dict[str, Any], *, tool_name: str | None, args: dict[str, Any] | None = None) -> dict[str, Any]:
    if payload.get("ok", True):
        return payload
    call_args = dict(args or {})
    current = dict(payload)
    original_type = str(current.get("error_type") or "").strip()
    error = str(current.get("error") or f"{tool_name or 'MCP tool'} failed")
    if original_type in {"FileNotFoundError", "NotADirectoryError"}:
        error_type = "not_found"
        recoverable = True
    elif original_type == "ValueError":
        error_type = _value_error_type(error)
        recoverable = True
    elif original_type == "claim_gate_blocked":
        error_type = original_type
        recoverable = True
        current.setdefault("error_family", "gate_blocked")
    elif original_type in {"", "error"} and error.lower().startswith("missing required"):
        error_type = "missing_argument"
        recoverable = True
    elif original_type == "not_implemented":
        error_type = "internal_error"
        recoverable = True
    else:
        error_type = original_type or "internal_error"
        recoverable = bool(current.get("recoverable", True))
    current["error_type"] = error_type
    current["recoverable"] = recoverable
    current.setdefault("error", error)
    if error_type == "not_found" and tool_name == "cs_get_analysis_campaign":
        current.setdefault("retry_template", _analysis_campaign_retry_template(call_args))
    if recoverable and not (current.get("suggested_next_action") or current.get("next_call") or current.get("retry_template")):
        current["suggested_next_action"] = _default_error_action(error_type)
    return current


def _missing_argument_payload(name: str, spec: ToolSpec, missing: list[str], args: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "error": f"Missing required MCP argument(s): {', '.join(missing)}",
        "error_type": "missing_argument",
        "recoverable": True,
        "missing_context_keys": missing,
        "required_context_keys": list(spec.required_context_keys),
        "suggested_next_action": "Retry the same MCP tool with the listed missing arguments; do not switch to CLI.",
        "retry_template": {
            "name": name,
            "required_arguments": list(spec.required_context_keys),
            "missing_arguments": missing,
            "known_arguments": _known_project_and_quest_args(args),
        },
    }


def _validate_required_args(name: str, args: dict[str, Any], spec: ToolSpec) -> dict[str, Any] | None:
    if name not in _STRICT_REQUIRED_ARG_TOOLS:
        return None
    missing = [key for key in spec.required_context_keys if _is_missing_arg(args.get(key))]
    if not missing:
        return None
    return _missing_argument_payload(name, spec, missing, args)


def _bash_exec_preflight(args: dict[str, Any]) -> dict[str, Any] | None:
    operation = str(args.get("operation") or ("run" if args.get("command") else "list")).strip().lower()
    if operation == "run" and _is_missing_arg(args.get("command")):
        spec = _SPECS_BY_NAME["cs_bash_exec"]
        return _missing_argument_payload("cs_bash_exec", spec, ["command"], args)
    if operation == "list" and _is_missing_arg(args.get("command")):
        quest_id = str(args.get("quest_id") or "").strip()
        if quest_id and not (_layout(args).quest_root_for(quest_id) / "quest.yaml").exists():
            return {"ok": True, "quest_id": quest_id, "sessions": [], "summary": {"session_count": 0}}
    return None


def list_tool_specs(profile: str | None = None, stage: str | None = None) -> list[ToolSpec]:
    profile_name = profile or DEFAULT_PROFILE_NAME
    names = get_profile_tool_names(profile_name, stage=stage)
    return [spec for name in names if (spec := _SPECS_BY_NAME.get(name)) is not None]


def tools_list_payload(args: dict[str, Any] | None = None) -> dict[str, Any]:
    payload_args = dict(args or {})
    profile = str(payload_args.get("profile") or DEFAULT_PROFILE_NAME).strip() or DEFAULT_PROFILE_NAME
    stage = str(payload_args.get("stage") or payload_args.get("active_stage") or "").strip() or None
    try:
        profile_obj = get_profile(profile)
    except KeyError as exc:
        return _finalize_tool_payload(
            _error_payload("unknown_profile", str(exc), True, "tools/list", profile=profile),
            tool_name="tools/list",
            args=payload_args,
        )
    if not profile_obj.registers_mcp:
        return _finalize_tool_payload(
            _error_payload(
                "profile_not_registered_for_mcp",
                f"Profile is not registered for default MCP: {profile}",
                True,
                "tools/list",
                profile=profile,
                suggested_next_action="Use core or goal MCP profile. Hidden admin/debug CLI remains outside default MCP.",
            ),
            tool_name="tools/list",
            args=payload_args,
        )
    warnings: list[str] = []
    if stage and profile_obj.name == "goal":
        normalized_stage, stage_ok = normalize_stage(stage)
        if not stage_ok:
            return _finalize_tool_payload(
                _error_payload(
                    "unknown_stage",
                    f"Unknown CodexScientist goal stage: {stage}",
                    True,
                    "tools/list",
                    profile=profile,
                    stage=stage,
                    allowed_stages=sorted(STAGE_TOOL_ADDITIONS),
                    stage_aliases=dict(STAGE_ALIASES),
                    suggested_next_action="Retry tools/list with one allowed stage or omit stage for the full goal profile.",
                ),
                tool_name="tools/list",
                args=payload_args,
            )
        stage = normalized_stage
    elif stage and profile_obj.name == "core":
        warnings.append("ignored_stage_for_core_profile")
    specs = list_tool_specs(profile, stage)
    return apply_budget_envelope(
        {
            "ok": True,
            "server": "codexscientist_mcp",
            "profile": profile,
            "stage": stage,
            "compact": True,
            "tools": [spec.as_dict() for spec in specs],
            "warnings": warnings,
        },
        tool_name="tools/list",
    )


def _finalize_tool_payload(payload: dict[str, Any], *, tool_name: str | None = None, args: dict[str, Any] | None = None) -> dict[str, Any]:
    return apply_budget_envelope(_normalized_failure_payload(payload, tool_name=tool_name, args=args), tool_name=tool_name)


def _maybe_apply_progress_watchdog(name: str, args: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    spec = _SPECS_BY_NAME.get(name)
    if spec is None or spec.read_only or not payload.get("ok") or name == "cs_checkpoint":
        return payload
    quest_id = str(args.get("quest_id") or payload.get("quest_id") or "").strip()
    if not quest_id:
        return payload
    payload.update(ProgressWatchdogService(_layout(args)).record_state_changing_tool(quest_id=quest_id, tool_name=name, args=args, payload=payload))
    return payload


def call_tool(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    if name not in _SPECS_BY_NAME:
        return _finalize_tool_payload(
            _error_payload("unknown_tool", f"Unknown MCP tool: {name}", True, name),
            tool_name=name,
            args=args,
        )
    handler = _HANDLERS.get(name)
    if handler is None:
        return _finalize_tool_payload(
            _error_payload(
                "internal_error",
                f"MCP tool not implemented yet: {name}",
                True,
                name,
                suggested_next_action="Run cs_doctor and implement or enable this MCP tool family; keep hidden admin/debug CLI outside the default agent research flow.",
            ),
            tool_name=name,
            args=args,
        )
    call_args = dict(args or {})
    if name == "cs_bash_exec":
        bash_preflight = _bash_exec_preflight(call_args)
        if bash_preflight is not None:
            return _finalize_tool_payload(bash_preflight, tool_name=name, args=call_args)
    spec = _SPECS_BY_NAME[name]
    required_error = _validate_required_args(name, call_args, spec)
    if required_error is not None:
        return _finalize_tool_payload(required_error, tool_name=name, args=call_args)
    try:
        payload = handler(call_args)
    except FileNotFoundError as exc:
        return _finalize_tool_payload(_error_payload("not_found", str(exc), True, name), tool_name=name, args=call_args)
    except ValueError as exc:
        return _finalize_tool_payload(_error_payload(_value_error_type(str(exc)), str(exc), True, name), tool_name=name, args=call_args)
    except Exception as exc:
        return _finalize_tool_payload(_error_payload("internal_error", f"MCP tool failed: {exc}", True, name), tool_name=name, args=call_args)
    payload = _maybe_apply_progress_watchdog(name, call_args, payload)
    return _finalize_tool_payload(payload, tool_name=name, args=call_args)
