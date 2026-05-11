
"""Codex-native DeepScientist tool handlers.

Handlers call vendored DeepScientist services directly. They do not use MCP, shell out to, or require the global npm `ds` command.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .redaction import dumps_json
from .runtime import compact_snapshot, doctor as native_doctor, get_services
from .state import StateStore


def _payload(data: dict[str, Any]) -> str:
    return dumps_json(data)


def _error(message: str, **extra: Any) -> str:
    return _payload({"ok": False, "error": message, **extra})


def _guard(fn: Callable[[dict[str, Any]], dict[str, Any]]):
    @wraps(fn)
    def wrapper(args: dict | None = None, **kwargs: Any) -> str:
        try:
            payload = fn(dict(args or {}))
            if "ok" not in payload:
                payload = {"ok": True, **payload}
            return _payload(payload)
        except Exception as exc:
            return _error(str(exc), error_type=exc.__class__.__name__)
    return wrapper


def _require(args: dict[str, Any], *names: str) -> str | None:
    missing = [name for name in names if not str(args.get(name) or "").strip()]
    return f"Missing required value(s): {', '.join(missing)}" if missing else None


def _limit(args: dict[str, Any], default: int = 20, maximum: int = 200) -> int:
    try:
        value = int(args.get("limit") or default)
    except Exception:
        value = default
    return max(1, min(value, maximum))


ALLOWED_MEMORY_KINDS = ("papers", "ideas", "decisions", "episodes", "knowledge", "templates")
MEMORY_KIND_ALIASES = {
    "paper": "papers",
    "idea": "ideas",
    "decision": "decisions",
    "episode": "episodes",
    "template": "templates",
}
SEMANTIC_MEMORY_KIND_ALIASES = {
    "constraint": "constraint",
    "constraints": "constraint",
    "context": "context",
    "observation": "observation",
    "observations": "observation",
    "hypothesis": "hypothesis",
    "hypotheses": "hypothesis",
    "result": "result",
    "results": "result",
    "plan": "plan",
    "plans": "plan",
}


def _normalize_tags(tags: Any) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        raw = tags.strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                values = parsed
            else:
                values = [part.strip() for part in raw.split(",")]
        else:
            values = [part.strip() for part in raw.split(",")]
    elif isinstance(tags, (list, tuple, set)):
        values = list(tags)
    else:
        values = [tags]
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _memory_kind_aliases_payload() -> dict[str, str]:
    aliases = dict(MEMORY_KIND_ALIASES)
    aliases.update({key: "knowledge" for key in SEMANTIC_MEMORY_KIND_ALIASES})
    return aliases


def _normalize_memory_kind(value: Any, *, default: str = "knowledge") -> dict[str, Any]:
    requested = str(value or default).strip().lower().replace("-", "_") or default
    if requested in ALLOWED_MEMORY_KINDS:
        normalized = requested
        semantic_tag = None
    elif requested in MEMORY_KIND_ALIASES:
        normalized = MEMORY_KIND_ALIASES[requested]
        semantic_tag = None
    elif requested in SEMANTIC_MEMORY_KIND_ALIASES:
        normalized = "knowledge"
        semantic_tag = SEMANTIC_MEMORY_KIND_ALIASES[requested]
    else:
        raise ValueError(
            "Unknown memory kind: "
            f"{requested}. Allowed memory kinds: {', '.join(ALLOWED_MEMORY_KINDS)}. "
            "Supported aliases: "
            + ", ".join(f"{key}->{value}" for key, value in sorted(_memory_kind_aliases_payload().items()))
        )
    return {
        "requested": requested,
        "normalized": normalized,
        "semantic_tag": semantic_tag,
        "alias_applied": requested != normalized,
    }


def _memory_kind_error_payload(exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error": str(exc),
        "error_type": exc.__class__.__name__,
        "allowed_memory_kinds": list(ALLOWED_MEMORY_KINDS),
        "memory_kind_aliases": _memory_kind_aliases_payload(),
    }


def _safe_slug(value: Any, default: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._-")
    return text or default


def _coerce_env(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    env: dict[str, str] = {}
    for key, item in value.items():
        key_text = str(key or "").strip()
        if not key_text or item is None:
            continue
        env[key_text] = str(item)
    return env


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _optional_bool(args: dict[str, Any], name: str, default: bool) -> bool:
    if name not in args or args.get(name) is None:
        return default
    if isinstance(args.get(name), bool):
        return bool(args[name])
    return _truthy(args.get(name))


def _clean_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            values = parsed
        else:
            values = [part.strip() for part in raw.split("\n") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = [value]
    cleaned: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if text:
            cleaned.append(text)
    return cleaned


WORKSPACE_MODE_VALUES = {"copilot", "autonomous"}
DECISION_POLICY_VALUES = {"user_gated", "autonomous"}
FINAL_GOAL_VALUES = {"paper", "quality_result", "idea_optimization", "literature_scout", "baseline_reproduction", "analysis_report", "open_ended"}


def _build_startup_contract(args: dict[str, Any]) -> dict[str, Any] | tuple[None, str]:
    raw_workspace_mode = str(args.get("workspace_mode") or "").strip().lower()
    if raw_workspace_mode and raw_workspace_mode not in WORKSPACE_MODE_VALUES:
        return None, "workspace_mode must be one of: autonomous, copilot. Omit it for the safe default copilot mode."
    workspace_mode = raw_workspace_mode or "copilot"

    raw_decision_policy = str(args.get("decision_policy") or "").strip().lower()
    if raw_decision_policy and raw_decision_policy not in DECISION_POLICY_VALUES:
        return None, "decision_policy must be one of: autonomous, user_gated."
    decision_policy = raw_decision_policy or ("autonomous" if workspace_mode == "autonomous" else "user_gated")

    raw_final_goal = str(args.get("final_goal") or "").strip().lower()
    if raw_final_goal and raw_final_goal not in FINAL_GOAL_VALUES:
        return None, "final_goal must be one of: paper, quality_result, idea_optimization, literature_scout, baseline_reproduction, analysis_report, open_ended."
    final_goal = raw_final_goal or "open_ended"

    need_research_paper = _optional_bool(args, "need_research_paper", final_goal == "paper")
    delivery_mode = str(args.get("delivery_mode") or "").strip() or ("paper_bundle" if need_research_paper else final_goal)
    mode_rationale = str(args.get("mode_rationale") or "").strip() or (
        "default_copilot: workspace_mode was omitted, so the Codex-managed DeepScientist quest starts in request-scoped copilot mode without a default paper goal."
        if workspace_mode == "copilot"
        else "agent_selected_autonomous: Codex selected autonomous mode for multi-step progress ownership."
    )
    completion_criteria = _clean_string_list(args.get("completion_criteria"))

    contract: dict[str, Any] = {
        "workspace_mode": workspace_mode,
        "decision_policy": decision_policy,
        "need_research_paper": need_research_paper,
        "final_goal": final_goal,
        "delivery_mode": delivery_mode,
        "completion_criteria": completion_criteria,
        "mode_selected_by": "codex_agent",
        "mode_rationale": mode_rationale,
    }
    if workspace_mode == "autonomous" and not need_research_paper and final_goal == "quality_result":
        contract.setdefault("standard_profile", "optimization_task")
    user_contract = args.get("startup_contract")
    if isinstance(user_contract, dict):
        contract.update(user_contract)
    return contract


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _append_jsonl_path(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _read_json_path(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_path(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_existing_path(raw_path: Any, *, quest_root: Path | None = None, services: Any = None) -> Path | None:
    text = str(raw_path or "").strip()
    if not text:
        return None
    candidate = Path(text).expanduser()
    candidates: list[Path] = []
    if candidate.is_absolute():
        candidates.append(candidate)
    else:
        roots: list[Path] = []
        if quest_root is not None:
            roots.append(quest_root)
        try:
            if services is not None and getattr(services, "home", None) is not None:
                roots.append(Path(str(services.home)).parent)
        except Exception:
            pass
        roots.append(Path.cwd())
        for root in roots:
            candidates.append(root / candidate)
    for item in candidates:
        try:
            resolved = item.resolve()
        except OSError:
            continue
        if resolved.exists() and resolved.is_file():
            return resolved
    return None


def _parse_markdown_sections(markdown_path: Path) -> list[dict[str, Any]]:
    """Return paper sections from an existing Markdown draft.

    The title (`# ...`) is intentionally excluded. The parser recognizes ATX
    headings outside fenced code blocks and treats level 2+ headings as paper
    sections.
    """
    try:
        lines = markdown_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    sections: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    in_fence = False
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^(#{2,6})\s+(.+?)(?:\s+#+\s*)?$", stripped)
        if not match:
            continue
        title = match.group(2).strip()
        if not title:
            continue
        base = _safe_slug(title.lower().replace(" ", "_"), f"section_{len(sections) + 1}").lower()
        count = seen.get(base, 0) + 1
        seen[base] = count
        section_id = base if count == 1 else f"{base}_{count}"
        sections.append({"section_id": section_id, "title": title, "level": len(match.group(1)), "line": line_no})
    return sections


def _patch_guidance_to_latest_anchor(guidance_vm: dict[str, Any], active_anchor: str | None) -> dict[str, Any]:
    patched = dict(guidance_vm or {})
    anchor = str(active_anchor or "").strip()
    if anchor:
        patched["current_anchor"] = anchor
        if anchor == "finalize":
            patched["recommended_skill"] = "finalize"
            patched["recommended_action"] = "finalize"
            patched.setdefault(
                "summary",
                "Paper bundle submitted. Final verification and handoff should proceed from the latest quest state.",
            )
    return patched


def _enrich_paper_bundle_result(services: Any, quest_root: Path, result: dict[str, Any], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Repair wrapper-visible paper bundle metadata from the update2 hardening pass."""
    if not isinstance(result, dict) or not result.get("ok"):
        return result
    enriched = result
    try:
        snapshot = services.quest.snapshot(quest_root.name)
    except Exception:
        snapshot = {}
    active_anchor = str((snapshot or {}).get("active_anchor") or "").strip() or None

    artifact_payload = enriched.get("artifact") if isinstance(enriched.get("artifact"), dict) else {}
    artifact_path_text = (
        str(artifact_payload.get("artifact_path") or artifact_payload.get("path") or "").strip()
        if isinstance(artifact_payload, dict)
        else ""
    )
    artifact_path = Path(artifact_path_text).expanduser() if artifact_path_text else None
    persisted_artifact = _read_json_path(artifact_path) if artifact_path and artifact_path.exists() else {}
    artifact_record = (
        dict(artifact_payload.get("record") or {})
        if isinstance(artifact_payload.get("record"), dict)
        else dict(persisted_artifact or {})
    )

    guidance_vm = {}
    if isinstance(artifact_payload.get("guidance_vm"), dict):
        guidance_vm = dict(artifact_payload.get("guidance_vm") or {})
    elif isinstance(artifact_record.get("guidance_vm"), dict):
        guidance_vm = dict(artifact_record.get("guidance_vm") or {})
    elif isinstance(persisted_artifact.get("guidance_vm"), dict):
        guidance_vm = dict(persisted_artifact.get("guidance_vm") or {})
    patched_guidance = _patch_guidance_to_latest_anchor(guidance_vm, active_anchor)
    if patched_guidance:
        artifact_payload["guidance_vm"] = patched_guidance
        artifact_record["guidance_vm"] = patched_guidance
        enriched["guidance_vm"] = patched_guidance
        if patched_guidance.get("recommended_skill"):
            enriched["next_anchor"] = patched_guidance.get("recommended_skill")

    manifest_path_text = str(enriched.get("manifest_path") or "").strip()
    manifest_path = Path(manifest_path_text).expanduser() if manifest_path_text else None
    manifest = dict(enriched.get("manifest") or {}) if isinstance(enriched.get("manifest"), dict) else {}
    if manifest_path and manifest_path.exists():
        manifest = {**_read_json_path(manifest_path), **manifest}

    draft_path = _resolve_existing_path(
        kwargs.get("draft_path") or manifest.get("draft_path"),
        quest_root=quest_root,
        services=services,
    )
    markdown_sections = _parse_markdown_sections(draft_path) if draft_path else []
    if markdown_sections:
        section_count = len(markdown_sections)
        ready_section_count = section_count
        evidence_gate = dict(manifest.get("evidence_gate") or {}) if isinstance(manifest.get("evidence_gate"), dict) else {}
        if int(manifest.get("section_count") or 0) <= 0:
            manifest["section_count"] = section_count
        if int(manifest.get("ready_section_count") or 0) <= 0:
            manifest["ready_section_count"] = ready_section_count
        manifest["markdown_section_count"] = section_count
        manifest["markdown_sections"] = markdown_sections
        if int(evidence_gate.get("section_count") or 0) <= 0:
            evidence_gate["section_count"] = section_count
        if int(evidence_gate.get("ready_section_count") or 0) <= 0:
            evidence_gate["ready_section_count"] = ready_section_count
        evidence_gate["markdown_section_count"] = section_count
        evidence_gate["markdown_sections"] = markdown_sections
        manifest["evidence_gate"] = evidence_gate
        enriched["manifest"] = manifest
        enriched["markdown_sections"] = markdown_sections
        enriched["section_count"] = manifest.get("section_count")
        enriched["ready_section_count"] = manifest.get("ready_section_count")
        details = dict(artifact_record.get("details") or {}) if isinstance(artifact_record.get("details"), dict) else {}
        if int(details.get("section_count") or 0) <= 0:
            details["section_count"] = section_count
        if int(details.get("ready_section_count") or 0) <= 0:
            details["ready_section_count"] = ready_section_count
        details["markdown_section_count"] = section_count
        details["markdown_sections"] = markdown_sections
        artifact_record["details"] = details
        artifact_payload["details"] = details
        if isinstance(artifact_payload.get("record"), dict):
            artifact_payload["record"]["details"] = details

    if artifact_record:
        artifact_payload["record"] = artifact_record
        enriched["artifact"] = artifact_payload
    if manifest_path and manifest:
        try:
            _write_json_path(manifest_path, manifest)
        except Exception:
            pass
    if artifact_path and artifact_record:
        try:
            _write_json_path(artifact_path, artifact_record)
        except Exception:
            pass
    return enriched


