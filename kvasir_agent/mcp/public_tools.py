"""Small public research API over the existing, guarded service operations."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from kvasir_agent.mcp.envelope import apply_budget_envelope
from kvasir_agent.services.manifest import ManifestService
from kvasir_agent.services.method_improvement import MethodImprovementService
from kvasir_agent.services.project_state import ProjectLayout


# Operation names are public API; targets remain internal service primitives.
OPERATIONS = {
    "ka_research_read": {
        "status": "ka_status", "resume": "ka_resume_brief",
        "delta": "ka_pack_delta", "review": "ka_review_status", "methods": None,
    },
    "ka_memory_query": {
        "search": "ka_memory_search", "read": "ka_memory_read", "recent": "ka_memory_list_recent",
    },
    "ka_baseline": {
        "create": "ka_create_local_baseline", "confirm": "ka_confirm_baseline",
        "record": "ka_manifest_record_baseline",
    },
    "ka_environment": {
        "register": "ka_environment_register", "validate": "ka_environment_validate",
        "show": "ka_environment_show", "validate_manifest": "ka_manifest_validate",
    },
    "ka_trajectory_query": {"search": "ka_trajectory_search", "show": "ka_trajectory_show"},
    "ka_method_record": {
        "idea": "ka_submit_idea", "negative": "ka_record_negative_result",
        "result": "ka_update_method_scoreboard",
    },
    "ka_analysis": {
        "create": "ka_create_analysis_campaign", "read": "ka_get_analysis_campaign",
        "record_slice": "ka_record_analysis_slice",
    },
    "ka_literature_setup": {
        "prepare": "ka_strict_research_prepare", "bibliography": "ka_strict_research_init_bibliography",
    },
    "ka_paper_record": {"outline": "ka_submit_paper_outline", "bundle": "ka_submit_paper_bundle"},
}

DESCRIPTIONS = {
    "ka_research_read": "Read bounded project status, resume anchors, event delta, review status, or persisted methods/frontier. Never refresh records.",
    "ka_memory_query": "Search, read, or list recent research memory cards. Writes use ka_memory_write.",
    "ka_baseline": "Create a baseline, confirm its evidence, or record manifest readiness. Recording readiness does not verify a baseline.",
    "ka_environment": "Register, validate, or inspect an experiment environment; validate_manifest checks the research manifest. Preserve protected hashes.",
    "ka_trajectory_query": "Search experiment trajectories or show one trajectory with bounded provenance paths.",
    "ka_method_record": "Record a candidate idea with novelty contract, a negative result, or a measured method outcome. Preserve failed-method memory.",
    "ka_analysis": "Create/read an evidence analysis campaign or record a slice. Writing-facing campaigns require selected-outline bindings.",
    "ka_literature_setup": "Prepare strict literature research or initialize bibliography after sufficient retained references exist.",
    "ka_paper_record": "Submit/select/revise an outline, or register a paper bundle with its evidence and artifact paths.",
}

STANDALONE = (
    "ka_record_user_requirement", "ka_checkpoint", "ka_memory_write",
    "ka_artifact_record", "ka_artifact_index", "ka_bash_exec", "ka_log_digest",
    "ka_trajectory_record", "ka_feedback_ingest", "ka_record_main_experiment",
    "ka_claim_gate", "ka_strict_research_upsert_candidate",
    "ka_record_literature_reading_note", "ka_paper_fetch", "ka_paper_reliability_verify",
)
PUBLIC_NAMES = frozenset((*OPERATIONS, *STANDALONE))


def canonical_schema(source: dict[str, Any]) -> dict[str, Any]:
    schema = deepcopy(source)
    properties = schema.setdefault("properties", {})
    properties.pop("quest_id", None)
    properties.pop("project_root", None)
    properties["project"] = {"type": "string", "description": "Absolute research project directory."}
    # Internal schemas use this alternative solely for project/project_root.
    schema.pop("anyOf", None)
    schema["required"] = list(dict.fromkeys(["project", *(
        key for key in schema.get("required", []) if key not in {"quest_id", "project_root"}
    )]))
    schema["additionalProperties"] = False
    return schema


@lru_cache(maxsize=None)
def operation_schema(name: str, operation: str | None = None) -> dict[str, Any]:
    from kvasir_agent.mcp import tool_registry as registry

    target = OPERATIONS[name][operation] if name in OPERATIONS else name
    if target is None:
        source = {"type": "object", "properties": {
            "max_items": {"type": "integer", "minimum": 1, "maximum": 100},
        }}
    else:
        source = registry._tool_schema({"name": target})["schema"]["input_schema"]
    return canonical_schema(source)


@lru_cache(maxsize=None)
def definition(name: str) -> dict[str, Any]:
    from kvasir_agent.mcp import tool_registry as registry

    if name not in OPERATIONS:
        spec = registry._SPECS_BY_NAME[name]
        return {
            "name": name, "description": spec.description,
            "inputSchema": operation_schema(name),
            "annotations": {
                "readOnlyHint": spec.read_only, "destructiveHint": spec.destructive,
                "idempotentHint": spec.idempotent, "openWorldHint": spec.open_world,
            },
        }
    properties: dict[str, Any] = {}
    branches = []
    schemas = {op: operation_schema(name, op) for op in OPERATIONS[name]}
    for schema in schemas.values():
        for key, value in schema["properties"].items():
            choices = properties.setdefault(key, [])
            if value not in choices:
                choices.append(value)
    for op, schema in schemas.items():
        branch = {"properties": {"operation": {"const": op}}, "required": schema["required"]}
        for key in properties.keys() - schema["properties"].keys():
            branch["properties"][key] = False
        for key, value in schema["properties"].items():
            if len(properties[key]) > 1:
                branch["properties"][key] = value
        branches.append(branch)
    combined = {key: values[0] if len(values) == 1 else {"anyOf": values}
                for key, values in properties.items()}
    combined["operation"] = {"type": "string", "enum": list(OPERATIONS[name])}
    specs = [registry._SPECS_BY_NAME[target] for target in OPERATIONS[name].values() if target]
    return {
        "name": name, "description": DESCRIPTIONS[name],
        "inputSchema": {
            "type": "object", "properties": combined, "required": ["project", "operation"],
            "oneOf": branches, "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": all(spec.read_only for spec in specs),
            "destructiveHint": any(spec.destructive for spec in specs),
            "idempotentHint": all(spec.idempotent for spec in specs),
            "openWorldHint": any(spec.open_world for spec in specs),
        },
    }


def _failure(name: str, kind: str, message: str, **details: Any) -> dict[str, Any]:
    return apply_budget_envelope({"ok": False, "error_type": kind, "error": message,
                                  "recoverable": True, **details}, tool_name=name)


def call_public_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    from kvasir_agent.mcp import tool_registry as registry

    if name not in PUBLIC_NAMES:
        return registry.mcp_tool_not_registered_payload(name)
    project = args.get("project")
    if not isinstance(project, str) or not project.strip() or not Path(project.strip()).expanduser().is_absolute():
        return _failure(name, "missing_project_root", "Pass the absolute research project path as project.")
    operation = args.get("operation") if name in OPERATIONS else None
    if name in OPERATIONS and (not isinstance(operation, str) or operation not in OPERATIONS[name]):
        return _failure(name, "invalid_operation", "Choose an advertised operation.", operations=list(OPERATIONS[name]))
    call_args = dict(args)
    if name in OPERATIONS:
        call_args.pop("operation")
    schema = operation_schema(name, operation)
    error = next(Draft202012Validator(schema).iter_errors(call_args), None)
    if error is not None:
        # Avoid reflecting arbitrary user content (including secrets) in errors.
        return _failure(name, "invalid_argument", "Arguments do not match this operation's schema.",
                        argument_path=".".join(map(str, error.absolute_path)),
                        constraint=error.validator, required_arguments=schema.get("required", []))
    call_args["project"] = str(Path(project.strip()).expanduser().resolve())
    target = OPERATIONS[name][operation] if name in OPERATIONS else name
    layout = ProjectLayout.from_project_root(Path(call_args["project"]))
    try:
        if target is None:
            result = MethodImprovementService(layout).read_summary(limit=call_args.get("max_items", 20))
        else:
            identity = ManifestService(layout).quest_identity(create=False)
            if identity.get("ok"):
                call_args["quest_id"] = identity["quest_id"]
            result = registry.call_tool(target, call_args)
        # The service layer may suggest internal primitive names. Translate its
        # actionable hints to the public API without rewriting research content.
        for key in ("suggested_next_action", "next_action"):
            if isinstance(result.get(key), str):
                result[key] = public_hint(result[key])
        for key in ("next_call", "retry_template"):
            hint = result.get(key)
            if isinstance(hint, dict):
                result[key] = public_call_hint(hint)
        result["tool"] = name
        if operation is not None:
            result["operation"] = operation
        return apply_budget_envelope(result, tool_name=name)
    except (ValueError, OSError) as exc:
        return _failure(name, "invalid_argument", str(exc))
    except Exception as exc:
        return _failure(name, "internal_error", str(exc))


def public_hint(text: str) -> str:
    for name, operations in OPERATIONS.items():
        for op, target in operations.items():
            if target:
                text = text.replace(target, f"{name}(operation={op})")
    return text


def public_call_hint(hint: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(hint)
    name_key = "name" if "name" in result else "tool"
    target = result.get(name_key)
    for name, operations in OPERATIONS.items():
        for op, internal in operations.items():
            if target == internal and internal:
                result[name_key] = name
                result["operation"] = op
                if isinstance(result.get("arguments"), dict):
                    result["arguments"]["operation"] = op
    for key in ("required_arguments", "missing_arguments"):
        if isinstance(result.get(key), list):
            result[key] = [k for k in result[key] if k not in {"quest_id", "project_root"}]
    for key in ("arguments", "known_arguments"):
        if isinstance(result.get(key), dict):
            result[key].pop("quest_id", None)
            result[key].pop("project_root", None)
    return result
