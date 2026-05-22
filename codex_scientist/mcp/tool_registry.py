"""Curated MCP tool registry for CodexScientist."""
from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from codex_scientist.mcp import goal_context, research_tools
from codex_scientist.mcp.envelope import apply_budget_envelope
from codex_scientist.mcp.skill_index import load_skill, search_skills
from codex_scientist.profiles import DEFAULT_PROFILE_NAME, PROFILES, get_profile, get_profile_tool_names
from codex_scientist.runtime.vendor.codexscientist.artifact.schemas import ARTIFACT_DIRS
from codex_scientist.services.artifacts import ArtifactIndexService
from codex_scientist.services.checkpoint import CheckpointService
from codex_scientist.services.context_pack import ContextPackService
from codex_scientist.services.costs import CostApprovalService
from codex_scientist.services.legacy_migration import LegacyQuestDetector
from codex_scientist.services.manifest import ManifestService
from codex_scientist.services.project_state import ProjectLayout, ProjectRootResolver
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
_ALLOWED_ARTIFACT_KINDS = tuple(sorted(ARTIFACT_DIRS))
_EXECUTOR_MCP_ENV = "CODEXSCIENTIST_ENABLE_EXECUTOR_MCP"
_EXECUTOR_PROFILE_NAME = "executor_local"
_EXECUTOR_TOOL_NAMES = frozenset(PROFILES[_EXECUTOR_PROFILE_NAME].tool_names)
_PROVENANCE_QUEST_ID_DESCRIPTION = (
    "Root-bound provenance id. Omit in normal Codex plugin use. When provided, it must match "
    "CodexScientist/research.yaml and never changes storage root."
)
_LEGACY_QUEST_ID_REQUIRED_TOOLS = frozenset({"cs_set_active_quest", "cs_goal_context", "cs_goal_state", "cs_goal_next_action", "cs_goal_watchdog"})


@dataclass(frozen=True)
class ResearchContext:
    project_root: Path
    layout: ProjectLayout
    state_root: Path
    manifest: dict[str, Any] | None
    quest_id: str | None
    quest_root: Path
    created_now: bool
    legacy_status: str
    legacy_quest_ids: tuple[str, ...]
    legacy_quests: tuple[dict[str, Any], ...]


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


def _project_root_arg(args: dict[str, Any]) -> Path:
    return ProjectRootResolver.resolve(args)


def _layout(args: dict[str, Any]) -> ProjectLayout:
    return ProjectLayout.from_project_root(_project_root_arg(args))


def _current_research(args: dict[str, Any], *, create: bool) -> ResearchContext:
    layout = _layout(args)
    manifest_service = ManifestService(layout)
    manifest_result = manifest_service.ensure_initialized(create=create)
    legacy = LegacyQuestDetector.inspect(layout)
    legacy_ids = tuple(quest.quest_id for quest in legacy.quests)
    manifest = manifest_result.get("manifest") if manifest_result.get("ok") else None
    quest_id = None
    created_now = bool(manifest_result.get("created")) if manifest_result.get("ok") else False
    if isinstance(manifest, dict):
        quest_value = manifest.get("quest")
        quest = quest_value if isinstance(quest_value, dict) else {}
        quest_id = str(quest.get("id") or "").strip() or None
    return ResearchContext(
        project_root=layout.project_root,
        layout=layout,
        state_root=layout.state_root,
        manifest=manifest,
        quest_id=quest_id,
        quest_root=layout.state_root,
        created_now=created_now,
        legacy_status=legacy.status,
        legacy_quest_ids=legacy_ids,
        legacy_quests=tuple(quest.as_dict() for quest in legacy.quests),
    )


def _manifest_status_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    goal_value = manifest.get("goal")
    project_value = manifest.get("project")
    goal = goal_value if isinstance(goal_value, dict) else {}
    project = project_value if isinstance(project_value, dict) else {}
    return {
        "schema_version": manifest.get("schema_version"),
        "layout_mode": manifest.get("layout_mode"),
        "project": project.get("name"),
        "goal": goal.get("title"),
    }


def _simple_status(args: dict[str, Any]) -> dict[str, Any]:
    context = _current_research(args, create=False)
    if context.manifest is not None:
        research_state = "ready"
    elif context.legacy_status != "none":
        research_state = context.legacy_status
    else:
        research_state = "no_research_state"
    payload: dict[str, Any] = {
        "ok": True,
        "transport": "codexscientist-mcp",
        "mcp": True,
        "tool": "cs_status",
        "project": str(context.project_root),
        "state_root": str(context.state_root),
        "state_root_exists": context.state_root.exists(),
        "research_state": research_state,
        "legacy_status": context.legacy_status,
        "legacy_quest_ids": list(context.legacy_quest_ids),
        "legacy_quests": list(context.legacy_quests),
    }
    if context.manifest is not None:
        payload["manifest"] = _manifest_status_summary(context.manifest)
        payload["quest_id"] = context.quest_id
        payload["quest_root"] = str(context.quest_root)
    return payload


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
    quest_id = str(args.get("quest_id") or "").strip() or None
    return ArtifactIndexService(_layout(args)).index(max_items=max(1, min(int(args.get("max_items") or 50), 500)), quest_id=quest_id)


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
    description = str(schema.get("description") or fallback)
    return description if len(description) <= 160 else f"{description[:157].rstrip()}..."


