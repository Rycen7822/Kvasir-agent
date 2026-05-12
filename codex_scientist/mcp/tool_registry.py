"""Curated MCP tool registry for CodexScientist."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable

from codexscientist_native import tools as native_tools
from codex_scientist.adapters.cli import normalize_envelope
from codex_scientist.mcp.skill_index import load_skill, search_skills
from codex_scientist.services.context_pack import ContextPackService
from codex_scientist.services.costs import CostApprovalService
from codex_scientist.services.manifest import ManifestService
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.queue import QueueService
from codex_scientist.services.research_wiki import ResearchWikiService
from codex_scientist.services.review import ReviewService
from codex_scientist.services.runner import RunnerService
from codex_scientist.services.soak import SoakService
from codex_scientist.services.trial import TrialService

_TRIAL_ID_RE = re.compile(r"^T\d{4}$")
_RUN_ID_RE = re.compile(r"^R\d{4}$")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    read_only: bool = True
    destructive: bool = False
    idempotent: bool = True
    open_world: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
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


def _native_call(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    handler = getattr(native_tools, tool_name)
    raw = handler(args)
    payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    payload = normalize_envelope(payload)
    payload["transport"] = "codexscientist-mcp"
    payload["mcp"] = True
    payload["tool"] = tool_name
    return payload


def _simple_status(args: dict[str, Any]) -> dict[str, Any]:
    project = Path(args.get("project") or ".").resolve()
    state_root = project / "CodexScientist"
    fallback_state_root = project / "CodexScientist"
    return {
        "ok": True,
        "transport": "codexscientist-mcp",
        "mcp": True,
        "tool": "cs_status",
        "project": str(project),
        "state_root": str(state_root if state_root.exists() else fallback_state_root),
        "state_root_exists": state_root.exists() or fallback_state_root.exists(),
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


def _context_pack(args: dict[str, Any]) -> dict[str, Any]:
    max_chars = max(200, min(int(args.get("max_chars") or 4000), 12000))
    return ContextPackService(_layout(args)).write_context_pack(max_chars=max_chars)


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


_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "cs_doctor": lambda args: _native_call("cs_doctor", args),
    "cs_status": _simple_status,
    "cs_context_pack": _context_pack,
    "cs_manifest_validate": _manifest_validate,
    "cs_trial_show": _trial_show,
    "cs_runner_status": _runner_status,
    "cs_queue_status": _queue_status,
    "cs_queue_reconcile": _queue_reconcile,
    "cs_wiki_query_pack": _wiki_query_pack,
    "cs_review_status": _review_status,
    "cs_cost_status": _cost_status,
    "cs_soak_accelerated": _soak_accelerated,
    "cs_soak_crash_resume": _soak_crash_resume,
    "cs_skill_search": search_skills,
    "cs_skill_load": load_skill,
}

_SPECS: list[ToolSpec] = [
    ToolSpec("cs_doctor", "Run CodexScientist diagnostics without external legacy commands.", read_only=False),
    ToolSpec("cs_status", "Return a compact CodexScientist project status snapshot."),
    ToolSpec("cs_context_pack", "Generate or read a bounded context pack.", read_only=False),
    ToolSpec("cs_manifest_validate", "Validate the project-local research manifest.", read_only=False),
    ToolSpec("cs_trial_show", "Read one trial record by id."),
    ToolSpec("cs_runner_status", "Read one or all runner records."),
    ToolSpec("cs_queue_status", "Read queue status."),
    ToolSpec("cs_queue_reconcile", "Reconcile expired queue leases.", read_only=False),
    ToolSpec("cs_wiki_query_pack", "Build a bounded research wiki query pack."),
    ToolSpec("cs_review_status", "Read review artifact status."),
    ToolSpec("cs_cost_status", "Read latest cost and approval gate status."),
    ToolSpec("cs_soak_accelerated", "Run accelerated fake-clock long-run validation.", read_only=False, idempotent=False),
    ToolSpec("cs_soak_crash_resume", "Record restart and reconcile expired leases.", read_only=False, idempotent=False),
    ToolSpec("cs_skill_search", "Search local CodexScientist skills and return short candidate cards."),
    ToolSpec("cs_skill_load", "Load a bounded view of one indexed CodexScientist skill."),
]


def list_tool_specs() -> list[ToolSpec]:
    return list(_SPECS)


def tools_list_payload() -> dict[str, Any]:
    return {"ok": True, "server": "codexscientist_mcp", "tools": [spec.as_dict() for spec in _SPECS]}


def _finalize_tool_payload(payload: dict[str, Any], *, tool_name: str | None = None) -> dict[str, Any]:
    if tool_name is not None:
        payload.setdefault("tool", tool_name)
    payload.setdefault("transport", "codexscientist-mcp")
    payload.setdefault("mcp", True)
    original_tokens_estimate = payload.get("tokens_estimate")
    normalized = normalize_envelope(payload)
    if isinstance(original_tokens_estimate, int):
        normalized["tokens_estimate"] = original_tokens_estimate
    return normalized


def call_tool(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    if name not in {spec.name for spec in _SPECS}:
        return _finalize_tool_payload(
            {
                "ok": False,
                "error": f"Unknown MCP tool: {name}",
                "error_type": "unknown_tool",
                "recoverable": True,
                "suggested_next_action": "Call tools/list and choose one of the curated cs_* tools.",
            },
            tool_name=name,
        )
    handler = _HANDLERS.get(name)
    if handler is None:
        return _finalize_tool_payload(
            {
                "ok": False,
                "error": f"MCP tool not implemented yet: {name}",
                "error_type": "not_implemented",
                "recoverable": True,
                "suggested_next_action": "Use CLI fallback for this tool family while Phase M3 is in progress.",
            },
            tool_name=name,
        )
    try:
        payload = handler(dict(args or {}))
    except Exception as exc:
        return _finalize_tool_payload(
            {
                "ok": False,
                "error": f"MCP tool failed: {exc}",
                "error_type": "tool_error",
                "recoverable": True,
            },
            tool_name=name,
        )
    return _finalize_tool_payload(payload, tool_name=name)
