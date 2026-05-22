from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from codex_scientist.runtime.redaction import redact_payload, redact_text

from .environment import EnvironmentService
from .project_state import ProjectLayout, _safe_segment

_PROTECTED_PLACEHOLDER = "[PROTECTED_FILE_CONTENT_REDACTED]"
_DATASET_PLACEHOLDER = "[DATASET_CONTENT_EXCLUDED]"
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_INVALID_SHA256 = "[INVALID_SHA256_REDACTED]"
_INVALID_PROTECTED_PATH = "[INVALID_PROTECTED_PATH]"
_INVALID_DATASET_PATH = "[INVALID_DATASET_PATH]"
_INVALID_CONTEXT_PATH = "[INVALID_CONTEXT_PATH]"
_INVALID_REPORT_PATH = "[INVALID_PATH_REDACTED]"


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


def _line_numbered(text: str) -> str:
    return "\n".join(f"{line_no}|{line}" for line_no, line in enumerate(text.splitlines(), start=1))


class ImplementerContextBuilder:
    """Build bounded, environment-aware contexts for patch implementers.

    The builder is intentionally read-only: it only loads the registered environment
    manifest and files explicitly allowed by that manifest. Protected files and
    datasets are represented by metadata only.
    """

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.environments = EnvironmentService(layout)

    def build(self, *, quest_id: str, env_id: str, idea_id: str, token_budget: int = 3000) -> dict[str, Any]:
        shown = self.environments.show(quest_id=quest_id, env_id=env_id)
        if shown.get("ok") is not True:
            return shown
        environment = shown.get("environment")
        if not isinstance(environment, dict):
            return _error("invalid_schema", "Environment record must be an object", recoverable=True)

        try:
            safe_quest_id = _safe_segment(quest_id, label="quest_id")
            safe_env_id = _safe_segment(env_id, label="env_id")
        except ValueError as exc:
            return _error("invalid_path", str(exc), recoverable=False)

        raw_baseline = environment.get("baseline")
        baseline = raw_baseline if isinstance(raw_baseline, dict) else {}
        repo_rel = str(baseline.get("repo_path") or ".")
        repo_root_result = self._project_path(repo_rel, label="baseline.repo_path")
        if isinstance(repo_root_result, dict):
            return repo_root_result
        repo_root = repo_root_result

        protected_project_paths = self._metadata_path_set(environment.get("protected_files") or [])
        dataset_project_paths = self._metadata_path_set(environment.get("datasets") or [])
        candidate_roles = self._candidate_paths(environment)

        char_budget = max(0, int(token_budget or 0)) * 4
        used_chars = 0
        included_files: list[dict[str, Any]] = []
        omitted_files: list[dict[str, Any]] = []
        for project_path, role in candidate_roles:
            target_result = self._project_path(project_path, label="context_file")
            if isinstance(target_result, dict):
                omitted_files.append({"project_path": _INVALID_CONTEXT_PATH, "reason": target_result.get("error_type", "invalid_path")})
                continue
            target = target_result
            if target in protected_project_paths:
                omitted_files.append({"project_path": project_path, "reason": "protected_file_excluded"})
                continue
            if target in dataset_project_paths:
                omitted_files.append({"project_path": project_path, "reason": "dataset_content_excluded"})
                continue
            if not target.exists() or not target.is_file():
                omitted_files.append({"project_path": project_path, "reason": "missing_file"})
                continue
            if used_chars >= char_budget:
                omitted_files.append({"project_path": project_path, "reason": "token_budget_exceeded"})
                continue

            raw_bytes = target.read_bytes()
            text = redact_text(raw_bytes.decode("utf-8", errors="replace"))
            numbered = _line_numbered(text)
            remaining = max(0, char_budget - used_chars)
            content = numbered[:remaining]
            reason: str | None = None
            if len(numbered) > remaining:
                reason = "content_truncated" if remaining else "token_budget_exceeded"
            used_chars += len(content)
            included_files.append(
                {
                    "path": self._repo_relative(target=target, repo_root=repo_root),
                    "project_path": self._project_relative(target),
                    "role": role,
                    "sha256": _sha256(target),
                    "byte_count": len(raw_bytes),
                    "content": content,
                }
            )
            if reason:
                omitted_files.append({"project_path": self._project_relative(target), "reason": reason})

        payload = {
            "ok": True,
            "quest_id": safe_quest_id,
            "env_id": safe_env_id,
            "idea_id": str(idea_id or ""),
            "environment": self._environment_summary(environment),
            "included_files": included_files,
            "protected_files": self._protected_metadata(environment=environment, repo_root=repo_root),
            "datasets": self._dataset_metadata(environment=environment, repo_root=repo_root),
            "omitted_files": omitted_files,
            "budget": {"token_budget": int(token_budget or 0), "char_budget": char_budget, "used_chars": used_chars},
        }
        return redact_payload(payload)

    def build_repair(
        self,
        *,
        quest_id: str,
        env_id: str,
        variant_id: str,
        token_budget: int = 3000,
        previous_failure: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            safe_variant_id = _safe_segment(variant_id, label="variant_id")
        except ValueError as exc:
            return _error("invalid_path", str(exc), recoverable=False)
        variant_result = self._load_variant(quest_id=quest_id, variant_id=safe_variant_id)
        if variant_result.get("ok") is not True:
            return variant_result
        variant = variant_result["variant"]
        variant_env_id = str(variant.get("env_id") or "").strip()
        if variant_env_id != str(env_id):
            return _error(
                "repair_context_env_mismatch",
                "Repair context env_id must match the variant record env_id",
                recoverable=False,
                variant_id=safe_variant_id,
                expected_env_id=variant_env_id,
                actual_env_id=str(env_id),
            )
        payload = self.build(quest_id=quest_id, env_id=env_id, idea_id=str(variant.get("idea_id") or (previous_failure or {}).get("idea_id") or safe_variant_id), token_budget=token_budget)
        if payload.get("ok") is not True:
            return payload
        checks = self._load_checks(quest_id=quest_id, variant_id=safe_variant_id)
        redacted_previous = redact_payload(previous_failure or {})
        smoke_digest = self._smoke_digest(checks)
        taxonomy = str((previous_failure or {}).get("failure_class") or checks.get("failure_class") or (previous_failure or {}).get("error_type") or checks.get("error_type") or "unknown")
        git_apply_check_stderr = str((previous_failure or {}).get("git_apply_check_stderr") or (previous_failure or {}).get("stderr_tail") or (previous_failure or {}).get("stderr") or "")
        payload["repair"] = {
            "variant_id": safe_variant_id,
            "previous_patch_failure": redacted_previous,
            "git_apply_check_stderr_label": "git apply --check stderr",
            "git_apply_check_stderr": redact_text(git_apply_check_stderr),
            "smoke_failure_digest": smoke_digest,
            "failure_taxonomy": taxonomy,
            "protected_hash_report": self._sanitize_hash_report(self.environments.protected_hash_report(quest_id=quest_id, env_id=env_id)),
        }
        return redact_payload(payload)

    def _project_path(self, raw_path: str, *, label: str) -> Path | dict[str, Any]:
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

    def _metadata_path_set(self, items: Any) -> set[Path]:
        paths: set[Path] = set()
        if not isinstance(items, list):
            return paths
        for item in items:
            if not isinstance(item, dict):
                continue
            target = self._project_path(str(item.get("path") or ""), label="metadata.path")
            if isinstance(target, Path):
                paths.add(target)
        return paths

    def _candidate_paths(self, environment: dict[str, Any]) -> list[tuple[str, str]]:
        roles: dict[str, str] = {}
        sources = (
            (environment.get("context_files") or [], "context"),
            (environment.get("mutable_allowlist") or [], "mutable"),
        )
        for source, role in sources:
            if not isinstance(source, list):
                continue
            for raw in source:
                if not isinstance(raw, str):
                    continue
                expanded = self._expand_project_pattern(raw)
                for project_path in expanded:
                    roles[project_path] = role
        return sorted(roles.items(), key=lambda item: Path(item[0]).as_posix())

    def _expand_project_pattern(self, raw_path: str) -> list[str]:
        if not any(ch in raw_path for ch in "*?["):
            return [raw_path]
        base = self.layout.project_root
        if Path(raw_path).is_absolute() or any(part in {"", ".", ".."} for part in Path(raw_path).parts):
            return [raw_path]
        return sorted(path.relative_to(base).as_posix() for path in base.glob(raw_path) if path.is_file())

    def _project_relative(self, target: Path) -> str:
        return target.resolve().relative_to(self.layout.project_root.resolve()).as_posix()

    def _repo_relative(self, *, target: Path, repo_root: Path) -> str:
        try:
            return target.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            return self._project_relative(target)

    def _protected_metadata(self, *, environment: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in environment.get("protected_files") or []:
            if not isinstance(item, dict):
                continue
            raw_path_value = item.get("path")
            target, raw_path = self._safe_metadata_path(raw_path_value, placeholder=_INVALID_PROTECTED_PATH)
            display = raw_path
            if target is not None:
                display = self._repo_relative(target=target, repo_root=repo_root)
            records.append(
                {
                    "path": display,
                    "project_path": raw_path,
                    "role": self._safe_metadata_string(item.get("role"), default="protected"),
                    "sha256": self._safe_sha256(item.get("sha256")),
                    "content": _PROTECTED_PLACEHOLDER,
                }
            )
        return records

    def _dataset_metadata(self, *, environment: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in environment.get("datasets") or []:
            if not isinstance(item, dict):
                continue
            raw_path_value = item.get("path")
            target, raw_path = self._safe_metadata_path(raw_path_value, placeholder=_INVALID_DATASET_PATH)
            display = raw_path
            if target is not None:
                display = self._repo_relative(target=target, repo_root=repo_root)
            record = self._safe_dataset_metadata(item)
            record.update({"path": display, "project_path": raw_path, "content": _DATASET_PLACEHOLDER})
            records.append(record)
        return records

    def _safe_metadata_path(self, value: Any, *, placeholder: str) -> tuple[Path | None, str]:
        if not isinstance(value, str):
            return None, placeholder
        target = self._project_path(value, label="metadata.path")
        if isinstance(target, dict):
            return None, placeholder
        return target, self._project_relative(target)

    def _safe_sha256(self, value: Any) -> str:
        if isinstance(value, str) and _SHA256_RE.fullmatch(value.strip()):
            return value.strip().lower()
        return _INVALID_SHA256

    def _safe_metadata_string(self, value: Any, *, default: str) -> str:
        if not isinstance(value, str):
            return default
        text = redact_text(value.strip())
        if not text or len(text) > 80:
            return default
        return text

    def _safe_dataset_metadata(self, item: dict[str, Any]) -> dict[str, Any]:
        record: dict[str, Any] = {}
        sha = item.get("sha256")
        if isinstance(sha, str) and _SHA256_RE.fullmatch(sha.strip()):
            record["sha256"] = sha.strip().lower()
        split = item.get("split")
        if isinstance(split, str) and len(split) <= 80:
            record["split"] = redact_text(split)
        rows = item.get("rows")
        if type(rows) is int and rows >= 0:
            record["rows"] = rows
        return record

    def _environment_summary(self, environment: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": environment.get("title"),
            "problem": environment.get("problem"),
            "baseline": environment.get("baseline"),
            "primary_metric": environment.get("primary_metric"),
            "resources": environment.get("resources"),
            "budget": environment.get("budget"),
            "security": environment.get("security"),
        }

    def _sanitize_hash_report(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._sanitize_hash_report(item) for item in value]
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                key_text = str(key)
                if key_text.endswith("sha256"):
                    sanitized[key_text] = self._safe_sha256(item)
                elif key_text == "path":
                    _target, path_value = self._safe_metadata_path(item, placeholder=_INVALID_REPORT_PATH)
                    sanitized[key_text] = path_value
                elif key_text in {"error", "message"}:
                    sanitized[key_text] = "[SANITIZED_HASH_REPORT_ERROR]"
                else:
                    sanitized[key_text] = self._sanitize_hash_report(item)
            return sanitized
        if isinstance(value, str):
            return redact_text(value)
        return value

    def _load_checks(self, *, quest_id: str, variant_id: str) -> dict[str, Any]:
        path = self.layout.state_root / "variants" / variant_id / "checks.json"
        if not path.exists():
            return {}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _load_variant(self, *, quest_id: str, variant_id: str) -> dict[str, Any]:
        try:
            path = self.layout.state_root / "variants" / variant_id / "variant.json"
        except ValueError as exc:
            return _error("invalid_path", str(exc), recoverable=False)
        if not path.exists():
            return _error("variant_not_found", f"Variant not found: {variant_id}", recoverable=True, variant_id=variant_id)
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return _error("invalid_schema", str(exc), recoverable=True, variant_id=variant_id)
        if not isinstance(loaded, dict):
            return _error("invalid_schema", "Variant record must be an object", recoverable=True, variant_id=variant_id)
        return {"ok": True, "variant": loaded, "path": str(path)}

    def _smoke_digest(self, checks: dict[str, Any]) -> dict[str, Any]:
        digest: dict[str, Any] = {}
        for key in ("smoke_status", "failure_class", "error_type", "stdout_tail", "stderr_tail", "exit_code"):
            if key in checks:
                digest[key] = checks[key]
        commands = checks.get("commands")
        if isinstance(commands, list) and commands:
            latest = commands[-1]
            if isinstance(latest, dict):
                for key in ("stdout_tail", "stderr_tail", "exit_code"):
                    if key in latest and key not in digest:
                        digest[key] = latest[key]
        return redact_payload(digest)