def _minimal_property_for_key(key: str) -> dict[str, Any]:
    if key == "quest_id":
        return {"type": "string", "description": _PROVENANCE_QUEST_ID_DESCRIPTION}
    if key.endswith("_id") or key in {"project", "project_root", "name", "goal", "title", "query", "baseline_path"}:
        return {"type": "string"}
    if key in {"slices", "completed", "decisions", "validation", "expected_outputs", "evidence_paths"}:
        return {"type": "array"}
    if key == "novelty_contract":
        return {
            "type": "object",
            "required": ["mechanism", "related_work_refs", "expected_difference"],
            "properties": {
                "mechanism": {"type": "string"},
                "related_work_refs": {"type": "array", "items": {"type": "string"}},
                "expected_difference": {"type": "string"},
            },
        }
    return {"type": "string"}


def _schema_with_registry_contract(schema: dict[str, Any], spec: ToolSpec) -> dict[str, Any]:
    merged: dict[str, Any] = dict(schema)
    merged.setdefault("name", spec.name)
    merged.setdefault("description", spec.description)
    input_schema: dict[str, Any] = dict(merged.get("input_schema") or merged.get("inputSchema") or {"type": "object"})
    properties: dict[str, Any] = dict(input_schema.get("properties") or {})
    for key in ("project", "project_root", *spec.required_context_keys):
        properties.setdefault(key, _minimal_property_for_key(key))
    if "quest_id" in properties:
        quest_prop = dict(properties["quest_id"])
        quest_prop["description"] = _PROVENANCE_QUEST_ID_DESCRIPTION
        properties["quest_id"] = quest_prop
    required = list(input_schema.get("required") or [])
    if "quest_id" not in spec.required_context_keys:
        required = [key for key in required if key != "quest_id"]
    for key in spec.required_context_keys:
        if key not in required:
            required.append(key)
    input_schema["type"] = "object"
    input_schema["properties"] = properties
    input_schema["required"] = required
    input_schema.setdefault("additionalProperties", True)
    merged["input_schema"] = input_schema
    return merged


def _minimal_schema_from_spec(spec: ToolSpec) -> dict[str, Any]:
    extra_properties: dict[str, Any] = {}
    if spec.name == "cs_resume_brief":
        extra_properties.update({
            "quest_id": _minimal_property_for_key("quest_id"),
            "max_chars": {"type": "integer", "default": 8000},
            "include_recent_events": {"type": "integer", "default": 5},
            "include_risks": {"type": "boolean", "default": True},
        })
    elif spec.name == "cs_pack_delta":
        extra_properties.update({
            "since_event_seq": {"type": "integer", "description": "Return events after this event sequence."},
            "since_checkpoint_id": {"type": "string", "description": "Return events after the checkpoint's event sequence."},
            "max_chars": {"type": "integer", "default": 6000},
        })
    elif spec.name == "cs_checkpoint":
        extra_properties.update({
            "quest_id": _minimal_property_for_key("quest_id"),
            "phase": {"type": "string", "description": "Compact label for the current research/recovery phase."},
            "completed": {"type": "array", "items": {"type": "string"}, "description": "Short completed-work bullets to preserve across compaction."},
            "decisions": {"type": "array", "items": {"type": "string"}, "description": "Durable decisions that future sessions should not rediscover."},
            "validation": {"type": "array", "items": {"type": "string"}, "description": "Tests, commands, or checks that were run."},
            "next_action": {"type": "string", "description": "Concrete next step for the next Codex session."},
            "artifact_refs": {"type": "array", "items": {}, "description": "Paths or structured refs for artifacts needed after resume."},
            "risk_flags": {"type": "array", "items": {"type": "string"}, "description": "Known risks/blockers that should survive context compaction."},
            "idempotency_key": {"type": "string", "description": "Optional stable key for retry-safe checkpoint writes."},
        })
    elif spec.name == "cs_context_pack":
        extra_properties.update({
            "quest_id": _minimal_property_for_key("quest_id"),
            "max_chars": {"type": "integer", "default": 12000},
        })
    elif spec.name == "cs_artifact_index":
        extra_properties.update({
            "quest_id": _minimal_property_for_key("quest_id"),
            "max_items": {"type": "integer", "default": 50},
        })
    return _schema_with_registry_contract(
        {
            "name": spec.name,
            "description": spec.description,
            "mcp_registry_only": True,
            "input_schema": {"type": "object", "properties": extra_properties, "required": [], "additionalProperties": True},
        },
        spec,
    )


