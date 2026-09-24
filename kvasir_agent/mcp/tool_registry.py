"""Five public tools, all routed through validated project evidence operations."""
from __future__ import annotations
from dataclasses import dataclass
from jsonschema import Draft202012Validator
from .public_tools import DEFINITIONS, PUBLIC_NAMES, definition
from ..services.evidence import EvidenceService
from ..services.evidence_contracts import EvidenceError

@dataclass(frozen=True)
class ToolSpec:
    name: str
    @property
    def read_only(self):
        return self.name == "ka_research_status"
    def as_dict(self):
        return definition(self.name)

def list_tool_specs(profile=None, stage=None):
    return [ToolSpec(item["name"]) for item in DEFINITIONS]

def tools_list_payload(args=None):
    return {"tools": [spec.as_dict() for spec in list_tool_specs()]}

def public_mcp_tool_names(args=None):
    return set(PUBLIC_NAMES)

def is_tool_registered_for_mcp(name, args=None):
    return name in PUBLIC_NAMES

def mcp_tool_not_registered_payload(name):
    return {"ok": False, "error_type": "tool_not_registered", "error": "Unknown tool."}

def call_tool(name, args=None):
    if name not in PUBLIC_NAMES:
        return mcp_tool_not_registered_payload(name)
    args = {} if args is None else args
    error = next(Draft202012Validator(definition(name)["inputSchema"]).iter_errors(args), None)
    if error:
        return {"ok": False, "error_type": "invalid_arguments", "error": f"Invalid tool arguments ({error.validator})."}
    try:
        service = EvidenceService(args["project"])
        if name == "ka_research_status":
            return service.status(args.get("run_id"))
        if name == "ka_experiment_run":
            return service.run(args["spec_path"], args["idempotency_key"])
        if name == "ka_experiment_stop":
            return service.stop(args["run_id"])
        if name == "ka_evidence_check":
            return service.check(args["spec_path"])
        return service.import_evidence(args["manifest_path"])
    except EvidenceError as exc:
        return {"ok": False, "error_type": exc.kind, "error": str(exc)[:240]}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        return {"ok": False, "error_type": "state_error", "error": "State or evidence could not be read or written."}