def _summary_mode_requested(args: dict[str, Any]) -> bool:
    mode = str(args.get("response_mode") or "").strip().lower()
    return _truthy(args.get("summary_mode")) or mode in {"summary", "compact"}


def _entry_text(entry: Any) -> str:
    if isinstance(entry, dict):
        for key in ("text", "content", "line", "message", "data", "raw"):
            value = entry.get(key)
            if value is not None:
                return str(value)
        return " ".join(str(value) for value in entry.values() if value is not None)
    return str(entry)


def _compact_bash_payload(payload: dict[str, Any], *, max_chars: int = 4000) -> dict[str, Any]:
    entries = list(payload.get("entries") or []) if isinstance(payload.get("entries"), list) else []
    rendered = "\n".join(_entry_text(entry) for entry in entries)
    session = dict(payload.get("session") or {}) if isinstance(payload.get("session"), dict) else {}
    session_keys = ["bash_id", "status", "exit_code", "pid", "cwd", "command", "started_at", "ended_at", "duration_seconds", "env_keys"]
    compact_session = {key: session.get(key) for key in session_keys if key in session}
    compact = {
        "ok": payload.get("ok", True),
        "summary_mode": True,
        "quest_id": payload.get("quest_id"),
        "session": compact_session,
        "entry_count": len(entries),
        "output_tail": rendered[-max_chars:],
    }
    if "log_meta" in payload:
        compact["log_meta"] = payload.get("log_meta")
    if "summary" in payload:
        compact["summary"] = payload.get("summary")
    return compact


def _active_analysis_campaign_payload(services, root: Path, message: str) -> dict[str, Any]:
    campaign: dict[str, Any] = {}
    try:
        campaign = services.artifact.get_analysis_campaign(root, "active")
        if not isinstance(campaign, dict):
            campaign = {}
    except Exception:
        campaign = {}
    active_id = str(campaign.get("campaign_id") or "").strip() or None
    next_pending = str(campaign.get("next_pending_slice_id") or "").strip() or None
    pending_count = campaign.get("pending_slice_count")
    guidance = "Finish or close the active analysis campaign before selecting an outline or submitting a paper bundle."
    details = []
    if active_id:
        details.append(f"active_analysis_campaign_id={active_id}")
    if next_pending:
        details.append(f"next_pending_slice_id={next_pending}")
    if pending_count is not None:
        details.append(f"pending_slice_count={pending_count}")
    enhanced = message
    if details:
        enhanced = f"{message} ({'; '.join(details)}). {guidance}"
    return {
        "ok": False,
        "error": enhanced,
        "error_type": "ActiveAnalysisCampaignError",
        "active_analysis_campaign_id": active_id,
        "next_pending_slice_id": next_pending,
        "pending_slice_count": pending_count,
        "campaign": campaign or None,
        "guidance": guidance,
    }


def _is_active_analysis_campaign_error(exc: Exception) -> bool:
    return "analysis campaign is active" in str(exc).lower()


def _session_id(args: dict[str, Any]) -> str:
    return str(args.get("session_id") or "local").strip() or "local"


def _active_or_latest_quest_id(args: dict[str, Any], services=None) -> str | None:
    qid = str(args.get("quest_id") or "").strip()
    if qid:
        return qid
    store = StateStore()
    qid = store.active_quest_id(_session_id(args)) or ""
    if qid:
        return qid
    services = services or get_services()
    quests = services.quest.list_quests()
    if quests:
        return str(quests[0].get("quest_id") or "").strip() or None
    return None


def _quest_root(services, quest_id: str) -> Path:
    qid = str(quest_id or "").strip()
    if not qid:
        raise ValueError("quest_id is required")
    root = services.home / "quests" / qid
    if not (root / "quest.yaml").exists():
        raise FileNotFoundError(f"Unknown quest `{qid}`")
    return root


@_guard
def ds_doctor(args: dict[str, Any]) -> dict[str, Any]:
    return native_doctor()