def _tool_schema(args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("name") or args.get("tool") or "").strip()
    if not name:
        return {"ok": False, "error": "Missing tool name", "error_type": "missing_argument", "recoverable": True}
    spec = _SPECS_BY_NAME.get(name)
    if spec is None:
        return {"ok": False, "error": f"Unknown tool schema: {name}", "error_type": "unknown_tool", "recoverable": True}
    native_schema = research_tools.SCHEMA_BY_NAME.get(name) or research_tools.PUBLIC_SCHEMA_BY_NAME.get(name)
    schema = _schema_with_registry_contract(native_schema, spec) if isinstance(native_schema, dict) else _minimal_schema_from_spec(spec)
    return {"ok": True, "schema": schema}


def _spec(name: str, fallback: str, *, group: str, read_only: bool = True, idempotent: bool = True, required: tuple[str, ...] = ()) -> ToolSpec:
    effective_required = required if name in _LEGACY_QUEST_ID_REQUIRED_TOOLS else tuple(key for key in required if key != "quest_id")
    return ToolSpec(
        name=name,
        description=_schema_description(name, fallback),
        group=group,
        read_only=read_only,
        idempotent=idempotent,
        required_context_keys=effective_required,
    )


_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "cs_doctor": research_tools.native_handler("cs_doctor"),
    "cs_status": _simple_status,
    "cs_goal_context": goal_context.goal_context,
    "cs_goal_state": goal_context.goal_state,
    "cs_goal_next_action": goal_context.goal_next_action,
    "cs_tool_schema": _tool_schema,
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
    "cs_memory_read",
    "cs_memory_list_recent",
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
    "cs_arxiv",
    "cs_environment_register",
    "cs_environment_validate",
    "cs_environment_show",
    "cs_feedback_ingest",
    "cs_trajectory_record",
    "cs_trajectory_search",
    "cs_trajectory_show",
    "cs_evolutionary_plan_round",
    "cs_variant_create",
    "cs_variant_apply_patch",
    "cs_variant_check",
    "cs_variant_pack",
    "cs_scheduler_submit",
    "cs_scheduler_status",
    "cs_worker_claim",
    "cs_worker_heartbeat",
    "cs_worker_collect",
    "cs_worker_upload_artifact",
    "cs_evolutionary_round_submit",
    "cs_implementer_patch_check",
    "cs_implementer_repair_patch",
    "cs_strict_research_prepare",
    "cs_strict_research_record_candidate",
    "cs_strict_research_upsert_candidate",
    "cs_record_literature_reading_note",
    "cs_strict_research_init_bibliography",
    "cs_paper_reliability_verify",
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
    _spec("cs_memory_search", "Search quest-local memory cards.", group="memory", required=("quest_id", "query")),
    _spec("cs_memory_read", "Read one quest-local memory card by id or path.", group="memory", required=("quest_id",)),
    _spec("cs_memory_list_recent", "List recent quest-local memory cards.", group="memory", required=("quest_id",)),
    _spec("cs_memory_write", "Write a quest-local memory card.", group="memory", read_only=False, idempotent=False, required=("quest_id", "title")),
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
    _spec("cs_arxiv", "Read or list the quest-local arXiv library.", group="literature", required=("quest_id",)),
    _spec("cs_environment_register", "Register an execution-grounded environment manifest.", group="execution_planning", read_only=False, idempotent=False, required=("quest_id", "manifest")),
    _spec("cs_environment_validate", "Validate an execution-grounded environment manifest.", group="execution_planning", required=("quest_id", "env_id")),
    _spec("cs_environment_show", "Read an execution-grounded environment manifest.", group="execution_planning", required=("quest_id", "env_id")),
    _spec("cs_feedback_ingest", "Ingest local execution feedback metrics/logs into a trajectory.", group="execution_feedback", read_only=False, idempotent=False, required=("quest_id", "env_id", "trajectory_id", "run_id", "source_kind")),
    _spec("cs_trajectory_record", "Create or update an execution-grounded trajectory record.", group="trajectory", read_only=False, idempotent=False, required=("quest_id",)),
    _spec("cs_trajectory_search", "Search execution-grounded trajectories.", group="trajectory", required=("quest_id",)),
    _spec("cs_trajectory_show", "Read one execution-grounded trajectory.", group="trajectory", required=("quest_id", "trajectory_id")),
    _spec("cs_evolutionary_plan_round", "Create a deterministic plan-only evolutionary round; never submits jobs or creates variants.", group="execution_planning", read_only=False, idempotent=True, required=("quest_id", "env_id")),
    _spec("cs_variant_create", "Create an isolated execution variant worktree behind executor approval gates.", group="executor", read_only=False, idempotent=False, required=("quest_id", "env_id", "trajectory_id", "idea_id")),
    _spec("cs_variant_apply_patch", "Apply a patch inside an isolated variant workspace behind executor approval gates.", group="executor", read_only=False, idempotent=False, required=("quest_id", "variant_id", "patch_path")),
    _spec("cs_variant_check", "Run smoke checks for a variant behind executor approval gates.", group="executor", read_only=False, idempotent=False, required=("quest_id", "variant_id")),
    _spec("cs_variant_pack", "Create a deterministic variant package behind executor approval gates.", group="executor", read_only=False, idempotent=False, required=("quest_id", "variant_id")),
    _spec("cs_scheduler_submit", "Submit one executor-local scheduler job for a packed variant.", group="executor", read_only=False, idempotent=False, required=("quest_id", "env_id", "trajectory_id", "variant_id", "package_path", "command")),
    _spec("cs_scheduler_status", "Read executor-local scheduler queue status.", group="executor", required=()),
    _spec("cs_worker_claim", "Claim and start one executor-local scheduler job.", group="executor", read_only=False, idempotent=False, required=("worker_id",)),
    _spec("cs_worker_heartbeat", "Record a heartbeat for an executor-local worker run.", group="executor", read_only=False, idempotent=True, required=("run_id",)),
    _spec("cs_worker_collect", "Collect one executor-local worker job and ingest metrics/log feedback.", group="executor", read_only=False, idempotent=False, required=("job_id",)),
    _spec("cs_worker_upload_artifact", "Copy one local worker artifact into the quest execution-grounded artifact area.", group="executor", read_only=False, idempotent=False, required=("job_id", "artifact_path")),
    _spec("cs_evolutionary_round_submit", "Submit scheduler jobs for an existing approved EvolutionaryRoundPlan; never creates variants.", group="executor", read_only=False, idempotent=False, required=("quest_id", "env_id", "round_id", "submissions")),
    _spec("cs_implementer_patch_check", "Dry-run an implementer patch against a variant behind executor approval gates.", group="executor", read_only=False, idempotent=False, required=("quest_id", "variant_id", "patch_path")),
    _spec("cs_implementer_repair_patch", "Return gated patch-repair guidance for an implementer failure.", group="executor", read_only=False, idempotent=False, required=("quest_id", "variant_id")),
    _spec("cs_strict_research_prepare", "Initialize strict literature research mode for a quest.", group="literature", read_only=False, idempotent=False, required=("quest_id",)),
    _spec("cs_strict_research_record_candidate", "Append a strict-research candidate paper row.", group="literature", read_only=False, idempotent=False, required=("quest_id", "title")),
    _spec("cs_strict_research_upsert_candidate", "Upsert a strict-research candidate paper row.", group="literature", read_only=False, idempotent=False, required=("quest_id",)),
    _spec("cs_record_literature_reading_note", "Record a strict-research reading note.", group="literature", read_only=False, idempotent=False, required=("quest_id", "title")),
    _spec("cs_strict_research_init_bibliography", "Initialize strict-research bibliography working files.", group="literature", read_only=False, idempotent=False, required=("quest_id",)),
    _spec("cs_paper_reliability_verify", "Verify and store one paper reliability evidence card.", group="literature", read_only=False, idempotent=False, required=("quest_id", "title")),
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
        "cs_environment_register",
        "cs_environment_validate",
        "cs_environment_show",
        "cs_feedback_ingest",
        "cs_trajectory_record",
        "cs_trajectory_search",
        "cs_trajectory_show",
        "cs_evolutionary_plan_round",
        "cs_variant_create",
        "cs_variant_apply_patch",
        "cs_variant_check",
        "cs_variant_pack",
        "cs_scheduler_submit",
        "cs_scheduler_status",
        "cs_worker_claim",
        "cs_worker_collect",
        "cs_implementer_patch_check",
        "cs_implementer_repair_patch",
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
    for key in ("project", "project_root", "quest_id"):
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


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _executor_manifest_mcp_enabled(environment: dict[str, Any]) -> bool:
    raw_executor = environment.get("executor")
    executor = raw_executor if isinstance(raw_executor, dict) else {}
    return _truthy(environment.get("executor_mcp_enabled")) or _truthy(executor.get("mcp_enabled"))


