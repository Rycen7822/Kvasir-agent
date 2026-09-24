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
SHA = {"type": "string", "pattern": "^[a-f0-9]{64}$"}
VERSION = {"const": 1}
HASHED = obj({"path": PATH, "sha256": SHA})
METRIC = obj({
    "name": ID, "direction": {"enum": ["maximize", "minimize"]},
    "parser": {"enum": ["json_path", "flat_key"]}, "path": TEXT,
    "validation": obj({"range": {"type": "array", "minItems": 2, "maxItems": 2,
                                 "items": {"type": ["number", "null"]}}}),
}, ["name", "direction", "parser", "path"])
ENVIRONMENT = obj({
    "schema_version": VERSION, "env_id": ID,
    "baseline": obj({"repo_path": PATH, "commit": {"type": "string", "pattern": "^[a-f0-9]{40,64}$"}}, ["repo_path"]),
    "protected_files": {"type": "array", "items": HASHED, "minItems": 1, "maxItems": 200},
    "datasets": {"type": "array", "items": HASHED, "minItems": 1, "maxItems": 200},
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
CHECK = {"oneOf": [
    obj({"schema_version": VERSION, "target": {"const": "environment"}, "environment_path": PATH}),
    obj({"schema_version": VERSION, "target": {"const": "run"}, "run_id": ID}),
    obj({"schema_version": VERSION, "target": {"const": "claim"}, "claim": TEXT,
         "run_ids": {"type": "array", "items": ID, "minItems": 1, "maxItems": 100, "uniqueItems": True},
         "minimum_seeds": {"type": "integer", "minimum": 1, "maximum": 100}}),
]}
IMPORT = obj({
    "schema_version": VERSION,
    "origin": obj({"type": {"enum": ["external_run", "published_result"]},
                   "source": TEXT, "run_id": TEXT}),
    "environment_path": PATH, "method_id": ID, "seed": {"type": "integer"},
    "metrics_path": PATH, "artifacts": {"type": "array", "items": HASHED, "minItems": 1, "maxItems": 100},
})
CONTRACTS = {"environment": ENVIRONMENT, "run": RUN, "check": CHECK, "import": IMPORT}


def validate_document(data, kind: str):
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
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise EvidenceError("invalid_json", "Invalid JSON document.") from exc
