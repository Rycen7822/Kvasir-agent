"""Versioned file contracts; kept outside the model's tool definitions."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


class EvidenceError(ValueError):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1, "maxLength": 4096}
ID = {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,80}$"}
PATH = {"type": "string", "minLength": 1, "maxLength": 1024}
VERSION = {"const": 1}
FILE = obj({"path": PATH, "version": ID}, ["path"])
METRIC = obj({
    "name": ID, "direction": {"enum": ["maximize", "minimize"]},
    "parser": {"enum": ["json_path", "flat_key"]}, "path": TEXT,
    "validation": obj({"range": {"type": "array", "minItems": 2, "maxItems": 2,
                                 "items": {"type": ["number", "null"]}}}),
}, ["name", "direction", "parser", "path"])
ENVIRONMENT = obj({
    "schema_version": VERSION, "env_id": ID,
    "baseline": obj({"repo_path": PATH, "commit": {"type": "string", "pattern": "^[a-f0-9]{40,64}$"}}, ["repo_path"]),
    "protected_files": {"type": "array", "items": FILE, "minItems": 1, "maxItems": 200},
    "datasets": {"type": "array", "items": FILE, "minItems": 1, "maxItems": 200},
    "primary_metric": METRIC,
})
RUN = obj({
    "schema_version": VERSION, "purpose": {"enum": ["baseline", "experiment"]},
    "command": {"type": "array", "items": TEXT, "minItems": 1, "maxItems": 128},
    "cwd": PATH, "environment_path": PATH, "method_id": ID,
    "seed": {"type": "integer"}, "baseline_run_id": ID,
    "resources": obj({"timeout_seconds": {"type": "number", "exclusiveMinimum": 0, "maximum": 604800},
                      "max_log_bytes": {"type": "integer", "minimum": 1024, "maximum": 104857600}}),
    "metrics_path": PATH,
    "outputs": {"type": "array", "items": PATH, "minItems": 1, "maxItems": 100, "uniqueItems": True},
}, ["schema_version", "purpose", "command", "cwd", "environment_path", "method_id", "seed", "resources", "metrics_path", "outputs"])
RUN["allOf"] = [{"if": {"properties": {"purpose": {"const": "experiment"}}},
                  "then": {"required": ["baseline_run_id"]}}]
RUN_V2 = obj({**RUN["properties"], "schema_version": {"const": 2},
    "comparison": obj({"protocol_path": PATH, "pair_id": ID, "metric_unit": TEXT,
                       "metric_selection": {"enum": ["last", "best", "prespecified"]}}),
    "candidate_path": PATH, "progress_path": PATH, "cost_path": PATH,
    "result_origin": obj({"kind": {"enum": ["fresh", "cached", "replayed", "unknown"]},
                          "source_run_id": ID, "reason": TEXT}, ["kind"]),
}, RUN["required"])
RUN_V2["allOf"] = RUN["allOf"]
RUN_CONTRACT = {"oneOf": [RUN, RUN_V2]}
COMPARISON = obj({
    "schema_version": VERSION, "protocol_id": ID, "declared_at": TEXT,
    "timing": {"enum": ["prospective", "retrospective"]},
    "environment_id": ID, "version": ID, "dataset_id": ID, "split": TEXT,
    "datasets": {"type": "array", "items": FILE, "minItems": 1, "maxItems": 200},
    "evaluator": FILE,
    "metric": obj({"name": ID, "unit": TEXT, "direction": {"enum": ["maximize", "minimize"]},
                   "selection": {"enum": ["last", "best", "prespecified"]}}),
    "methods": obj({"baseline": ID, "candidate": ID}),
    "method_inputs": obj({"baseline": {"type": "array", "items": FILE, "minItems": 1, "maxItems": 200},
                          "candidate": {"type": "array", "items": FILE, "minItems": 1, "maxItems": 200}}),
    "budget": obj({"basis": {"const": "wall_timeout"},
                   "timeout_seconds": {"type": "number", "exclusiveMinimum": 0, "maximum": 604800}}),
    "pairs": {"type": "array", "minItems": 1, "maxItems": 1000,
              "items": obj({"pair_id": ID, "task_id": ID, "seed": {"type": "integer"}})},
    "failure_policy": {"const": "require_all_pairs"},
    "selection_rule": {"const": "unique_valid_attempt"},
    "statistics": {"const": "descriptive_only"},
})
COMPARISON["required"] = [key for key in COMPARISON["required"]
                          if key not in {"environment_id", "version"}]
CHECK = {"oneOf": [
    obj({"schema_version": VERSION, "target": {"const": "environment"}, "environment_path": PATH}),
    obj({"schema_version": VERSION, "target": {"const": "run"}, "run_id": ID}),
    obj({"schema_version": VERSION, "target": {"const": "claim"}, "claim": TEXT,
         "run_ids": {"type": "array", "items": ID, "minItems": 1, "maxItems": 100, "uniqueItems": True},
         "minimum_seeds": {"type": "integer", "minimum": 1, "maximum": 100}}),
    obj({"schema_version": {"const": 2}, "target": {"const": "import"}, "import_id": ID}),
    obj({"schema_version": {"const": 2}, "target": {"const": "comparison"}, "protocol_path": PATH}),
    obj({"schema_version": {"const": 2}, "target": {"const": "research"},
         "record_ids": {"type": "array", "items": ID, "minItems": 1, "maxItems": 100, "uniqueItems": True}}),
]}
IMPORT = obj({
    "schema_version": VERSION,
    "origin": obj({"type": {"enum": ["external_run", "published_result"]},
                   "source": TEXT, "run_id": TEXT}),
    "environment_path": PATH, "method_id": ID, "seed": {"type": "integer"},
    "metrics_path": PATH, "artifacts": {"type": "array", "items": FILE, "minItems": 1, "maxItems": 100},
})
REFERENCE = obj({"record_id": ID, "revision": ID})
REFERENCES = {"type": "array", "items": REFERENCE, "maxItems": 100, "uniqueItems": True}
FILES = {"type": "array", "items": FILE, "minItems": 1, "maxItems": 200}
LOCATOR = {"oneOf": [
    obj({"kind": {"const": "lines"}, "path": PATH,
         "start": {"type": "integer", "minimum": 1}, "end": {"type": "integer", "minimum": 1}, "excerpt": TEXT},
        ["kind", "path", "start", "end", "excerpt"]),
    obj({"kind": {"const": "page"}, "path": PATH,
         "page": {"type": "integer", "minimum": 1}, "excerpt": TEXT}, ["kind", "path", "page", "excerpt"]),
]}
RESEARCH_METADATA = {
    "source": obj({"source_id": TEXT, "version": TEXT, "url": TEXT, "retrieved_at": TEXT,
        "submitted_query": TEXT, "effective_query": TEXT,
        "coverage": obj({"mode": {"enum": ["fulltext", "abstract", "partial", "unavailable"]},
                         "truncated": {"type": "boolean"}, "pages_received": {"type": "integer", "minimum": 0},
                         "pages_total": {"type": ["integer", "null"], "minimum": 0}, "failure": TEXT}, ["mode", "truncated"]),
        "locators": {"type": "array", "items": LOCATOR, "maxItems": 100}, "limitations": TEXT,
    }, ["source_id", "version", "url", "retrieved_at", "coverage", "locators"]),
    "idea": obj({"hypothesis": TEXT, "alternatives": {"type": "array", "items": TEXT, "maxItems": 20},
                 "distinguishing_experiment": TEXT, "falsification": TEXT}),
    "candidate": obj({"method_id": ID, "files": FILES, "parents": REFERENCES, "rationale": TEXT}),
    "claim": obj({"statement": TEXT, "limitations": TEXT, "status": {"enum": ["proposal", "supported", "inconclusive", "contradicted"]}}),
    "review": obj({"target": FILE, "reviewer": TEXT, "outcome": {"enum": ["draft", "partial", "approved", "rejected"]},
                   "issues": {"type": "array", "items": TEXT, "maxItems": 100},
                   "unresolved": {"type": "array", "items": TEXT, "maxItems": 100}}),
    "negative_result": obj({"observation": TEXT, "scope": TEXT, "explanation": TEXT}),
}
RESEARCH = {"oneOf": [obj({
    "schema_version": VERSION, "record_id": ID, "kind": {"const": kind}, "title": TEXT,
    "content": FILE, "dependencies": REFERENCES,
    "run_ids": {"type": "array", "items": ID, "maxItems": 100, "uniqueItems": True},
    "metadata": metadata,
}, ["schema_version", "record_id", "kind", "title", "content", "dependencies", "metadata"])
    for kind, metadata in RESEARCH_METADATA.items()]}
PROGRESS = obj({
    "schema_version": VERSION, "run_id": ID, "updated_at": TEXT, "phase": TEXT,
    "step": {"type": "number", "minimum": 0}, "total": {"type": ["number", "null"], "minimum": 0},
    "heartbeat_at": TEXT, "last_progress_at": TEXT,
    "versions": obj({key: TEXT for key in ("requested", "published", "applied", "serving")}, []),
}, ["schema_version", "run_id", "updated_at", "phase"])
COST_ENTRY = obj({"resource": {"enum": ["wall_seconds", "cpu_seconds", "gpu_seconds", "tokens", "currency"]},
                  "unit": TEXT, "basis": {"enum": ["observed", "estimated", "unknown"]},
                  "value": {"type": ["number", "null"], "minimum": 0},
                  "scope": {"enum": ["run", "search", "selected_candidate"]}})
COST_ENTRY["allOf"] = [{"if": {"properties": {"basis": {"const": "unknown"}}},
                         "then": {"properties": {"value": {"type": "null"}}},
                         "else": {"properties": {"value": {"type": "number"}}}}]
COST = obj({"schema_version": VERSION, "run_id": ID,
            "entries": {"type": "array", "items": COST_ENTRY, "maxItems": 200}})
CONTRACTS = {"environment": ENVIRONMENT, "run": RUN_CONTRACT, "check": CHECK,
             "import": IMPORT, "comparison": COMPARISON, "research": RESEARCH,
             "progress": PROGRESS, "cost": COST}


def validate_document(data, kind: str):
    if kind in {"environment", "comparison", "import", "research"}:
        # Old checksum fields are read-only compatibility data, not part of the
        # current schemas, public identities or verification prerequisites.
        def without_legacy_hashes(value):
            if isinstance(value, list):
                return [without_legacy_hashes(item) for item in value]
            if not isinstance(value, dict):
                return value
            file_ref = set(value) <= {"path", "version", "sha256"}
            locator_ref = value.get("kind") in ("lines", "page")
            return {key: without_legacy_hashes(item) for key, item in value.items()
                    if not (key == "sha256" and "path" in value and (file_ref or locator_ref))}

        data = without_legacy_hashes(data)
        if kind == "comparison" and isinstance(data, dict):
            data.pop("environment_digest", None)
    errors = Draft202012Validator(CONTRACTS[kind]).iter_errors(data)
    error = next(errors, None)
    if error:
        # Never echo arbitrary user input or an entire oneOf schema in errors.
        where = "/".join(str(p) for p in error.absolute_path)[:160] or "/"
        raise EvidenceError("invalid_spec", f"Invalid {kind} field {where} ({error.validator}).")
    return data


def read_json(path: Path, *, limit: int = 2_000_000):
    if not path.is_file() or path.stat().st_size > limit:
        raise EvidenceError("invalid_file", "Missing or oversized JSON file.")
    try:
        def invalid_constant(value):
            raise ValueError(value)
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise EvidenceError("invalid_file", "Oversized JSON file.")
        return json.loads(raw.decode("utf-8"), parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise EvidenceError("invalid_json", "Invalid JSON document.") from exc