def _executor_mcp_gate_error(args: dict[str, Any], *, tool_name: str) -> dict[str, Any] | None:
    if not _truthy(os.environ.get(_EXECUTOR_MCP_ENV)):
        return _error_payload(
            "executor_mcp_disabled",
            f"Executor MCP profile requires {_EXECUTOR_MCP_ENV}=1.",
            True,
            tool_name,
            required_env=_EXECUTOR_MCP_ENV,
        )
    missing = [key for key in ("quest_id", "env_id") if _is_missing_arg(args.get(key))]
    if missing:
        return _error_payload(
            "executor_mcp_manifest_required",
            "Executor MCP profile requires quest_id/env_id so the environment manifest can authorize executor exposure.",
            True,
            tool_name,
            missing_context_keys=missing,
        )
    from codex_scientist.services.environment import EnvironmentService

    shown = EnvironmentService(_layout(args)).show(quest_id=str(args["quest_id"]), env_id=str(args["env_id"]))
    if shown.get("ok") is not True:
        payload = _normalized_failure_payload(dict(shown), tool_name=tool_name, args=args)
        payload.setdefault("error_type", "executor_mcp_manifest_required")
        return payload
    raw_environment = shown.get("environment")
    environment = raw_environment if isinstance(raw_environment, dict) else {}
    if not _executor_manifest_mcp_enabled(environment):
        return _error_payload(
            "executor_mcp_manifest_required",
            "Executor MCP profile requires environment manifest flag executor.mcp_enabled=true.",
            True,
            tool_name,
            required_manifest_flag="executor.mcp_enabled",
        )
    return None