@_guard
def ds_list_quests(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    items = services.quest.list_quests()[: _limit(args, default=50, maximum=500)]
    return {"quests": items, "count": len(items), "runtime_home": str(services.home)}


@_guard
def ds_get_quest_state(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return {"ok": False, "error": "No quest_id supplied and no active quest exists.", "quests": []}
    snapshot = services.quest.snapshot(quest_id)
    return {"quest_id": quest_id, "snapshot": snapshot if args.get("full") else compact_snapshot(snapshot)}


@_guard
def ds_set_active_quest(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id"):
        return {"ok": False, "error": err}
    services = get_services()
    quest_id = str(args["quest_id"])
    snapshot = services.quest.snapshot(quest_id)
    requested_stage = str(args.get("stage") or "").strip()
    stage = requested_stage or str(snapshot.get("active_anchor") or "").strip() or "preparing"
    relation = "session_only"
    if requested_stage:
        try:
            snapshot = services.quest.update_settings(quest_id, active_anchor=requested_stage)
            relation = "synced"
        except Exception as exc:
            relation = "not_synced"
            snapshot = services.quest.snapshot(quest_id)
            anchor_warning = f"active_stage was set for this Codex session, but quest active_anchor was not updated: {exc}"
        else:
            anchor_warning = "stage was treated as the current quest anchor and synchronized to quest.active_anchor."
    else:
        anchor_warning = "No stage supplied; active_stage follows the quest active_anchor."
    state = StateStore().set_active_quest(quest_id, _session_id(args), active_stage=stage)
    return {
        "state": state,
        "quest": compact_snapshot(snapshot),
        "active_stage": stage,
        "active_anchor": str((snapshot or {}).get("active_anchor") or ""),
        "stage_anchor_relation": relation,
        "anchor_semantics": "active_stage is the Hermes session routing label; active_anchor is the durable quest-stage anchor. When stage is supplied, the wrapper treats it as the desired current anchor and synchronizes both.",
        "warning": anchor_warning if relation != "synced" or requested_stage else None,
    }


@_guard
def ds_new_quest(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "goal"):
        return {"ok": False, "error": err}
    startup_contract = _build_startup_contract(args)
    if isinstance(startup_contract, tuple):
        _none, message = startup_contract
        return {"ok": False, "error": message}
    services = get_services()
    snapshot = services.quest.create(
        str(args.get("goal") or ""),
        quest_id=str(args.get("quest_id") or "").strip() or None,
        runner="codex",
        title=str(args.get("title") or "").strip() or None,
        startup_contract=startup_contract,
    )
    state = StateStore().set_active_quest(str(snapshot.get("quest_id")), _session_id(args), active_stage=str(snapshot.get("active_anchor") or "scout"))
    return {
        "quest": compact_snapshot(snapshot),
        "state": state,
        "workspace_mode": startup_contract.get("workspace_mode"),
        "decision_policy": startup_contract.get("decision_policy"),
        "final_goal": startup_contract.get("final_goal"),
        "delivery_mode": startup_contract.get("delivery_mode"),
        "startup_contract": startup_contract,
    }


@_guard
def ds_update_quest_mode(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id", "workspace_mode"):
        return {"ok": False, "error": err}
    workspace_mode = str(args.get("workspace_mode") or "").strip().lower()
    if workspace_mode not in WORKSPACE_MODE_VALUES:
        return {"ok": False, "error": "workspace_mode must be one of: autonomous, copilot."}

    existing_contract: dict[str, Any] = {}
    services = get_services()
    quest_id = str(args.get("quest_id") or "").strip()
    snapshot_before = services.quest.snapshot(quest_id)
    if isinstance(snapshot_before.get("startup_contract"), dict):
        existing_contract = dict(snapshot_before.get("startup_contract") or {})

    raw_decision_policy = str(args.get("decision_policy") or "").strip().lower()
    if raw_decision_policy and raw_decision_policy not in DECISION_POLICY_VALUES:
        return {"ok": False, "error": "decision_policy must be one of: autonomous, user_gated."}
    decision_policy = raw_decision_policy or ("autonomous" if workspace_mode == "autonomous" else "user_gated")

    raw_final_goal = str(args.get("final_goal") or existing_contract.get("final_goal") or "open_ended").strip().lower()
    if raw_final_goal not in FINAL_GOAL_VALUES:
        return {"ok": False, "error": "final_goal must be one of: paper, quality_result, idea_optimization, literature_scout, baseline_reproduction, analysis_report, open_ended."}
    final_goal = raw_final_goal

    need_research_paper = _optional_bool(
        args,
        "need_research_paper",
        bool(existing_contract.get("need_research_paper", final_goal == "paper")),
    )
    delivery_mode = str(args.get("delivery_mode") or existing_contract.get("delivery_mode") or ("paper_bundle" if need_research_paper else final_goal)).strip()
    completion_criteria = _clean_string_list(args.get("completion_criteria"))
    if not completion_criteria and isinstance(existing_contract.get("completion_criteria"), list):
        completion_criteria = _clean_string_list(existing_contract.get("completion_criteria"))

    raw_user_contract = args.get("startup_contract")
    user_contract = dict(raw_user_contract) if isinstance(raw_user_contract, dict) else {}
    mode_rationale = str(args.get("mode_rationale") or user_contract.get("mode_rationale") or "").strip()
    if not mode_rationale and workspace_mode == "copilot":
        mode_rationale = "agent_selected_copilot: Hermes returned this quest to user-gated copilot mode without changing the quest identity."
    if workspace_mode == "autonomous" and not mode_rationale:
        return {"ok": False, "error": "mode_rationale is required when switching an existing quest to autonomous mode."}

    startup_contract = {
        **existing_contract,
        **user_contract,
        "workspace_mode": workspace_mode,
        "decision_policy": decision_policy,
        "need_research_paper": need_research_paper,
        "final_goal": final_goal,
        "delivery_mode": delivery_mode,
        "completion_criteria": completion_criteria,
        "mode_selected_by": "codex_agent",
        "mode_rationale": mode_rationale,
    }
    snapshot = services.quest.update_settings(
        quest_id,
        workspace_mode=workspace_mode,
        decision_policy=decision_policy,
        need_research_paper=need_research_paper,
        final_goal=final_goal,
        delivery_mode=delivery_mode,
        completion_criteria=completion_criteria,
        mode_rationale=mode_rationale,
        startup_contract=startup_contract,
    )
    StateStore().set_active_quest(quest_id, _session_id(args), active_stage=str(snapshot.get("active_anchor") or "scout"))
    return {
        "quest": compact_snapshot(snapshot),
        "workspace_mode": workspace_mode,
        "decision_policy": decision_policy,
        "final_goal": final_goal,
        "delivery_mode": delivery_mode,
        "startup_contract": startup_contract,
    }


def _add_user_message_payload(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "message"):
        return {"ok": False, "error": err}
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required when no active quest exists"}
    record_only = _truthy(args.get("record_only")) or str(args.get("delivery_state") or "").strip().lower() == "record_only"
    if record_only:
        root = _quest_root(services, quest_id)
        timestamp = _utc_now()
        record = {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "role": "user",
            "content": str(args.get("message") or ""),
            "source": str(args.get("source") or "hermes-requirement"),
            "created_at": timestamp,
            "delivery_state": "record_only",
        }
        if args.get("stage"):
            record["skill_id"] = str(args.get("stage"))
        try:
            services.quest.bind_source(quest_id, record["source"])
        except Exception:
            pass
        _append_jsonl_path(root / ".ds" / "conversations" / "main.jsonl", record)
        _append_jsonl_path(
            root / ".ds" / "events.jsonl",
            {
                "type": "conversation.message",
                "quest_id": quest_id,
                "message_id": record["id"],
                "role": "user",
                "source": record["source"],
                "content": record["content"],
                "run_id": None,
                "skill_id": record.get("skill_id"),
                "reply_to_interaction_id": None,
                "client_message_id": None,
                "delivery_state": "record_only",
                "attachments": [],
                "created_at": timestamp,
            },
        )
        queue_path = root / ".ds" / "user_message_queue.json"
        queue_payload = _read_json_path(queue_path) if queue_path.exists() else {"version": 1, "pending": [], "completed": []}
        pending = [item for item in (queue_payload.get("pending") or []) if str(item.get("message_id") or "") != record["id"]]
        queue_payload["pending"] = pending
        queue_payload.setdefault("completed", [])
        queue_payload.setdefault("version", 1)
        _write_json_path(queue_path, queue_payload)
        try:
            services.quest._write_active_user_requirements(root, latest_requirement=record)
        except Exception:
            pass
        try:
            services.quest.update_runtime_state(quest_root=root, pending_user_message_count=len(pending))
        except Exception:
            pass
    else:
        record = services.quest.append_message(
            quest_id,
            role="user",
            content=str(args.get("message") or ""),
            source=str(args.get("source") or "hermes"),
            skill_id=str(args.get("stage") or "").strip() or None,
        )
    if args.get("stage"):
        try:
            services.quest.update_settings(quest_id, active_anchor=str(args.get("stage")))
            StateStore().set_active_stage(str(args.get("stage")), _session_id(args))
        except Exception:
            pass
    return {
        "quest_id": quest_id,
        "message": record,
        "record_only": record_only,
        "snapshot": compact_snapshot(services.quest.snapshot(quest_id)),
    }


@_guard
def ds_add_user_message(args: dict[str, Any]) -> dict[str, Any]:
    return _add_user_message_payload(args)


@_guard
def ds_record_user_requirement(args: dict[str, Any]) -> dict[str, Any]:
    args = dict(args)
    args["record_only"] = True
    args.setdefault("source", "hermes-requirement")
    return _add_user_message_payload(args)


def _read_events_payload(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required"}
    root = _quest_root(services, quest_id)
    path = root / ".ds" / "events.jsonl"
    events = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-_limit(args, 20, 200):]:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                events.append({"raw": line})
    return {"quest_id": quest_id, "events": events, "count": len(events), "path": str(path)}


@_guard
def ds_events(args: dict[str, Any]) -> dict[str, Any]:
    return _read_events_payload(args)


# Hidden compatibility alias for the former Hermes-style tool name.
deepscientist_events = ds_events


@_guard
def ds_read_quest_documents(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required"}
    docs = services.quest.list_documents(quest_id)
    names = args.get("names") or []
    if isinstance(names, str):
        names = [names]
    names = [str(x) for x in names if str(x).strip()]
    if not names:
        return {"quest_id": quest_id, "documents": docs, "count": len(docs)}
    max_chars = max(100, min(int(args.get("max_chars") or 12000), 200000))
    selected = []
    for name in names:
        hit = next((d for d in docs if name in {str(d.get("document_id")), str(d.get("title")), Path(str(d.get("path") or "")).name}), None)
        if not hit:
            selected.append({"name": name, "ok": False, "error": "document not found"})
            continue
        item = dict(hit)
        if args.get("include_content", True):
            path = Path(str(hit.get("path") or ""))
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                item["content"] = text[:max_chars]
                item["truncated"] = len(text) > max_chars
            except Exception as exc:
                item["read_error"] = str(exc)
        selected.append(item)
    return {"quest_id": quest_id, "documents": selected, "count": len(selected)}


@_guard
def ds_memory_search(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "query"):
        return {"ok": False, "error": err}
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    scope = str(args.get("scope") or ("both" if quest_id else "global"))
    quest_root = _quest_root(services, quest_id) if quest_id and scope in {"quest", "both"} else None
    kind_info = None
    kind_arg = str(args.get("kind") or "").strip()
    if kind_arg:
        try:
            kind_info = _normalize_memory_kind(kind_arg)
        except ValueError as exc:
            return _memory_kind_error_payload(exc)
    requested_limit = _limit(args)
    service_limit = 500 if kind_info and kind_info.get("semantic_tag") else requested_limit
    matches = services.memory.search(
        str(args.get("query") or ""),
        scope=scope,
        quest_root=quest_root,
        limit=service_limit,
        kind=str(kind_info["normalized"]) if kind_info else None,
    )
    if kind_info and kind_info.get("semantic_tag"):
        semantic_tag = str(kind_info["semantic_tag"])
        filtered = []
        for match in matches:
            tags = {str(tag) for tag in (match.get("tags") or [])}
            if not tags:
                try:
                    card = services.memory.read_card(
                        path=str(match.get("path") or ""),
                        scope=str(match.get("scope") or scope),
                        quest_root=quest_root,
                    )
                    tags = {str(tag) for tag in (card.get("metadata", {}).get("tags") or [])}
                except Exception:
                    tags = set()
            if semantic_tag in tags:
                filtered.append(match)
        matches = filtered[:requested_limit]
    payload = {"matches": matches, "count": len(matches), "scope": scope, "quest_id": quest_id}
    if kind_info:
        payload["memory_kind_alias"] = kind_info
    return payload


@_guard
def ds_memory_read(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    scope = str(args.get("scope") or ("quest" if quest_id else "global"))
    quest_root = _quest_root(services, quest_id) if quest_id and scope == "quest" else None
    card = services.memory.read_card(card_id=str(args.get("card_id") or "").strip() or None, path=str(args.get("path") or "").strip() or None, scope=scope, quest_root=quest_root)
    return {"card": card}


def _memory_item_matches_semantic_tag(services: Any, item: dict[str, Any], semantic_tag: str, *, default_scope: str, quest_root: Path | None) -> bool:
    tags = {str(tag) for tag in (item.get("tags") or [])}
    if not tags:
        try:
            card = services.memory.read_card(
                path=str(item.get("path") or ""),
                scope=str(item.get("scope") or default_scope),
                quest_root=quest_root,
            )
            tags = {str(tag) for tag in (card.get("metadata", {}).get("tags") or [])}
        except Exception:
            tags = set()
    return semantic_tag in tags


@_guard
def ds_memory_list_recent(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    requested_scope = str(args.get("scope") or ("quest" if quest_id else "global")).strip().lower() or "global"
    if requested_scope not in {"quest", "global", "both"}:
        return {"ok": False, "error": "scope must be `quest`, `global`, or `both`."}
    scope = requested_scope
    if scope in {"quest", "both"} and not quest_id:
        scope = "global"
    quest_root = _quest_root(services, quest_id) if quest_id and scope in {"quest", "both"} else None
    kind_info = None
    kind_arg = str(args.get("kind") or "").strip()
    if kind_arg:
        try:
            kind_info = _normalize_memory_kind(kind_arg)
        except ValueError as exc:
            return _memory_kind_error_payload(exc)
    requested_limit = _limit(args, default=10, maximum=500)
    service_limit = 500 if kind_info and kind_info.get("semantic_tag") else requested_limit
    scopes = ["quest", "global"] if scope == "both" else [scope]
    items: list[dict[str, Any]] = []
    for resolved_scope in scopes:
        if resolved_scope == "quest" and quest_root is None:
            continue
        recent = services.memory.list_recent(
            scope=resolved_scope,
            quest_root=quest_root if resolved_scope == "quest" else None,
            limit=service_limit,
            kind=str(kind_info["normalized"]) if kind_info else None,
        )
        for item in recent:
            enriched = dict(item)
            enriched.setdefault("scope", resolved_scope)
            items.append(enriched)
    if len(scopes) > 1:
        try:
            items.sort(key=services.memory._card_sort_key, reverse=True)  # type: ignore[attr-defined]
        except Exception:
            items.sort(key=lambda item: (str(item.get("updated_at") or ""), str(item.get("path") or "")), reverse=True)
    if kind_info and kind_info.get("semantic_tag"):
        semantic_tag = str(kind_info["semantic_tag"])
        filtered: list[dict[str, Any]] = []
        for item in items:
            item_scope = str(item.get("scope") or scope)
            item_quest_root = quest_root if item_scope == "quest" else None
            if _memory_item_matches_semantic_tag(services, item, semantic_tag, default_scope=item_scope, quest_root=item_quest_root):
                filtered.append(item)
        items = filtered
    items = items[:requested_limit]
    payload = {"items": items, "count": len(items), "scope": scope, "requested_scope": requested_scope, "quest_id": quest_id}
    if kind_info:
        payload["memory_kind_alias"] = kind_info
    return payload


@_guard
def ds_memory_write(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "title"):
        return {"ok": False, "error": err}
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    scope = str(args.get("scope") or ("quest" if quest_id else "global"))
    quest_root = _quest_root(services, quest_id) if quest_id and scope == "quest" else None
    try:
        kind_info = _normalize_memory_kind(args.get("kind") or "knowledge")
    except ValueError as exc:
        return _memory_kind_error_payload(exc)
    tags = _normalize_tags(args.get("tags"))
    semantic_tag = kind_info.get("semantic_tag")
    if semantic_tag and semantic_tag not in tags:
        tags.append(str(semantic_tag))
    metadata = args.get("metadata") if isinstance(args.get("metadata"), dict) else {}
    metadata = dict(metadata or {})
    metadata["requested_kind"] = kind_info["requested"]
    metadata["normalized_kind"] = kind_info["normalized"]
    if kind_info.get("alias_applied"):
        metadata["kind_alias"] = {"requested": kind_info["requested"], "normalized": kind_info["normalized"]}
    card = services.memory.write_card(
        scope=scope,
        kind=str(kind_info["normalized"]),
        title=str(args.get("title") or ""),
        body=str(args.get("body") if args.get("body") is not None else args.get("content") or ""),
        markdown=str(args.get("markdown") or "") or None,
        quest_root=quest_root,
        quest_id=quest_id,
        tags=tags,
        metadata=metadata,
    )
    return {"card": card, "quest_id": quest_id, "scope": scope, "memory_kind_alias": kind_info}


@_guard
def ds_artifact_record(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id"):
        return {"ok": False, "error": err}
    services = get_services()
    root = _quest_root(services, str(args["quest_id"]))
    payload = dict(args.get("payload") or {}) if isinstance(args.get("payload"), dict) else {}
    top_kind = str(args.get("kind") or "").strip()
    if payload:
        if top_kind and not str(payload.get("kind") or "").strip():
            payload["kind"] = top_kind
        if args.get("status") is not None and not str(payload.get("status") or "").strip():
            payload["status"] = str(args.get("status") or "")
        if args.get("summary") is not None and not str(payload.get("summary") or "").strip():
            payload["summary"] = str(args.get("summary") or "")
    else:
        payload = {
            "kind": top_kind or "report",
            "status": str(args.get("status") or "completed"),
            "summary": str(args.get("summary") or "Codex-native artifact record."),
            "source": {"kind": "codex", "role": "native-plugin"},
        }
    record = services.artifact.record(root, payload, checkpoint=args.get("checkpoint") if isinstance(args.get("checkpoint"), bool) else None)
    artifact_ok = bool(record.get("ok")) if isinstance(record, dict) and "ok" in record else True
    response: dict[str, Any] = {"artifact": record, "artifact_ok": artifact_ok, "quest_id": str(args["quest_id"]), "payload_kind": payload.get("kind")}
    if not artifact_ok:
        errors = record.get("errors") if isinstance(record, dict) else None
        message = "; ".join(str(item) for item in errors) if isinstance(errors, list) else str(errors or "artifact record failed")
        response.update({"ok": False, "error": message})
    return response


@_guard
def ds_confirm_baseline(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id", "baseline_path"):
        return {"ok": False, "error": err}
    services = get_services()
    root = _quest_root(services, str(args["quest_id"]))
    return services.artifact.confirm_baseline(
        root,
        baseline_path=str(args.get("baseline_path") or ""),
        comment=args.get("comment"),
        baseline_id=str(args.get("baseline_id") or "").strip() or None,
        variant_id=str(args.get("variant_id") or "").strip() or None,
        summary=str(args.get("summary") or "").strip() or None,
        metric_contract=args.get("metric_contract") if isinstance(args.get("metric_contract"), dict) else None,
    )


@_guard
def ds_waive_baseline(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id", "reason"):
        return {"ok": False, "error": err}
    services = get_services()
    root = _quest_root(services, str(args["quest_id"]))
    return services.artifact.waive_baseline(root, reason=str(args.get("reason") or ""), comment=args.get("comment"))


@_guard
def ds_attach_baseline(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id", "baseline_id"):
        return {"ok": False, "error": err}
    services = get_services()
    root = _quest_root(services, str(args["quest_id"]))
    return services.artifact.attach_baseline(root, str(args.get("baseline_id") or ""), variant_id=str(args.get("variant_id") or "").strip() or None)


@_guard
def ds_create_local_baseline(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id", "baseline_id"):
        return {"ok": False, "error": err}
    services = get_services()
    quest_id = str(args["quest_id"])
    root = _quest_root(services, quest_id)
    baseline_id = _safe_slug(args.get("baseline_id"), "local_baseline")
    filename = _safe_slug(args.get("filename") or "baseline.md", "baseline.md")
    if not filename.endswith(".md"):
        filename = f"{filename}.md"
    baseline_root = root / "baselines" / "local" / baseline_id
    baseline_root.mkdir(parents=True, exist_ok=True)
    baseline_path = baseline_root / filename
    overwrite = bool(args.get("overwrite", False))
    if baseline_path.exists() and not overwrite:
        return {
            "ok": False,
            "error": f"Local baseline already exists: {baseline_path}. Pass overwrite=true to replace it.",
            "baseline_path": str(baseline_path),
            "baseline_id": baseline_id,
        }
    source_path = str(args.get("source_path") or "").strip()
    if source_path:
        source = Path(source_path).expanduser()
        if not source.exists():
            return {"ok": False, "error": f"source_path not found: {source}", "baseline_id": baseline_id}
        if source.is_dir():
            if any(baseline_root.iterdir()) and not overwrite:
                return {
                    "ok": False,
                    "error": f"Local baseline directory already has files: {baseline_root}. Pass overwrite=true to replace it.",
                    "baseline_root": str(baseline_root),
                    "baseline_id": baseline_id,
                }
            if overwrite and baseline_root.exists():
                for child in baseline_root.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
            shutil.copytree(source, baseline_root, dirs_exist_ok=True)
            if not baseline_path.exists():
                readme = baseline_root / "README.md"
                baseline_path = readme if readme.exists() else next((p for p in baseline_root.glob("*.md") if p.is_file()), baseline_path)
        else:
            shutil.copy2(source, baseline_path)
    else:
        content = str(args.get("content") or "").strip()
        if not content:
            title = str(args.get("title") or baseline_id).strip() or baseline_id
            summary = str(args.get("summary") or "Local baseline contract created by Hermes-native DeepScientist.").strip()
            content = f"# {title}\n\n{summary}\n"
        baseline_path.write_text(content.rstrip() + "\n", encoding="utf-8")
    confirm_args = {
        "quest_id": quest_id,
        "baseline_path": str(baseline_path),
        "baseline_id": baseline_id,
    }
    if args.get("variant_id"):
        confirm_args["variant_id"] = str(args.get("variant_id"))
    if args.get("summary"):
        confirm_args["summary"] = str(args.get("summary"))
    if isinstance(args.get("metric_contract"), dict):
        confirm_args["metric_contract"] = args.get("metric_contract")
    return {
        "quest_id": quest_id,
        "baseline_id": baseline_id,
        "baseline_root": str(baseline_root),
        "baseline_path": str(baseline_path),
        "confirm_args": confirm_args,
        "next_tool": "ds_confirm_baseline",
        "guidance": "Pass confirm_args to ds_confirm_baseline when this local baseline is ready to open the baseline gate.",
    }


@_guard
def ds_submit_idea(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id", "title"):
        return {"ok": False, "error": err}
    services = get_services()
    root = _quest_root(services, str(args["quest_id"]))
    keys = ["mode","submission_mode","idea_id","lineage_intent","title","problem","hypothesis","mechanism","method_brief","selection_scores","mechanism_family","change_layer","source_lens","expected_gain","evidence_paths","risks","decision_reason","foundation_ref","foundation_reason","next_target","draft_markdown","source_candidate_id"]
    kwargs = {k: args[k] for k in keys if k in args}
    return services.artifact.submit_idea(root, **kwargs)


@_guard
def ds_list_research_branches(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id"):
        return {"ok": False, "error": err}
    services = get_services()
    return services.artifact.list_research_branches(_quest_root(services, str(args["quest_id"])))


def _artifact_root_from_args(args: dict[str, Any], services: Any) -> tuple[str | None, Path | None, dict[str, Any] | None]:
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return None, None, {"ok": False, "error": "quest_id is required when no active quest exists"}
    return quest_id, _quest_root(services, quest_id), None


@_guard
def ds_resolve_runtime_refs(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id, root, error = _artifact_root_from_args(args, services)
    if error:
        return error
    payload = services.artifact.resolve_runtime_refs(root)  # type: ignore[arg-type]
    payload.setdefault("quest_id", quest_id)
    return payload


@_guard
def ds_get_paper_contract_health(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id, root, error = _artifact_root_from_args(args, services)
    if error:
        return error
    payload = services.artifact.get_paper_contract_health(
        root,  # type: ignore[arg-type]
        detail=str(args.get("detail") or "summary").strip().lower() or "summary",
    )
    payload.setdefault("quest_id", quest_id)
    return payload


@_guard
def ds_get_global_status(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id, root, error = _artifact_root_from_args(args, services)
    if error:
        return error
    payload = services.artifact.get_global_status(
        root,  # type: ignore[arg-type]
        detail=str(args.get("detail") or "brief").strip().lower() or "brief",
        locale=str(args.get("locale") or "zh").strip().lower() or "zh",
    )
    payload.setdefault("quest_id", quest_id)
    return payload


@_guard
def ds_get_method_scoreboard(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id, root, error = _artifact_root_from_args(args, services)
    if error:
        return error
    payload = services.artifact.refresh_method_scoreboard(root)  # type: ignore[arg-type]
    payload.setdefault("quest_id", quest_id)
    return payload


@_guard
def ds_get_optimization_frontier(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id, root, error = _artifact_root_from_args(args, services)
    if error:
        return error
    payload = services.artifact.get_optimization_frontier(root)  # type: ignore[arg-type]
    payload.setdefault("quest_id", quest_id)
    return payload


@_guard
def ds_get_conversation_context(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id, root, error = _artifact_root_from_args(args, services)
    if error:
        return error
    payload = services.artifact.get_conversation_context(
        root,  # type: ignore[arg-type]
        limit=_limit(args, default=12, maximum=200),
        include_attachments=_truthy(args.get("include_attachments")),
    )
    payload.setdefault("quest_id", quest_id)
    return payload


@_guard
def ds_record_main_experiment(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id", "run_id"):
        return {"ok": False, "error": err}
    services = get_services()
    root = _quest_root(services, str(args["quest_id"]))
    keys = ["run_id","title","hypothesis","setup","execution","results","conclusion","metric_rows","metrics_summary","metric_contract","evidence_paths","changed_files","config_paths","notes","dataset_scope","verdict","status","baseline_id","baseline_variant_id","evaluation_summary","strict_metric_contract"]
    kwargs = {k: args[k] for k in keys if k in args}
    return services.artifact.record_main_experiment(root, **kwargs)


@_guard
def ds_create_analysis_campaign(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id", "campaign_title", "campaign_goal", "slices"):
        return {"ok": False, "error": err}
    services = get_services()
    root = _quest_root(services, str(args["quest_id"]))
    keys = ["campaign_title","campaign_goal","parent_run_id","slices","campaign_origin","selected_outline_ref","research_questions","experimental_designs","todo_items"]
    kwargs = {k: args[k] for k in keys if k in args}
    return services.artifact.create_analysis_campaign(root, **kwargs)


@_guard
def ds_get_analysis_campaign(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id"):
        return {"ok": False, "error": err}
    services = get_services()
    quest_id = str(args["quest_id"])
    root = _quest_root(services, quest_id)
    campaign_id = str(args.get("campaign_id") or "active").strip() or "active"
    campaign = services.artifact.get_analysis_campaign(root, campaign_id)
    return {"quest_id": quest_id, "campaign_id": campaign_id, "campaign": campaign}


@_guard
def ds_record_analysis_slice(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id", "campaign_id", "slice_id"):
        return {"ok": False, "error": err}
    services = get_services()
    root = _quest_root(services, str(args["quest_id"]))
    keys = ["campaign_id","slice_id","status","setup","execution","results","evidence_paths","metric_rows","deviations","claim_impact","reviewer_resolution","manuscript_update_hint","next_recommendation","dataset_scope","subset_approval_ref","comparison_baselines","evaluation_summary"]
    kwargs = {k: args[k] for k in keys if k in args}
    return services.artifact.record_analysis_slice(root, **kwargs)


@_guard
def ds_submit_paper_outline(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id"):
        return {"ok": False, "error": err}
    services = get_services()
    root = _quest_root(services, str(args["quest_id"]))
    keys = ["mode","outline_id","title","note","story","ten_questions","detailed_outline","review_result","selected_reason"]
    kwargs = {k: args[k] for k in keys if k in args}
    if "mode" in kwargs:
        mode = str(kwargs.get("mode") or "candidate").strip().lower() or "candidate"
        if mode == "selected":
            mode = "select"
        if mode not in {"candidate", "select", "revise"}:
            return {
                "ok": False,
                "error": "submit_paper_outline mode must be `candidate`, `select`, or `revise` (`selected` is accepted as an alias for `select`).",
                "allowed_modes": ["candidate", "select", "revise"],
                "mode_aliases": {"selected": "select"},
            }
        kwargs["mode"] = mode
    try:
        return services.artifact.submit_paper_outline(root, **kwargs)
    except ValueError as exc:
        if _is_active_analysis_campaign_error(exc):
            return _active_analysis_campaign_payload(services, root, str(exc))
        raise


@_guard
def ds_list_paper_outlines(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id, root, error = _artifact_root_from_args(args, services)
    if error:
        return error
    payload = services.artifact.list_paper_outlines(root)  # type: ignore[arg-type]
    payload.setdefault("quest_id", quest_id)
    return payload


@_guard
def ds_submit_paper_bundle(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id"):
        return {"ok": False, "error": err}
    services = get_services()
    root = _quest_root(services, str(args["quest_id"]))
    keys = ["title","summary","outline_path","draft_path","writing_plan_path","references_path","claim_evidence_map_path","compile_report_path","pdf_path","latex_root_path","prepare_open_source"]
    kwargs = {k: args[k] for k in keys if k in args}
    try:
        result = services.artifact.submit_paper_bundle(root, **kwargs)
        return _enrich_paper_bundle_result(services, root, result, kwargs)
    except ValueError as exc:
        if _is_active_analysis_campaign_error(exc):
            return _active_analysis_campaign_payload(services, root, str(exc))
        raise


@_guard
def ds_refresh_summary(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id, root, error = _artifact_root_from_args(args, services)
    if error:
        return error
    payload = services.artifact.refresh_summary(root, reason=str(args.get("reason") or "").strip() or None)  # type: ignore[arg-type]
    payload.setdefault("quest_id", quest_id)
    return payload


@_guard
def ds_arxiv(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id, root, error = _artifact_root_from_args(args, services)
    if error:
        return error
    payload = services.artifact.arxiv(
        str(args.get("paper_id") or "").strip() or None,
        mode=str(args.get("mode") or "read").strip().lower() or "read",
        full_text=_truthy(args.get("full_text")),
        quest_root=root,
    )
    payload.setdefault("quest_id", quest_id)
    return payload


@_guard
def ds_bash_exec(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    summary_mode = _summary_mode_requested(args)
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required"}
    root = _quest_root(services, quest_id)
    operation = str(args.get("operation") or ("run" if args.get("command") else "list")).strip().lower()
    if operation == "list":
        payload = {"quest_id": quest_id, "sessions": services.bash.list_sessions(root, limit=_limit(args, 20, 200)), "summary": services.bash.summary(root)}
        if summary_mode:
            payload = {
                "quest_id": quest_id,
                "summary_mode": True,
                "session_count": len(payload.get("sessions") or []),
                "summary": payload.get("summary"),
            }
        return payload
    bash_id = str(args.get("bash_id") or "").strip()
    if operation in {"status", "read", "wait", "stop"}:
        if not bash_id:
            bash_id = services.bash.resolve_session_id(root)
        if operation == "stop":
            session = services.bash.request_stop(root, bash_id, reason=str(args.get("reason") or "codex_native_stop"), force=bool(args.get("force")))
        elif operation == "wait":
            session = services.bash.wait_for_session(root, bash_id, timeout_seconds=int(args.get("timeout_seconds") or 30))
        else:
            session = services.bash.get_session(root, bash_id)
        entries, meta = services.bash.read_log_entries(root, bash_id, limit=_limit(args, 40, 500), prefer_visible=True)
        payload = {"quest_id": quest_id, "session": session, "entries": entries, "log_meta": meta}
        return _compact_bash_payload(payload) if summary_mode else payload
    if operation != "run":
        return {"ok": False, "error": f"Unknown ds_bash_exec operation: {operation}"}
    if err := _require(args, "command"):
        return {"ok": False, "error": err}
    from deepscientist.execution_context import ExecutionContext
    project_root = services.home.parent.resolve()
    allow_project_root = bool(args.get("allow_project_root"))
    context_worktree_root = project_root if allow_project_root else root
    requested_workdir = str(args.get("workdir") or "").strip() or None
    if allow_project_root and requested_workdir is None:
        requested_workdir = str(root)
    env_payload = _coerce_env(args.get("env"))
    if allow_project_root:
        env_payload.setdefault("DEEPSCIENTIST_PROJECT_ROOT", str(project_root))
        existing_pythonpath = env_payload.get("PYTHONPATH") or os.environ.get("PYTHONPATH", "")
        pythonpath_parts = [part for part in existing_pythonpath.split(os.pathsep) if part]
        project_plugins = project_root / ".codex" / "plugins"
        if project_plugins.exists():
            plugin_parent = str(project_plugins.resolve())
            if plugin_parent not in pythonpath_parts:
                pythonpath_parts.insert(0, plugin_parent)
        if pythonpath_parts:
            env_payload["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    context = ExecutionContext(home=services.home, quest_id=quest_id, quest_root=root, run_id=None, active_anchor=None, conversation_id=f"codex:{quest_id}", agent_role="codex", worker_id=None, worktree_root=context_worktree_root, team_mode=None)
    session = services.bash.start_session(context, command=str(args.get("command") or ""), mode="exec", workdir=requested_workdir, env=env_payload, timeout_seconds=int(args.get("timeout_seconds") or 120), comment=args.get("comment"))
    if args.get("wait", True):
        session = services.bash.wait_for_session(root, str(session.get("bash_id")), timeout_seconds=int(args.get("timeout_seconds") or 120))
    entries, meta = services.bash.read_log_entries(root, str(session.get("bash_id")), limit=_limit(args, 40, 500), prefer_visible=True)
    payload = {"quest_id": quest_id, "session": session, "entries": entries, "log_meta": meta}
    return _compact_bash_payload(payload) if summary_mode else payload


@_guard
def ds_workflow_smoke_report(args: dict[str, Any]) -> dict[str, Any]:
    """Return a lightweight DeepScientist full-workflow checklist.

    This intentionally does not train or mutate experiment artifacts. It gives a
    canonical tool sequence and path readiness report for Hermes-only DS runs.
    """
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required"}
    checks: dict[str, Any] = {}
    for key, label in (("dataset_path", "dataset"), ("paper_path", "paper"), ("report_dir", "report_dir")):
        raw = str(args.get(key) or "").strip()
        if not raw:
            checks[label] = {"provided": False, "exists": False, "path": None}
            continue
        path = Path(raw).expanduser()
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        checks[label] = {
            "provided": True,
            "exists": resolved.exists(),
            "is_file": resolved.is_file(),
            "is_dir": resolved.is_dir(),
            "path": str(resolved),
        }
    try:
        snapshot = compact_snapshot(services.quest.snapshot(quest_id))
    except Exception:
        snapshot = {"quest_id": quest_id}
    recommended_sequence = [
        {
            "id": "dataset_inspection",
            "tool": "ds_artifact_record",
            "purpose": "Record dataset label/schema inspection before any claimed task mapping.",
        },
        {
            "id": "baseline",
            "tool": "ds_create_local_baseline -> ds_confirm_baseline",
            "purpose": "Create or attach the minimal baseline and explicitly open the baseline gate.",
        },
        {
            "id": "experiment",
            "tool": "ds_bash_exec(summary_mode=true) + ds_record_main_experiment",
            "purpose": "Run the quest-local command when provenance matters, then record metrics/evidence.",
        },
        {
            "id": "analysis",
            "tool": "ds_create_analysis_campaign -> ds_record_analysis_slice",
            "purpose": "Record at least one analysis slice or rollup for limitations and evidence checks.",
        },
        {
            "id": "paper_bundle",
            "tool": "ds_submit_paper_outline -> ds_submit_paper_bundle",
            "purpose": "Submit Markdown/LaTeX paper bundle; wrapper repairs Markdown section counts and latest anchor guidance.",
        },
        {
            "id": "report_summary",
            "tool": "ds_artifact_record",
            "purpose": "Record final verification, error log, and upgrade summary paths.",
        },
    ]
    required_labels = ("dataset", "paper")
    ready = all(checks[name].get("provided") and checks[name].get("exists") for name in required_labels)
    return {
        "quest_id": quest_id,
        "snapshot": snapshot,
        "checks": checks,
        "recommended_sequence": recommended_sequence,
        "ready": ready,
        "summary": "Hermes-only DeepScientist smoke checklist covers dataset inspection, baseline, experiment, analysis, paper_bundle, and final report summary.",
    }


STRICT_RESEARCH_RULES = [
    "预印本论文：保留一年前发表且被引用数量大于10的；近一年发表不看引用量但必须有顶尖研究机构证据；用户指定的一律保留并标注。",
    "会议论文：保留已录用且满足 CCF-A、CCF-B、CORE-A、CORE-A* 任一条件的论文。",
    "会议论文被拒：非 desk reject 且有预印本时改按预印本规则；desk reject 不保留，除非用户指定。",
    "期刊论文：保留已录用且满足 CCF A、CCF B、中科院1区、中科院2区、JCR Q1、JCR Q2 任一条件的论文。",
    "筛选后数量不足时必须继续广泛调研，不得提前深读或写作。",
]


def _plugin_root() -> Path:
    return Path(__file__).resolve().parent


def _strict_reference_dir(services: Any, quest_id: str) -> Path:
    root = _quest_root(services, quest_id)
    reference_dir = root / "reference"
    reference_dir.mkdir(parents=True, exist_ok=True)
    return reference_dir


def _default_target_count(args: dict[str, Any]) -> int:
    raw = args.get("target_count")
    if raw not in (None, ""):
        try:
            return max(1, int(raw))
        except Exception:
            pass
    complexity = str(args.get("complexity") or "").strip().lower()
    return {"small": 8, "medium": 15, "large": 25, "survey": 40}.get(complexity, 15)


def _candidate_template(quest_id: str, target_count: int, intent: str) -> str:
    return f"""# candidate_references

Quest: `{quest_id}`
Strict research intent: {intent or 'strict literature research'}
Target retained references: {target_count}

Broadly collect candidates here before deep reading. Run `ds_paper_reliability_verify` for each candidate once the pool is large enough, using the bundled `paper_reliability_verifier`, then mark status.

| Status | Title | DOI | Link | Year | Authors/Institutions | Source | Reliability card | Retain/reject reason | Notes |
|---|---|---|---|---|---|---|---|---|---|
"""


def _ensure_candidate_file(reference_dir: Path, quest_id: str, target_count: int = 15, intent: str = "") -> Path:
    path = reference_dir / "candidate_references.md"
    if not path.exists():
        path.write_text(_candidate_template(quest_id, target_count, intent), encoding="utf-8")
    return path


def _split_markdown_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    parts = re.split(r"(?<!\\)\|", text)
    return [part.strip().replace("\\|", "|") for part in parts]


def _escape_md_cell(value: Any) -> str:
    return str(value or "").strip().replace("|", "\\|").replace("\n", "<br>")


def _candidate_row(values: dict[str, Any]) -> str:
    ordered = [
        "status",
        "title",
        "doi",
        "link",
        "year",
        "authors",
        "source",
        "evidence_card",
        "retain_reject_reason",
        "note",
    ]
    return "| " + " | ".join(_escape_md_cell(values.get(key)) for key in ordered) + " |\n"


def _candidate_record_from_row(line: str) -> dict[str, str] | None:
    cells = _split_markdown_row(line)
    if len(cells) < 10:
        return None
    keys = ["status", "title", "doi", "link", "year", "authors", "source", "evidence_card", "retain_reject_reason", "note"]
    return {key: cells[idx] if idx < len(cells) else "" for idx, key in enumerate(keys)}


def _candidate_key_text(record: dict[str, Any], key_field: str | None = None) -> list[str]:
    fields = [key_field] if key_field else ["doi", "link", "title"]
    values = []
    for field in fields:
        if not field:
            continue
        value = str(record.get(field) or "").strip()
        if value:
            values.append(norm_key(value))
    return values


def norm_key(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _download_url_to_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "DeepScientist-Hermes/0.2 paper-fetch"})
    with urlopen(req, timeout=60) as response:
        return response.read()


def _extract_arxiv_id(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    match = re.search(r"(?:arxiv\.org/(?:abs|pdf)/|arXiv:)([0-9]{4}\.[0-9]{4,5}(?:v\d+)?|[a-z\-]+/[0-9]{7}(?:v\d+)?)", text, re.I)
    if match:
        return match.group(1).removesuffix(".pdf")
    if re.fullmatch(r"[0-9]{4}\.[0-9]{4,5}(?:v\d+)?|[a-z\-]+/[0-9]{7}(?:v\d+)?", text, re.I):
        return text.removesuffix(".pdf")
    return ""


def _openreview_id(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    match = re.search(r"openreview\.net/(?:forum|pdf)\?id=([^&#]+)", text)
    if match:
        return match.group(1)
    return text if "/" not in text and " " not in text and "." not in text else ""


def _resolve_pdf_url(args: dict[str, Any]) -> tuple[str, str]:
    explicit = str(args.get("pdf_url") or args.get("url") or "").strip()
    if explicit and (explicit.lower().endswith(".pdf") or "/pdf" in urlparse(explicit).path.lower()):
        return explicit, "direct_pdf"
    arxiv_id = _extract_arxiv_id(args.get("arxiv_id") or args.get("arxiv_url") or explicit)
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf", "arxiv"
    openreview_id = _openreview_id(args.get("openreview_id") or explicit)
    if openreview_id:
        return f"https://openreview.net/pdf?id={openreview_id}", "openreview"
    pmlr = str(args.get("pmlr_url") or explicit or "").strip()
    if "proceedings.mlr.press" in pmlr:
        if pmlr.lower().endswith(".pdf"):
            return pmlr, "pmlr"
        try:
            html = _download_url_to_bytes(pmlr).decode("utf-8", errors="replace")
            match = re.search(r"href=[\"']([^\"']+\.pdf)[\"']", html, re.I)
            if match:
                href = match.group(1)
                if href.startswith("http"):
                    return href, "pmlr"
                parsed = urlparse(pmlr)
                base = f"{parsed.scheme}://{parsed.netloc}"
                return base + (href if href.startswith("/") else "/" + href), "pmlr"
        except Exception:
            pass
    if explicit:
        return explicit, "url_unclassified"
    return "", "missing_url"


def _download_url_candidates(canonical_url: str, source_kind: str) -> list[str]:
    """Return download attempts while preserving the canonical URL in ledgers.

    arXiv occasionally serves the extensionless `/pdf/<id>` route when the
    equivalent `/pdf/<id>.pdf` route is flaky. Keep the canonical URL stable,
    but retry the extensionless route before reporting the paper unreachable.
    """
    urls = [canonical_url]
    parsed = urlparse(canonical_url)
    if parsed.netloc.lower().endswith("arxiv.org") and parsed.path.lower().startswith("/pdf/") and parsed.path.lower().endswith(".pdf"):
        extensionless = canonical_url[:-4]
        if extensionless not in urls:
            urls.append(extensionless)
    elif source_kind == "arxiv":
        arxiv_id = _extract_arxiv_id(canonical_url)
        if arxiv_id:
            extensionless = f"https://arxiv.org/pdf/{arxiv_id}"
            if extensionless not in urls:
                urls.append(extensionless)
    return urls


def _pdf_page_count(data: bytes) -> int | None:
    if not data:
        return None
    try:
        return len(set(re.findall(rb"/Type\s*/Page\b", data))) or None
    except Exception:
        return None


@_guard
def ds_strict_research_prepare(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required when no active quest exists"}
    target_count = _default_target_count(args)
    intent = str(args.get("intent") or "").strip()
    reference_dir = _strict_reference_dir(services, quest_id)
    candidate_path = _ensure_candidate_file(reference_dir, quest_id, target_count, intent)
    cards_dir = reference_dir / "reliability_cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    workflow = [
        "广泛查阅相关论文并用 ds_strict_research_upsert_candidate 维护 candidate_references.md；此阶段不急着深读。",
        "候选数量足够后，对候选分小 batch 调用 ds_paper_reliability_verify；每篇返回 paper/tier/quality_flags/warnings 和 reliability_card_path。",
        "每完成一个小 batch，立刻用 ds_strict_research_upsert_candidate 更新 candidate_references.md 中对应论文的 status、Reliability card、Retain/reject reason，再进入下一 batch。",
        "完成所有候选 verify 和标记后，清理 candidate_references.md：删除不能参考的 rejected/do-not-use 论文，保留 retained/needs-human-review 及用户指定论文。",
        "按 strict-research 筛选规则保留/剔除；数量不足则继续调研。",
        "保留列表足够后用 ds_paper_fetch 将 PDF 下载到 reference/pdfs/，记录 canonical_url、sha256、page_count 和 ledger。",
        "调用 ds_strict_research_init_bibliography 创建 bibliography 三文件。",
        "逐篇精读；每读完一篇调用 ds_record_literature_reading_note 记录 read_status、sections_read、claim_routes，并立刻更新 bibliography 三文件，再进入下一篇。",
        "全部完成后再回答、写报告、写论文或执行用户要求的下一步。",
    ]
    return {
        "mode": "strict_research",
        "quest_id": quest_id,
        "reference_dir": str(reference_dir),
        "candidate_references_path": str(candidate_path),
        "reliability_cards_dir": str(cards_dir),
        "target_count": target_count,
        "selection_rules": STRICT_RESEARCH_RULES,
        "workflow": workflow,
        "verifier_skill": "deepscientist:paper-reliability-verifier",
        "verifier_resource_path": str(_plugin_root() / "resources" / "skills" / "paper-reliability-verifier"),
    }


@_guard
def ds_strict_research_record_candidate(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "title"):
        return {"ok": False, "error": err}
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required when no active quest exists"}
    reference_dir = _strict_reference_dir(services, quest_id)
    candidate_path = _ensure_candidate_file(reference_dir, quest_id)
    values = {
        "status": str(args.get("status") or "candidate").strip() or "candidate",
        "title": str(args.get("title") or "").strip(),
        "doi": str(args.get("doi") or "").strip(),
        "link": str(args.get("link") or "").strip(),
        "year": str(args.get("year") or "").strip(),
        "authors": str(args.get("authors") or "").strip(),
        "source": str(args.get("source") or "").strip(),
        "evidence_card": str(args.get("evidence_card") or "").strip(),
        "retain_reject_reason": str(args.get("retain_reject_reason") or args.get("reason") or "").strip(),
        "note": str(args.get("note") or "").strip(),
    }
    with candidate_path.open("a", encoding="utf-8") as f:
        f.write(_candidate_row(values))
    return {"quest_id": quest_id, "reference_dir": str(reference_dir), "candidate_references_path": str(candidate_path), "record": values}


@_guard
def ds_strict_research_upsert_candidate(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required when no active quest exists"}
    key_text = str(args.get("key") or "").strip()
    if not key_text and not any(str(args.get(field) or "").strip() for field in ("title", "doi", "link")):
        return {"ok": False, "error": "Provide key or at least one of title, doi, or link."}
    reference_dir = _strict_reference_dir(services, quest_id)
    candidate_path = _ensure_candidate_file(reference_dir, quest_id)
    lines = candidate_path.read_text(encoding="utf-8").splitlines(keepends=True)
    key_field = str(args.get("key_field") or "").strip() or None
    incoming = {
        "status": str(args.get("status") or "candidate").strip() or "candidate",
        "title": str(args.get("title") or key_text or "").strip(),
        "doi": str(args.get("doi") or "").strip(),
        "link": str(args.get("link") or "").strip(),
        "year": str(args.get("year") or "").strip(),
        "authors": str(args.get("authors") or "").strip(),
        "source": str(args.get("source") or "").strip(),
        "evidence_card": str(args.get("evidence_card") or args.get("reliability_card") or "").strip(),
        "retain_reject_reason": str(args.get("retain_reject_reason") or args.get("reason") or "").strip(),
        "note": str(args.get("note") or "").strip(),
    }
    target_keys = {norm_key(key_text)} if key_text else set()
    target_keys.update(_candidate_key_text(incoming, key_field))
    target_keys.discard("")
    action = "inserted"
    updated_record = incoming
    for idx, line in enumerate(lines):
        if not line.lstrip().startswith("|") or set(line.strip()) <= {"|", "-", " ", ":"}:
            continue
        record = _candidate_record_from_row(line)
        if not record or norm_key(record.get("title")) == "title":
            continue
        record_keys = set(_candidate_key_text(record, key_field))
        if target_keys and not (target_keys & record_keys):
            continue
        merged = dict(record)
        for field, value in incoming.items():
            if value:
                merged[field] = value
        # Preserve the original title when the caller used only `key` to update status.
        if not str(args.get("title") or "").strip() and record.get("title"):
            merged["title"] = record["title"]
        lines[idx] = _candidate_row(merged)
        updated_record = merged
        action = "updated"
        break
    if action == "inserted":
        lines.append(_candidate_row(incoming))
    candidate_path.write_text("".join(lines), encoding="utf-8")
    return {"quest_id": quest_id, "reference_dir": str(reference_dir), "candidate_references_path": str(candidate_path), "action": action, "record": updated_record}


@_guard
def ds_paper_fetch(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required when no active quest exists"}
    canonical_url, source_kind = _resolve_pdf_url(args)
    if not canonical_url:
        return {"ok": False, "error": "Could not resolve a PDF URL from title/url/arxiv_id/openreview_id/pmlr_url/pdf_url.", "official_resource_status": source_kind}
    reference_dir = _strict_reference_dir(services, quest_id)
    pdf_dir = reference_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    stem_source = args.get("output_name") or args.get("title") or args.get("arxiv_id") or args.get("openreview_id") or canonical_url
    stem = _safe_slug(stem_source, "paper")[:120]
    pdf_path = pdf_dir / f"{stem}.pdf"
    overwrite = _truthy(args.get("overwrite"))
    if pdf_path.exists() and not overwrite:
        data = pdf_path.read_bytes()
        status = "already_exists"
        retrieval_url = canonical_url
        download_attempts = [canonical_url]
    else:
        download_errors = []
        data = b""
        retrieval_url = ""
        download_attempts = _download_url_candidates(canonical_url, source_kind)
        for candidate_url in download_attempts:
            try:
                candidate_data = _download_url_to_bytes(candidate_url)
            except Exception as exc:
                download_errors.append({"url": candidate_url, "error": str(exc)})
                continue
            if not candidate_data.startswith(b"%PDF") and b"%PDF" not in candidate_data[:2048]:
                download_errors.append({"url": candidate_url, "error": f"resource does not look like a PDF; byte_count={len(candidate_data)}"})
                continue
            data = candidate_data
            retrieval_url = candidate_url
            break
        if not data:
            return {
                "ok": False,
                "error": "PDF download failed for all attempted URLs.",
                "canonical_url": canonical_url,
                "attempted_urls": download_attempts,
                "download_errors": download_errors,
                "official_resource_status": source_kind,
            }
        pdf_path.write_bytes(data)
        status = "downloaded"
    sha = hashlib.sha256(data).hexdigest()
    page_count = _pdf_page_count(data)
    ledger_path = reference_dir / "paper_fetch_ledger.jsonl"
    record = {
        "paper": str(args.get("title") or "").strip(),
        "canonical_url": canonical_url,
        "retrieval_url": retrieval_url,
        "attempted_urls": download_attempts,
        "pdf_path": str(pdf_path),
        "sha256": sha,
        "page_count": page_count,
        "body_text_status": "not_extracted",
        "official_resource_status": source_kind,
        "status": status,
        "fetched_at": _utc_now(),
    }
    _append_jsonl_path(ledger_path, record)
    return {"quest_id": quest_id, "reference_dir": str(reference_dir), "ledger_path": str(ledger_path), **record}


@_guard
def ds_record_literature_reading_note(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required when no active quest exists"}
    title = str(args.get("title") or args.get("paper_id") or "").strip()
    if not title:
        return {"ok": False, "error": "title or paper_id is required"}
    reference_dir = _strict_reference_dir(services, quest_id)
    notes_dir = reference_dir / "reading_notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    bibliography_dir = reference_dir / "bibliography"
    bibliography_dir.mkdir(parents=True, exist_ok=True)
    paper_id = _safe_slug(args.get("paper_id") or title, "paper")[:120]
    surfaces_read = _clean_string_list(args.get("surfaces_read"))
    sections_read = _clean_string_list(args.get("sections_read"))
    claim_routes = _clean_string_list(args.get("claim_routes"))
    status = str(args.get("status") or "read").strip() or "read"
    record = {
        "paper_id": paper_id,
        "title": title,
        "pdf_path": str(args.get("pdf_path") or "").strip(),
        "surfaces_read": surfaces_read,
        "sections_read": sections_read,
        "claim_routes": claim_routes,
        "status": status,
        "note": str(args.get("note") or "").strip(),
        "recorded_at": _utc_now(),
    }
    note_path = notes_dir / f"{paper_id}.md"
    note_body = [
        f"# {title}",
        "",
        f"- paper_id: `{paper_id}`",
        f"- status: {status}",
        f"- pdf_path: {record['pdf_path'] or 'not-recorded'}",
        f"- surfaces_read: {', '.join(surfaces_read) if surfaces_read else 'not-recorded'}",
        f"- sections_read: {', '.join(sections_read) if sections_read else 'not-recorded'}",
        f"- claim_routes: {', '.join(claim_routes) if claim_routes else 'not-recorded'}",
        "",
        "## Note",
        "",
        record["note"] or "(empty)",
        "",
    ]
    note_path.write_text("\n".join(note_body), encoding="utf-8")
    ledger_path = reference_dir / "literature_reading_ledger.jsonl"
    _append_jsonl_path(ledger_path, record)
    updates = args.get("bibliography_updates") if isinstance(args.get("bibliography_updates"), dict) else {}
    bib_files = {
        "essential_reference_details": bibliography_dir / "essential_reference_details.md",
        "reference_list": bibliography_dir / "reference_list.md",
        "priority_reference_materials": bibliography_dir / "priority_reference_materials.md",
    }
    default_headers = {
        "essential_reference_details": "# Essential Reference Details\n\n",
        "reference_list": "# Reference List\n\n",
        "priority_reference_materials": "# Priority Reference Materials\n\n",
    }
    bibliography_written: list[str] = []
    for key, path in bib_files.items():
        if not path.exists():
            path.write_text(default_headers[key], encoding="utf-8")
        text = str(updates.get(key) or updates.get(path.name) or "").strip()
        if text:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(f"\n## {title}\n\n{text}\n")
            bibliography_written.append(str(path))
    status_counts: dict[str, int] = {}
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except Exception:
                continue
            item_status = str(item.get("status") or "unknown")
            status_counts[item_status] = status_counts.get(item_status, 0) + 1
    completion = {"total_notes": sum(status_counts.values()), "status_counts": status_counts, "updated_at": _utc_now()}
    completion_path = reference_dir / "literature_reading_completion.json"
    _write_json_path(completion_path, completion)
    return {
        "quest_id": quest_id,
        "reference_dir": str(reference_dir),
        "bibliography_dir": str(bibliography_dir),
        "note_path": str(note_path),
        "ledger_path": str(ledger_path),
        "completion_path": str(completion_path),
        "completion": completion,
        "bibliography_written": bibliography_written,
        "record": record,
    }


@_guard
def ds_strict_research_init_bibliography(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required when no active quest exists"}
    reference_dir = _strict_reference_dir(services, quest_id)
    bibliography_dir = reference_dir / "bibliography"
    bibliography_dir.mkdir(parents=True, exist_ok=True)
    overwrite = _truthy(args.get("overwrite"))
    files = {
        "essential_reference_details.md": "# Essential Reference Details\n\n逐篇阅读保留论文后更新。每篇论文记录：标题、文件名、核心观点/发现现象、motivation、方法论、解决的问题、结论；每篇论文不超过300字。\n\n",
        "reference_list.md": "# Reference List\n\n记录写到什么内容时该引用哪篇论文：定义、背景、motivation、方法比较、实验结论、局限性、未来方向等。\n\n",
        "priority_reference_materials.md": "# Priority Reference Materials\n\n当需要写某篇论文中的发现、观点或结论时，优先查看哪些论文、章节、段落、图表或附录。逐篇阅读后持续更新。\n\n",
    }
    written: list[str] = []
    for name, content in files.items():
        path = bibliography_dir / name
        if overwrite or not path.exists():
            path.write_text(content, encoding="utf-8")
        written.append(str(path))
    return {"quest_id": quest_id, "reference_dir": str(reference_dir), "bibliography_dir": str(bibliography_dir), "files": written}


def _load_bundled_verifier(verifier_root: Path) -> Any:
    script = verifier_root / "scripts" / "verifier.py"
    if not script.exists():
        raise FileNotFoundError(f"Bundled verifier script not found: {script}")
    module_name = f"_deepscientist_bundled_paper_verifier_{abs(hash(script))}"
    spec = importlib.util.spec_from_file_location(module_name, script)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load bundled verifier from {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@_guard
def ds_paper_reliability_verify(args: dict[str, Any]) -> dict[str, Any]:
    services = get_services()
    quest_id = _active_or_latest_quest_id(args, services)
    if not quest_id:
        return {"ok": False, "error": "quest_id is required when no active quest exists"}
    if not str(args.get("doi") or args.get("title") or args.get("arxiv_url") or "").strip():
        return {"ok": False, "error": "Provide at least one of doi, title, or arxiv_url."}
    reference_dir = _strict_reference_dir(services, quest_id)
    cards_dir = reference_dir / "reliability_cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    verifier_root = _plugin_root() / "resources" / "skills" / "paper-reliability-verifier"
    stem = _safe_slug(args.get("output_name") or args.get("doi") or args.get("title") or args.get("arxiv_url"), "paper")[:120]
    out = cards_dir / f"{stem}.json"
    verifier = _load_bundled_verifier(verifier_root)
    card = verifier.build_card(
        doi=str(args.get("doi") or "").strip() or None,
        title=str(args.get("title") or "").strip() or None,
        year=int(args["year"]) if args.get("year") not in (None, "") else None,
        arxiv_url=str(args.get("arxiv_url") or "").strip() or None,
        include_raw=_truthy(args.get("include_raw")),
        accepted_venue=str(args.get("accepted_venue") or "").strip() or None,
        accepted_type=str(args.get("accepted_type") or "").strip() or None,
        accepted_acronym=str(args.get("accepted_acronym") or "").strip() or None,
    )
    out.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    response_mode = str(args.get("response_mode") or "full").strip().lower()
    summary = {
        "quest_id": quest_id,
        "reference_dir": str(reference_dir),
        "reliability_card_path": str(out),
        "paper": card.get("paper") if isinstance(card, dict) else {},
        "tier": card.get("tier") if isinstance(card, dict) else None,
        "quality_flags": card.get("quality_flags") if isinstance(card, dict) else [],
        "warnings": card.get("warnings") if isinstance(card, dict) else [],
        "verifier_resource_path": str(verifier_root),
    }
    if response_mode in {"summary", "compact"}:
        return summary
    return {**summary, "card": card}


@_guard
def ds_pause_quest(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id"):
        return {"ok": False, "error": err}
    services = get_services()
    return {"quest": compact_snapshot(services.quest.set_status(str(args["quest_id"]), "paused"))}


@_guard
def ds_resume_quest(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id"):
        return {"ok": False, "error": err}
    services = get_services()
    return {"quest": compact_snapshot(services.quest.set_status(str(args["quest_id"]), "active"))}


@_guard
def ds_stop_quest(args: dict[str, Any]) -> dict[str, Any]:
    if err := _require(args, "quest_id"):
        return {"ok": False, "error": err}
    services = get_services()
    snap = services.quest.set_status(str(args["quest_id"]), "stopped")
    return {"quest": compact_snapshot(snap), "reason": str(args.get("reason") or "stopped_by_hermes")}

# Compatibility aliases.
deepscientist_doctor = ds_doctor
deepscientist_list_quests = ds_list_quests
deepscientist_status = ds_get_quest_state
deepscientist_new_quest = ds_new_quest
deepscientist_send_message = ds_add_user_message
deepscientist_read_documents = ds_read_quest_documents
deepscientist_memory_search = ds_memory_search
deepscientist_memory_write = ds_memory_write
deepscientist_confirm_baseline = ds_confirm_baseline
deepscientist_submit_idea = ds_submit_idea
deepscientist_record_experiment = ds_record_main_experiment
deepscientist_submit_paper_bundle = ds_submit_paper_bundle
deepscientist_pause = ds_pause_quest
deepscientist_resume = ds_resume_quest
