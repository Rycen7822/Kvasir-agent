from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .event_store import EventStore
from .metric import extract_metric_value
from .project_state import ProjectLayout, _safe_segment

_SCHEMA_VERSION = 1
_REQUIRED_FIELDS = (
    "schema_version",
    "env_id",
    "quest_id",
    "title",
    "problem",
    "baseline",
    "mutable_allowlist",
    "protected_files",
    "datasets",
    "commands",
    "primary_metric",
    "resources",
    "budget",
    "security",
)
_REQUIRED_COMMANDS = ("setup", "smoke", "run", "evaluate")


def _error(error_type: str, message: str, *, recoverable: bool = True, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "error_type": error_type, "error": message, "recoverable": recoverable}
    payload.update(extra)
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("environment manifest must be a JSON object")
    return loaded


class EnvironmentService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)

    def register(self, *, quest_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
        schema = self._check_schema(quest_id=quest_id, manifest=manifest)
        if schema["ok"] is False:
            return schema
        safe_env_id = _safe_segment(str(manifest["env_id"]), label="env_id")
        quest = self.layout.ensure_quest_layout(quest_id)
        path = quest.detail_path(Path("environments") / f"{safe_env_id}.json")
        record = dict(manifest)
        record["schema_version"] = _SCHEMA_VERSION
        record["quest_id"] = _safe_segment(quest_id, label="quest_id")
        record["env_id"] = safe_env_id
        self.events.write_snapshot(record, path=path)
        self.events.append(
            "environment.registered",
            {"quest_id": record["quest_id"], "env_id": safe_env_id, "path": str(path)},
            idempotency_key=f"environment.registered:{record['quest_id']}:{safe_env_id}",
        )
        return {"ok": True, "quest_id": record["quest_id"], "env_id": safe_env_id, "path": str(path)}

    def show(self, *, quest_id: str, env_id: str) -> dict[str, Any]:
        loaded = self._read_environment(quest_id=quest_id, env_id=env_id)
        if loaded["ok"] is False:
            return loaded
        return {"ok": True, "environment": loaded["environment"]}

    def validate(self, *, quest_id: str, env_id: str) -> dict[str, Any]:
        loaded = self._read_environment(quest_id=quest_id, env_id=env_id)
        if loaded["ok"] is False:
            return loaded
        manifest = loaded["environment"]
        schema = self._check_schema(quest_id=quest_id, manifest=manifest)
        if schema["ok"] is False:
            return self._validation_failed(quest_id=quest_id, env_id=env_id, result=schema)

        path_result = self._validate_paths_and_hashes(manifest)
        if path_result["ok"] is False:
            return self._validation_failed(quest_id=quest_id, env_id=env_id, result=path_result)

        command_result = self._validate_commands(manifest)
        if command_result["ok"] is False:
            return self._validation_failed(quest_id=quest_id, env_id=env_id, result=command_result)

        metric_result = extract_metric_value(manifest.get("sample_metrics") or {}, manifest["primary_metric"])
        if metric_result["ok"] is False:
            result = _error("metric_parser_invalid", metric_result.get("error", "Primary metric parser failed"), recoverable=True, parser_error_type=metric_result.get("error_type"))
            return self._validation_failed(quest_id=quest_id, env_id=env_id, result=result)

        return {
            "ok": True,
            "status": "valid",
            "quest_id": quest_id,
            "env_id": env_id,
            "primary_metric": {
                "name": manifest["primary_metric"].get("name"),
                "value": metric_result["value"],
                "direction": manifest["primary_metric"].get("direction"),
            },
            "protected_hashes": path_result["protected_hashes"],
            "dataset_hashes": path_result["dataset_hashes"],
        }

    def protected_hash_report(self, *, quest_id: str, env_id: str) -> dict[str, Any]:
        loaded = self._read_environment(quest_id=quest_id, env_id=env_id)
        if loaded["ok"] is False:
            return loaded
        result = self._validate_paths_and_hashes(loaded["environment"], check_existence=True)
        if result["ok"] is False:
            return result
        return {"ok": True, "protected_hashes": result["protected_hashes"], "dataset_hashes": result["dataset_hashes"]}

    def _environment_path(self, *, quest_id: str, env_id: str) -> Path:
        safe_env_id = _safe_segment(env_id, label="env_id")
        return self.layout.quest_detail_path(quest_id, Path("environments") / f"{safe_env_id}.json")

    def _read_environment(self, *, quest_id: str, env_id: str) -> dict[str, Any]:
        try:
            path = self._environment_path(quest_id=quest_id, env_id=env_id)
        except ValueError as exc:
            return _error("invalid_path", str(exc), recoverable=False)
        if not path.exists():
            return _error("environment_not_found", f"Environment not found: {env_id}", recoverable=True)
        try:
            return {"ok": True, "environment": _load_json(path), "path": str(path)}
        except (json.JSONDecodeError, ValueError) as exc:
            return _error("invalid_schema", str(exc), recoverable=True)

    def _check_schema(self, *, quest_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(manifest, dict):
            return _error("invalid_schema", "Environment manifest must be an object", recoverable=True)
        missing = [field for field in _REQUIRED_FIELDS if field not in manifest]
        if missing:
            return _error("invalid_schema", "Missing environment fields", recoverable=True, missing_fields=missing)
        if manifest.get("schema_version") != _SCHEMA_VERSION:
            return _error("invalid_schema", "Unsupported environment schema_version", recoverable=True)
        try:
            _safe_segment(str(manifest["env_id"]), label="env_id")
            safe_quest_id = _safe_segment(quest_id, label="quest_id")
        except ValueError as exc:
            return _error("invalid_schema", str(exc), recoverable=True)
        if str(manifest.get("quest_id")) != safe_quest_id:
            return _error("invalid_schema", "Environment quest_id must match request quest_id", recoverable=True)
        if not isinstance(manifest.get("baseline"), dict):
            return _error("invalid_schema", "baseline must be an object", recoverable=True)
        if not isinstance(manifest.get("mutable_allowlist"), list):
            return _error("invalid_schema", "mutable_allowlist must be a list", recoverable=True)
        if not isinstance(manifest.get("protected_files"), list) or not isinstance(manifest.get("datasets"), list):
            return _error("invalid_schema", "protected_files and datasets must be lists", recoverable=True)
        if not isinstance(manifest.get("commands"), dict):
            return _error("invalid_schema", "commands must be an object", recoverable=True)
        if not isinstance(manifest.get("primary_metric"), dict):
            return _error("invalid_schema", "primary_metric must be an object", recoverable=True)
        if manifest["primary_metric"].get("direction") not in {"maximize", "minimize"}:
            return _error("invalid_schema", "primary_metric.direction must be maximize or minimize", recoverable=True)
        if not isinstance(manifest.get("resources"), dict) or not isinstance(manifest.get("budget"), dict):
            return _error("invalid_schema", "resources and budget must be objects", recoverable=True)
        return {"ok": True}

    def _project_relative_path(self, raw_path: str, *, label: str) -> Path | dict[str, Any]:
        rel = Path(str(raw_path or ""))
        if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
            return _error("invalid_path", f"{label} must be a safe project-relative path: {raw_path!r}", recoverable=False)
        target = (self.layout.project_root / rel).resolve()
        root = self.layout.project_root.resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return _error("invalid_path", f"{label} escapes project root: {raw_path!r}", recoverable=False)
        return target

    def _validate_paths_and_hashes(self, manifest: dict[str, Any], *, check_existence: bool = True) -> dict[str, Any]:
        baseline_path = self._project_relative_path(str(manifest.get("baseline", {}).get("repo_path") or "."), label="baseline.repo_path")
        if isinstance(baseline_path, dict):
            return baseline_path
        if check_existence and not baseline_path.exists():
            return _error("invalid_path", f"baseline.repo_path does not exist: {manifest['baseline'].get('repo_path')}", recoverable=True)

        for mutable in manifest.get("mutable_allowlist") or []:
            mutable_path = self._project_relative_path(str(mutable), label="mutable_allowlist")
            if isinstance(mutable_path, dict):
                return mutable_path

        protected_hashes: list[dict[str, Any]] = []
        for item in manifest.get("protected_files") or []:
            result = self._check_hashed_path(item, label="protected_files")
            if result["ok"] is False:
                return result
            protected_hashes.append(result["hash"])

        dataset_hashes: list[dict[str, Any]] = []
        for item in manifest.get("datasets") or []:
            result = self._check_hashed_path(item, label="datasets")
            if result["ok"] is False:
                return result
            dataset_hashes.append(result["hash"])

        return {"ok": True, "protected_hashes": protected_hashes, "dataset_hashes": dataset_hashes}

    def _check_hashed_path(self, item: Any, *, label: str) -> dict[str, Any]:
        if not isinstance(item, dict):
            return _error("invalid_schema", f"{label} entries must be objects", recoverable=True)
        raw_path = str(item.get("path") or "")
        expected = str(item.get("sha256") or "").strip()
        if not expected:
            return _error("protected_hash_missing", f"Missing sha256 for {label}: {raw_path}", recoverable=True)
        target = self._project_relative_path(raw_path, label=f"{label}.path")
        if isinstance(target, dict):
            return target
        if not target.exists() or not target.is_file():
            return _error("invalid_path", f"{label} path does not exist: {raw_path}", recoverable=True)
        actual = _sha256(target)
        if actual != expected:
            return _error("protected_hash_mismatch", f"Hash mismatch for {raw_path}", recoverable=False, path=raw_path, expected_sha256=expected, actual_sha256=actual)
        return {"ok": True, "hash": {"path": raw_path, "sha256": actual}}

    def _validate_commands(self, manifest: dict[str, Any]) -> dict[str, Any]:
        commands = manifest.get("commands") or {}
        for name in _REQUIRED_COMMANDS:
            value = commands.get(name)
            if not isinstance(value, list) or not all(isinstance(command, list) and command for command in value):
                return _error("invalid_schema", f"commands.{name} must be a non-empty list of argv lists", recoverable=True)
        return {"ok": True}

    def _validation_failed(self, *, quest_id: str, env_id: str, result: dict[str, Any]) -> dict[str, Any]:
        payload = dict(result)
        payload.setdefault("ok", False)
        payload.setdefault("recoverable", True)
        payload["status"] = payload.get("error_type", "invalid")
        self.events.append("environment.validation_failed", {"quest_id": quest_id, "env_id": env_id, "error_type": payload.get("error_type")})
        return payload