def _analysis_campaign_retry_template(args: dict[str, Any]) -> dict[str, Any]:
    required = ["quest_id", "campaign_title", "campaign_goal", "slices"]
    writing_keys = ["selected_outline_ref", "research_questions", "experimental_designs", "todo_items"]
    raw_slices_value = args.get("slices")
    raw_slices = raw_slices_value if isinstance(raw_slices_value, list) else []
    first_slice = next((item for item in raw_slices if isinstance(item, dict)), {})
    slice_id = str(first_slice.get("slice_id") or "S1").strip() or "S1"
    todo_template = {
        "slice_id": slice_id,
        "section_id": "paper-section-id",
        "item_id": f"{slice_id}-evidence",
        "paper_role": "evidence",
        "claim_links": ["claim-id"],
    }
    return {
        "name": "cs_create_analysis_campaign",
        "required_arguments": required,
        "missing_arguments": [key for key in required if _is_missing_arg(args.get(key))],
        "known_arguments": _known_args(args, [*required, *writing_keys]),
        "writing_facing_required_arguments": writing_keys,
        "writing_facing_rule": "If selected_outline_ref, research_questions, experimental_designs, or todo_items is present, provide all four and one outline-bound todo item per slice.",
        "todo_item_template": todo_template,
        "minimal_writing_example": {
            "selected_outline_ref": str(args.get("selected_outline_ref") or "outline-001"),
            "research_questions": args.get("research_questions") or ["What evidence gap does this slice close?"],
            "experimental_designs": args.get("experimental_designs") or ["Run the full planned analysis for this slice; do not simplify the protocol."],
            "todo_items": args.get("todo_items") or [todo_template],
        },
    }


def _analysis_campaign_preflight(args: dict[str, Any]) -> dict[str, Any] | None:
    writing_keys = ("selected_outline_ref", "research_questions", "experimental_designs", "todo_items")
    writing_facing = any(not _is_missing_arg(args.get(key)) for key in writing_keys)
    if not writing_facing:
        return None
    missing = [key for key in writing_keys if _is_missing_arg(args.get(key))]
    todo_items_value = args.get("todo_items")
    slices_value = args.get("slices")
    todo_items = todo_items_value if isinstance(todo_items_value, list) else []
    slices = slices_value if isinstance(slices_value, list) else []
    slice_ids = [str(item.get("slice_id") or "").strip() for item in slices if isinstance(item, dict) and str(item.get("slice_id") or "").strip()]
    todo_by_slice = {
        str(item.get("slice_id") or "").strip(): item
        for item in todo_items
        if isinstance(item, dict) and str(item.get("slice_id") or "").strip()
    }
    for slice_id in slice_ids:
        item = todo_by_slice.get(slice_id)
        if item is None:
            if "todo_items" not in missing:
                missing.append("todo_items")
            continue
        for field in ("section_id", "item_id", "paper_role", "claim_links"):
            if _is_missing_arg(item.get(field)):
                missing.append(f"todo_items[{slice_id}].{field}")
    if missing:
        return _error_payload(
            "missing_argument",
            "Writing-facing analysis campaigns require selected_outline_ref, research_questions, experimental_designs, todo_items, and outline-bound todo fields before slices can be launched.",
            True,
            "cs_create_analysis_campaign",
            missing_context_keys=missing,
            retry_template=_analysis_campaign_retry_template(args),
            suggested_next_action="Retry cs_create_analysis_campaign with the missing writing-facing fields; omit all writing-facing fields only for evidence-only campaigns.",
        )
    return None


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
    current["error"] = error
    if tool_name == "cs_bash_exec" and error == "workdir_outside_quest":
        layout = _layout(call_args)
        quest_root = str(layout.state_root)
        current["error_type"] = "workdir_outside_quest"
        current["allowed_roots"] = [quest_root]
        current["retry_template"] = {
            "name": "cs_bash_exec",
            "required_arguments": ["quest_id", "operation", "command", "command_class", "provenance_reason", "experiment_or_artifact_id", "cwd_policy"],
            "workdir": quest_root,
            "cwd_policy": "quest",
        }
        current["suggested_next_action"] = "Retry cs_bash_exec with workdir under the quest root, or omit workdir and keep cwd_policy=quest."
    if tool_name == "cs_confirm_baseline" and "baseline_path" in error and ("state_root" in error or "quest_root" in error):
        current.setdefault("retry_template", {
            "name": "cs_confirm_baseline",
            "required_arguments": ["quest_id", "baseline_path"],
            "path_constraint": "baseline_path must be under state_root; use cs_create_local_baseline to create a canonical root-bound baseline first.",
        })
        current["suggested_next_action"] = "Use cs_create_local_baseline, then retry cs_confirm_baseline with the returned confirm_args."
    if tool_name in {"cs_record_main_experiment", "cs_create_analysis_campaign", "cs_record_analysis_slice", "cs_claim_gate"} and (
        "artifact.confirm_baseline" in error or "artifact.waive_baseline" in error
    ):
        current["error"] = error.replace("artifact.confirm_baseline(...)", "cs_confirm_baseline").replace("artifact.waive_baseline(...)", "cs_waive_baseline")
        current.setdefault("retry_template", {
            "name": "cs_confirm_baseline_or_cs_waive_baseline",
            "options": ["cs_confirm_baseline", "cs_waive_baseline"],
            "required_before_retry": [tool_name],
        })
        current["suggested_next_action"] = "Open the baseline gate with cs_confirm_baseline, or explicitly record a waiver with cs_waive_baseline, then retry this MCP tool."
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


_MEMORY_TOOLS = frozenset({"cs_memory_search", "cs_memory_read", "cs_memory_list_recent", "cs_memory_write"})


def _artifact_record_preflight(args: dict[str, Any]) -> dict[str, Any] | None:
    raw_payload = args.get("payload")
    payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}
    top_kind = str(args.get("kind") or "").strip()
    requested_kind = str(payload.get("kind") or top_kind or "report").strip() or "report"
    if requested_kind in _ALLOWED_ARTIFACT_KINDS:
        return None
    summary = str(args.get("summary") or payload.get("summary") or "").strip()
    retry_payload = {"kind": "report", "report_type": requested_kind}
    if summary:
        retry_payload["summary"] = summary
    return _error_payload(
        "invalid_argument",
        f"Unknown artifact kind: {requested_kind}. Use one of allowed_kinds, or store semantic subtypes as kind=report with payload.report_type.",
        True,
        "cs_artifact_record",
        allowed_kinds=list(_ALLOWED_ARTIFACT_KINDS),
        retry_template={"name": "cs_artifact_record", "kind": "report", "payload": retry_payload},
        suggested_next_action="Retry cs_artifact_record with a canonical kind. For dataset_inspection or metric_report use kind=report and set payload.report_type to the semantic subtype.",
    )


def _memory_preflight(name: str, args: dict[str, Any]) -> dict[str, Any] | None:
    if name not in _MEMORY_TOOLS:
        return None
    scope = str(args.get("scope") or "quest").strip().lower() or "quest"
    if scope != "quest":
        return {
            "ok": False,
            "error": f"Unsupported memory scope for agent-facing MCP path: {scope}",
            "error_type": "unsupported_scope",
            "recoverable": True,
            "scope": scope,
            "allowed_scopes": ["quest"],
        }
    return None


_FORMAL_BASH_COMMAND_CLASSES = frozenset({"formal_experiment", "benchmark", "paper_build", "reproduction", "official_evaluation"})


def _paper_reliability_preflight(args: dict[str, Any]) -> dict[str, Any] | None:
    dry_run = bool(args.get("dry_run"))
    network_raw = args.get("network", args.get("allow_network", True))
    network_enabled = False if network_raw is False or str(network_raw).strip().lower() in {"0", "false", "no", "off"} else True
    title = str(args.get("title") or args.get("doi") or args.get("arxiv_url") or args.get("url") or "").strip()
    if not title:
        return _error_payload(
            "missing_argument",
            "Provide at least one of title, doi, arxiv_url, or url for cs_paper_reliability_verify.",
            True,
            "cs_paper_reliability_verify",
            missing_context_keys=["title"],
        )
    if not dry_run and network_enabled:
        has_external_url = bool(str(args.get("url") or "").strip())
        has_resolvable_identifier = bool(str(args.get("doi") or args.get("arxiv_url") or "").strip())
        if has_external_url and not has_resolvable_identifier:
            return _error_payload(
                "external_io_requires_bounded_mode",
                "External URL-only paper reliability checks must be bounded: pass dry_run=true or network=false, or provide a DOI/arxiv_url for a full verifier run.",
                True,
                "cs_paper_reliability_verify",
                retry_template={
                    "name": "cs_paper_reliability_verify",
                    "required_arguments": ["quest_id", "title"],
                    "bounded_options": [{"dry_run": True, "network": False}, {"doi": "10.xxxx/example"}, {"arxiv_url": "https://arxiv.org/abs/xxxx.xxxxx"}],
                },
            )
        return None
    return {
        "ok": True,
        "dry_run": True,
        "network": False,
        "title": str(args.get("title") or "").strip() or None,
        "doi": str(args.get("doi") or "").strip() or None,
        "arxiv_url": str(args.get("arxiv_url") or args.get("url") or "").strip() or None,
        "required_evidence": ["official_pdf_or_metadata", "venue_or_source_evidence", "reliability_card_output"],
        "suggested_next_action": "Retry cs_paper_reliability_verify without dry_run/network=false after official paper metadata is available and external IO is acceptable.",
    }


def _bash_exec_preflight(args: dict[str, Any]) -> dict[str, Any] | None:
    operation = str(args.get("operation") or ("run" if args.get("command") else "list")).strip().lower()
    if operation == "run":
        missing: list[str] = []
        for key in ("command", "command_class", "provenance_reason", "experiment_or_artifact_id", "cwd_policy"):
            if _is_missing_arg(args.get(key)):
                missing.append(key)
        if _is_missing_arg(args.get("expected_outputs")) and _is_missing_arg(args.get("evidence_paths")):
            missing.append("expected_outputs_or_evidence_paths")
        if missing:
            spec = _SPECS_BY_NAME["cs_bash_exec"]
            payload = _missing_argument_payload("cs_bash_exec", spec, missing, args)
            payload["missing_arguments"] = missing
            return payload
        command_class = str(args.get("command_class") or "").strip()
        if command_class not in _FORMAL_BASH_COMMAND_CLASSES:
            return {
                "ok": False,
                "error": f"Unsupported cs_bash_exec command_class for formal-run provenance: {command_class}",
                "error_type": "invalid_command_class",
                "recoverable": True,
                "allowed_command_classes": sorted(_FORMAL_BASH_COMMAND_CLASSES),
                "command_class": command_class,
            }
    if operation == "list" and _is_missing_arg(args.get("command")):
        quest_id = str(args.get("quest_id") or "").strip()
        if quest_id:
            return {"ok": True, "quest_id": quest_id, "sessions": [], "summary": {"session_count": 0}}
    return None


def list_tool_specs(profile: str | None = None, stage: str | None = None) -> list[ToolSpec]:
    profile_name = profile or DEFAULT_PROFILE_NAME
    names = get_profile_tool_names(profile_name, stage=stage)
    return [spec for name in names if (spec := _SPECS_BY_NAME.get(name)) is not None]


def public_mcp_tool_names(args: dict[str, Any] | None = None) -> set[str]:
    names: set[str] = set()
    for profile in PROFILES.values():
        if profile.registers_mcp:
            names.update(profile.tool_names)
    payload_args = dict(args or {})
    if _executor_mcp_gate_error(payload_args, tool_name="tools/list") is None:
        names.update(_EXECUTOR_TOOL_NAMES)
    return names


def is_tool_registered_for_mcp(name: str, args: dict[str, Any] | None = None) -> bool:
    return name in public_mcp_tool_names(args)


def mcp_tool_not_registered_payload(name: str) -> dict[str, Any]:
    if name not in _SPECS_BY_NAME:
        return _finalize_tool_payload(_error_payload("unknown_tool", f"Unknown MCP tool: {name}", True, name), tool_name=name, args={})
    return _finalize_tool_payload(
        _error_payload(
            "tool_not_registered_for_mcp",
            f"Tool is not registered for the default Codex MCP public surface: {name}",
            True,
            name,
            registered_profiles=[profile.name for profile in PROFILES.values() if profile.registers_mcp and name in profile.tool_names],
            suggested_next_action="Call tools/list and choose one of the registered public CodexScientist MCP tools; hidden admin/autonomous tools are not callable over default MCP.",
            retry_template={"name": "tools/list", "profiles": [profile.name for profile in PROFILES.values() if profile.registers_mcp]},
        ),
        tool_name=name,
        args={},
    )


def tools_list_payload(args: dict[str, Any] | None = None) -> dict[str, Any]:
    payload_args = dict(args or {})
    requested_profile = str(payload_args.get("profile") or DEFAULT_PROFILE_NAME).strip() or DEFAULT_PROFILE_NAME
    stage_label = str(payload_args.get("stage") or payload_args.get("active_stage") or "").strip() or None
    try:
        profile_obj = get_profile(requested_profile)
    except KeyError as exc:
        return _finalize_tool_payload(
            _error_payload("unknown_profile", str(exc), True, "tools/list", profile=requested_profile),
            tool_name="tools/list",
            args=payload_args,
        )
    warnings: list[str] = []
    if profile_obj.deprecated:
        warnings.append(f"profile_deprecated:{profile_obj.name}->" f"{profile_obj.replacement or DEFAULT_PROFILE_NAME}")
    if stage_label:
        warnings.append("stage_label_not_used_for_tool_filtering")
    if not profile_obj.registers_mcp:
        if profile_obj.name == _EXECUTOR_PROFILE_NAME and any(not _is_missing_arg(payload_args.get(key)) for key in ("project", "project_root", "quest_id", "env_id")):
            executor_gate_error = _executor_mcp_gate_error(payload_args, tool_name="tools/list")
            if executor_gate_error is not None:
                return _finalize_tool_payload(executor_gate_error, tool_name="tools/list", args=payload_args)
        else:
            return _finalize_tool_payload(
                _error_payload(
                    "profile_not_registered_for_mcp",
                    f"Profile is not registered for default MCP: {requested_profile}",
                    True,
                    "tools/list",
                    profile=requested_profile,
                    stage_label=stage_label,
                    warnings=warnings,
                    suggested_next_action="Use an agent-facing profile such as core, evidence, formal_run, literature, or paper_write.",
                ),
                tool_name="tools/list",
                args=payload_args,
            )
    specs = list_tool_specs(requested_profile)
    return apply_budget_envelope(
        {
            "ok": True,
            "server": "codexscientist_mcp",
            "profile": requested_profile,
            "stage": stage_label,
            "stage_label": stage_label,
            "compact": True,
            "tools": [spec.as_dict() for spec in specs],
            "warnings": warnings,
        },
        tool_name="tools/list",
    )


def _finalize_tool_payload(payload: dict[str, Any], *, tool_name: str | None = None, args: dict[str, Any] | None = None) -> dict[str, Any]:
    return apply_budget_envelope(_normalized_failure_payload(payload, tool_name=tool_name, args=args), tool_name=tool_name)


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
    if name == "cs_paper_reliability_verify":
        reliability_preflight = _paper_reliability_preflight(call_args)
        if reliability_preflight is not None:
            return _finalize_tool_payload(reliability_preflight, tool_name=name, args=call_args)
    if name == "cs_bash_exec":
        bash_preflight = _bash_exec_preflight(call_args)
        if bash_preflight is not None:
            return _finalize_tool_payload(bash_preflight, tool_name=name, args=call_args)
    if name == "cs_create_analysis_campaign":
        analysis_preflight = _analysis_campaign_preflight(call_args)
        if analysis_preflight is not None:
            return _finalize_tool_payload(analysis_preflight, tool_name=name, args=call_args)
    if name == "cs_artifact_record":
        artifact_preflight = _artifact_record_preflight(call_args)
        if artifact_preflight is not None:
            return _finalize_tool_payload(artifact_preflight, tool_name=name, args=call_args)
    executor_gate_authorized = False
    if name in _EXECUTOR_TOOL_NAMES:
        executor_preflight = _executor_mcp_gate_error(call_args, tool_name=name)
        if executor_preflight is not None:
            return _finalize_tool_payload(executor_preflight, tool_name=name, args=call_args)
        executor_gate_authorized = True
    memory_preflight = _memory_preflight(name, call_args)
    if memory_preflight is not None:
        return _finalize_tool_payload(memory_preflight, tool_name=name, args=call_args)
    spec = _SPECS_BY_NAME[name]
    required_error = _validate_required_args(name, call_args, spec)
    if required_error is not None:
        return _finalize_tool_payload(required_error, tool_name=name, args=call_args)
    executor_gate_token = None
    if executor_gate_authorized:
        executor_gate_token = research_tools.native_tools._MCP_EXECUTOR_GATE_GRANTED.set(True)  # noqa: SLF001 - internal MCP-to-runtime gate context
    try:
        payload = handler(call_args)
    except FileNotFoundError as exc:
        return _finalize_tool_payload(_error_payload("not_found", str(exc), True, name), tool_name=name, args=call_args)
    except ValueError as exc:
        return _finalize_tool_payload(_error_payload(_value_error_type(str(exc)), str(exc), True, name), tool_name=name, args=call_args)
    except Exception as exc:
        return _finalize_tool_payload(_error_payload("internal_error", f"MCP tool failed: {exc}", True, name), tool_name=name, args=call_args)
    finally:
        if executor_gate_token is not None:
            research_tools.native_tools._MCP_EXECUTOR_GATE_GRANTED.reset(executor_gate_token)  # noqa: SLF001 - internal MCP-to-runtime gate context
    return _finalize_tool_payload(payload, tool_name=name, args=call_args)
