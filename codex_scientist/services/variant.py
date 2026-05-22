from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import stat
import subprocess
import tarfile
from fnmatch import fnmatch
from pathlib import Path
from typing import Any
from uuid import uuid4

from .environment import EnvironmentService
from .event_store import EventStore, utc_now
from .project_state import ProjectLayout, _safe_segment
from .readonly_guard import check_readonly_changes
from .trajectory import TrajectoryStore


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


def _tree_snapshot_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file() and ".git" not in item.parts):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _json_load(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("variant record must be a JSON object")
    return loaded


def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _is_full_commit_hash(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdefABCDEF" for char in value)


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


class VariantService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)

    def create(
        self,
        *,
        quest_id: str,
        env_id: str,
        trajectory_id: str,
        idea_id: str,
        strategy: str = "worktree",
    ) -> dict[str, Any]:
        if strategy != "worktree":
            return _error("invalid_strategy", f"Unsupported variant strategy: {strategy}", recoverable=True)
        try:
            safe_quest_id = _safe_segment(quest_id, label="quest_id")
            safe_env_id = _safe_segment(env_id, label="env_id")
            safe_trajectory_id = _safe_segment(trajectory_id, label="trajectory_id")
            safe_idea_id = _safe_segment(idea_id, label="idea_id")
        except ValueError as exc:
            return _error("invalid_path", str(exc), recoverable=False)

        env_service = EnvironmentService(self.layout)
        validation = env_service.validate(quest_id=safe_quest_id, env_id=safe_env_id)
        if validation.get("ok") is not True:
            return validation
        shown = env_service.show(quest_id=safe_quest_id, env_id=safe_env_id)
        if shown.get("ok") is not True:
            return shown
        manifest = shown["environment"]

        trajectory = TrajectoryStore(self.layout).show(quest_id=safe_quest_id, trajectory_id=safe_trajectory_id)
        if trajectory.get("ok") is not True:
            return trajectory
        trajectory_record = trajectory.get("trajectory") or {}
        if trajectory_record.get("env_id") != safe_env_id:
            return _error("trajectory_mismatch", "trajectory.env_id must match env_id", recoverable=False)
        if ((trajectory_record.get("idea") or {}).get("idea_id")) != safe_idea_id:
            return _error("trajectory_mismatch", "trajectory.idea.idea_id must match idea_id", recoverable=False)

        baseline_root = self._baseline_root(manifest)
        if isinstance(baseline_root, dict):
            return baseline_root
        if not baseline_root.exists() or not baseline_root.is_dir():
            return _error("invalid_path", f"baseline.repo_path does not exist or is not a directory: {manifest.get('baseline', {}).get('repo_path')}", recoverable=True)

        git_repo = self._is_git_repo(baseline_root)
        baseline = dict(manifest.get("baseline") or {})
        requested_commit = ""
        if git_repo:
            requested_commit = str(baseline.get("commit") or "").strip()
            if not requested_commit or requested_commit == "local-snapshot" or not _is_full_commit_hash(requested_commit):
                return _error("baseline_commit_required", "git baseline requires an explicit immutable 40-character baseline.commit", recoverable=True)

        variant_id = f"var_{uuid4().hex[:16]}"
        quest = self.layout.ensure_quest_layout(safe_quest_id)
        variant_dir = quest.detail_path(Path("variants") / variant_id)
        workspace = quest.detail_path(Path("runtime") / "worktrees" / variant_id)
        variant_path = variant_dir / "variant.json"
        patch_path = variant_dir / "patch.diff"
        workspace_created = False
        try:
            variant_dir.mkdir(parents=True, exist_ok=False)
            workspace.parent.mkdir(parents=True, exist_ok=True)
            snapshot_sha = None
            if git_repo:
                created = self._create_git_worktree(baseline_root=baseline_root, workspace=workspace, commit=requested_commit)
                if created.get("ok") is not True:
                    self._cleanup_variant(variant_dir=variant_dir, workspace=workspace, baseline_root=baseline_root, git_repo=True)
                    return created
                workspace_created = True
                baseline["commit"] = created["baseline_commit"]
            else:
                copied = self._create_snapshot_worktree(baseline_root=baseline_root, workspace=workspace)
                if copied.get("ok") is not True:
                    self._cleanup_variant(variant_dir=variant_dir, workspace=workspace, baseline_root=baseline_root, git_repo=False)
                    return copied
                workspace_created = True
                baseline["commit"] = copied["baseline_commit"]
                snapshot_sha = copied["baseline_snapshot_sha256"]

            now = utc_now()
            record = {
                "schema_version": 1,
                "variant_id": variant_id,
                "quest_id": safe_quest_id,
                "env_id": safe_env_id,
                "idea_id": safe_idea_id,
                "trajectory_id": safe_trajectory_id,
                "baseline_commit": baseline.get("commit"),
                "workspace_path": str(workspace),
                "patch_path": str(patch_path),
                "patch_sha256": None,
                "changed_paths": [],
                "protected_hashes_ok": True,
                "mutable_allowlist_ok": True,
                "smoke_status": "not_run",
                "package_path": None,
                "status": "created",
                "strategy": strategy,
                "variant_path": str(variant_path),
                "baseline": baseline,
                "baseline_repo_path": str(baseline_root),
                "baseline_snapshot_sha256": snapshot_sha,
                "created_at": now,
                "updated_at": now,
            }
            self.events.write_snapshot(record, path=variant_path)
            update = TrajectoryStore(self.layout).update_variant(
                quest_id=safe_quest_id,
                trajectory_id=safe_trajectory_id,
                variant={
                    "variant_id": variant_id,
                    "workspace_path": str(workspace),
                    "baseline_commit": baseline.get("commit"),
                    "baseline_snapshot_sha256": snapshot_sha,
                    "status": "created",
                },
            )
            if update.get("ok") is not True:
                self._cleanup_variant(variant_dir=variant_dir, workspace=workspace, baseline_root=baseline_root, git_repo=git_repo and workspace_created)
                return update
            self.events.append(
                "variant.created",
                {"quest_id": safe_quest_id, "env_id": safe_env_id, "trajectory_id": safe_trajectory_id, "variant_id": variant_id},
            )
            return {
                "ok": True,
                "quest_id": safe_quest_id,
                "env_id": safe_env_id,
                "trajectory_id": safe_trajectory_id,
                "variant_id": variant_id,
                "workspace_path": str(workspace),
                "variant_path": str(variant_path),
                "baseline_commit": baseline.get("commit"),
                "baseline_snapshot_sha256": snapshot_sha,
            }
        except OSError as exc:
            self._cleanup_variant(variant_dir=variant_dir, workspace=workspace, baseline_root=baseline_root, git_repo=git_repo and workspace_created)
            return _error("variant_create_failed", str(exc), recoverable=True)

    def apply_patch(self, *, quest_id: str, variant_id: str, patch_path: str) -> dict[str, Any]:
        loaded = self._read_variant(quest_id=quest_id, variant_id=variant_id)
        if loaded.get("ok") is not True:
            return loaded
        record = loaded["variant"]
        workspace = Path(str(record.get("workspace_path") or ""))
        if not workspace.is_dir():
            return _error("invalid_path", "variant workspace does not exist", recoverable=True)
        source_patch = Path(patch_path).expanduser().resolve()
        if not source_patch.exists() or not source_patch.is_file():
            return _error("invalid_path", f"patch_path does not exist: {patch_path}", recoverable=True)
        manifest = EnvironmentService(self.layout).show(quest_id=str(record["quest_id"]), env_id=str(record["env_id"]))
        if manifest.get("ok") is not True:
            return manifest
        environment = manifest["environment"]

        planned_paths = self._changed_paths_from_patch(source_patch)
        guard = self._readonly_guard(environment=environment, changed_paths=planned_paths)
        if guard.get("ok") is not True:
            failure = self._patch_failure(record=record, loaded_path=loaded["path"], error_type="readonly_or_eval_changed", message="Patch touches readonly or evaluator paths", extra={"blocked_paths": guard.get("blocked_paths", [])})
            return failure

        stat = _run_git(["apply", "--stat", str(source_patch)], cwd=workspace)
        if stat.returncode != 0:
            return self._patch_failure(record=record, loaded_path=loaded["path"], error_type="patch_fail", message="git apply --stat failed", extra={"stderr_tail": stat.stderr[-4000:]})
        check = _run_git(["apply", "--check", str(source_patch)], cwd=workspace)
        if check.returncode != 0:
            return self._patch_failure(record=record, loaded_path=loaded["path"], error_type="patch_fail", message="git apply --check failed", extra={"stderr_tail": check.stderr[-4000:]})

        destination = Path(str(record["patch_path"]))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_patch, destination)
        patch_sha = _sha256(destination)
        applied = _run_git(["apply", str(destination)], cwd=workspace)
        if applied.returncode != 0:
            return self._patch_failure(record=record, loaded_path=loaded["path"], error_type="patch_fail", message="git apply failed", extra={"stderr_tail": applied.stderr[-4000:]})

        intent = self._mark_intent_to_add(workspace=workspace, paths=planned_paths)
        if intent.get("ok") is not True:
            _run_git(["apply", "-R", str(destination)], cwd=workspace)
            return self._patch_failure(record=record, loaded_path=loaded["path"], error_type="patch_fail", message="git add --intent-to-add failed", extra=intent)
        diff = _run_git(["diff", "HEAD", "--name-only"], cwd=workspace)
        if diff.returncode != 0:
            _run_git(["apply", "-R", str(destination)], cwd=workspace)
            return self._patch_failure(record=record, loaded_path=loaded["path"], error_type="patch_fail", message="git diff --name-only failed", extra={"stderr_tail": diff.stderr[-4000:]})
        changed_paths = [line.strip() for line in diff.stdout.splitlines() if line.strip()]
        guard = self._readonly_guard(environment=environment, changed_paths=changed_paths)
        if guard.get("ok") is not True:
            _run_git(["apply", "-R", str(destination)], cwd=workspace)
            return self._patch_failure(record=record, loaded_path=loaded["path"], error_type="readonly_or_eval_changed", message="Patch touches readonly or evaluator paths", extra={"blocked_paths": guard.get("blocked_paths", [])})
        protected = self._workspace_protected_hashes_ok(environment=environment, workspace=workspace)
        if protected.get("ok") is not True:
            _run_git(["apply", "-R", str(destination)], cwd=workspace)
            return self._patch_failure(record=record, loaded_path=loaded["path"], error_type=str(protected.get("error_type") or "protected_hash_mismatch"), message=str(protected.get("error") or "protected hash mismatch"), extra=protected)
        current_diff = _run_git(["diff", "HEAD", "--binary", "--no-ext-diff"], cwd=workspace)
        if current_diff.returncode != 0:
            _run_git(["apply", "-R", str(destination)], cwd=workspace)
            return self._patch_failure(record=record, loaded_path=loaded["path"], error_type="patch_fail", message="git diff snapshot failed", extra={"stderr_tail": current_diff.stderr[-4000:]})

        record.update({
            "status": "patched",
            "patch_path": str(destination),
            "patch_sha256": patch_sha,
            "changed_paths": changed_paths,
            "workspace_diff_sha256": _text_sha256(current_diff.stdout),
            "protected_hashes_ok": True,
            "mutable_allowlist_ok": True,
            "updated_at": utc_now(),
        })
        self.events.write_snapshot(record, path=loaded["path"])
        TrajectoryStore(self.layout).update_patch(
            quest_id=str(record["quest_id"]),
            trajectory_id=str(record["trajectory_id"]),
            patch={"status": "applied", "patch_path": str(destination), "patch_sha256": patch_sha, "protected_hashes_ok": True, "changed_paths": changed_paths},
        )
        self.events.append("variant.patch_applied", {"quest_id": record["quest_id"], "env_id": record["env_id"], "trajectory_id": record["trajectory_id"], "variant_id": record["variant_id"], "changed_paths": changed_paths})
        return {"ok": True, "variant_id": record["variant_id"], "patch_path": str(destination), "patch_sha256": patch_sha, "changed_paths": changed_paths}

    def export_patch(self, *, quest_id: str, variant_id: str) -> dict[str, Any]:
        loaded = self._read_variant(quest_id=quest_id, variant_id=variant_id)
        if loaded.get("ok") is not True:
            return loaded
        record = loaded["variant"]
        workspace = Path(str(record.get("workspace_path") or ""))
        if not workspace.is_dir():
            return _error("invalid_path", "variant workspace does not exist", recoverable=True)
        intent = self._mark_intent_to_add(workspace=workspace, paths=list(record.get("changed_paths") or []))
        if intent.get("ok") is not True:
            return _error("patch_fail", "git add --intent-to-add failed", recoverable=True, **intent)
        manifest = EnvironmentService(self.layout).show(quest_id=str(record["quest_id"]), env_id=str(record["env_id"]))
        if manifest.get("ok") is not True:
            return manifest
        environment = manifest["environment"]
        names = _run_git(["diff", "HEAD", "--name-only"], cwd=workspace)
        if names.returncode != 0:
            return _error("patch_fail", "git diff --name-only failed", recoverable=True, stderr_tail=names.stderr[-4000:])
        changed_paths = [line.strip() for line in names.stdout.splitlines() if line.strip()]
        guard = self._readonly_guard(environment=environment, changed_paths=changed_paths)
        if guard.get("ok") is not True:
            return _error("readonly_or_eval_changed", "Workspace diff touches readonly, evaluator, or non-mutable paths", recoverable=True, blocked_paths=guard.get("blocked_paths", []))
        protected = self._workspace_protected_hashes_ok(environment=environment, workspace=workspace)
        if protected.get("ok") is not True:
            return protected
        diff = _run_git(["diff", "HEAD", "--binary", "--no-ext-diff"], cwd=workspace)
        if diff.returncode != 0:
            return _error("patch_fail", "git diff export failed", recoverable=True, stderr_tail=diff.stderr[-4000:])
        export_path = loaded["path"].parent / "export.patch"
        export_path.write_text(diff.stdout, encoding="utf-8")
        return {"ok": True, "variant_id": record["variant_id"], "patch_path": str(export_path), "patch_sha256": _sha256(export_path)}

    def check(self, *, quest_id: str, variant_id: str) -> dict[str, Any]:
        loaded = self._read_variant(quest_id=quest_id, variant_id=variant_id)
        if loaded.get("ok") is not True:
            return loaded
        record = loaded["variant"]
        workspace = Path(str(record.get("workspace_path") or ""))
        if not workspace.is_dir():
            return _error("invalid_path", "variant workspace does not exist", recoverable=True)
        manifest = EnvironmentService(self.layout).show(quest_id=str(record["quest_id"]), env_id=str(record["env_id"]))
        if manifest.get("ok") is not True:
            return manifest
        environment = manifest["environment"]
        commands = ((environment.get("commands") or {}).get("smoke") or [])
        if not isinstance(commands, list) or not commands:
            return _error("invalid_schema", "commands.smoke must be a non-empty list", recoverable=True)
        timeout = max(1, min(int(((environment.get("resources") or {}).get("max_wall_time_sec") or 60)), 300))
        records: list[dict[str, Any]] = []
        for command in commands:
            if not isinstance(command, list) or not command:
                return _error("invalid_schema", "commands.smoke entries must be argv lists", recoverable=True)
            completed = self._run_smoke_command(command=[str(part) for part in command], workspace=workspace, timeout=timeout)
            command_record = self._smoke_record(command=command, completed=completed)
            records.append(command_record)
            if completed.returncode != 0:
                failure_class = self._classify_smoke_failure(completed.stderr + "\n" + completed.stdout)
                checks = {"schema_version": 1, "variant_id": record["variant_id"], "quest_id": record["quest_id"], "env_id": record["env_id"], "trajectory_id": record["trajectory_id"], "smoke_status": "failed", "commands": records, "failure_class": failure_class, "updated_at": utc_now()}
                checks_path = loaded["path"].parent / "checks.json"
                self.events.write_snapshot(checks, path=checks_path)
                record.update({"status": "failed_smoke", "smoke_status": "failed", "checks_path": str(checks_path), "smoke": {"commands": records}, "updated_at": checks["updated_at"]})
                self.events.write_snapshot(record, path=loaded["path"])
                TrajectoryStore(self.layout).update_result(
                    quest_id=str(record["quest_id"]),
                    trajectory_id=str(record["trajectory_id"]),
                    result={"status": "failed"},
                    failure={"class": failure_class, "message": command_record["stderr_tail"] or command_record["stdout_tail"] or "smoke command failed"},
                )
                self.events.append("variant.smoke_failed", {"quest_id": record["quest_id"], "env_id": record["env_id"], "trajectory_id": record["trajectory_id"], "variant_id": record["variant_id"], "failure_class": failure_class})
                return {"ok": False, "error_type": failure_class, "recoverable": True, "smoke_status": "failed", "exit_code": completed.returncode, "stdout_tail": command_record["stdout_tail"], "stderr_tail": command_record["stderr_tail"]}
        checks = {"schema_version": 1, "variant_id": record["variant_id"], "quest_id": record["quest_id"], "env_id": record["env_id"], "trajectory_id": record["trajectory_id"], "smoke_status": "passed", "commands": records, "updated_at": utc_now()}
        checks_path = loaded["path"].parent / "checks.json"
        self.events.write_snapshot(checks, path=checks_path)
        record.update({"status": "checked", "smoke_status": "passed", "checks_path": str(checks_path), "smoke": {"commands": records}, "updated_at": checks["updated_at"]})
        self.events.write_snapshot(record, path=loaded["path"])
        TrajectoryStore(self.layout).update_variant(quest_id=str(record["quest_id"]), trajectory_id=str(record["trajectory_id"]), variant={"status": "checked", "smoke_status": "passed"})
        self.events.append("variant.smoke_passed", {"quest_id": record["quest_id"], "env_id": record["env_id"], "trajectory_id": record["trajectory_id"], "variant_id": record["variant_id"]})
        last = records[-1]
        return {"ok": True, "variant_id": record["variant_id"], "smoke_status": "passed", "exit_code": last["exit_code"], "stdout_tail": last["stdout_tail"], "stderr_tail": last["stderr_tail"]}

    def pack(self, *, quest_id: str, variant_id: str) -> dict[str, Any]:
        loaded = self._read_variant(quest_id=quest_id, variant_id=variant_id)
        if loaded.get("ok") is not True:
            return loaded
        record = loaded["variant"]
        workspace = Path(str(record.get("workspace_path") or ""))
        if not workspace.is_dir():
            return _error("invalid_path", "variant workspace does not exist", recoverable=True)
        if record.get("smoke_status") != "passed":
            return _error("invalid_state", "variant must pass smoke check before packaging", recoverable=True)
        env_service = EnvironmentService(self.layout)
        environment = env_service.show(quest_id=str(record["quest_id"]), env_id=str(record["env_id"]))
        if environment.get("ok") is not True:
            return environment
        environment_record = environment.get("environment") or {}
        protected_report = self._workspace_protected_hashes_ok(environment=environment_record, workspace=workspace)
        if protected_report.get("ok") is not True:
            record.update({"status": "failed_package", "updated_at": utc_now()})
            self.events.write_snapshot(record, path=loaded["path"])
            return protected_report
        drift = self._workspace_diff_matches_record(workspace=workspace, record=record)
        if drift.get("ok") is not True:
            record.update({"status": "failed_package", "updated_at": utc_now()})
            self.events.write_snapshot(record, path=loaded["path"])
            return drift
        variant_dir = loaded["path"].parent
        archive_path = variant_dir / "package.tar.gz"
        package_path = variant_dir / "package.json"
        self._write_deterministic_archive(workspace=workspace, archive_path=archive_path)
        archive_sha = _sha256(archive_path)
        package = {
            "schema_version": 1,
            "variant_id": record["variant_id"],
            "quest_id": record["quest_id"],
            "env_id": record["env_id"],
            "trajectory_id": record["trajectory_id"],
            "archive_path": str(archive_path),
            "archive_sha256": archive_sha,
            "changed_paths": list(record.get("changed_paths") or []),
            "patch_sha256": record.get("patch_sha256"),
            "environment_sha256": self._json_sha256(environment_record),
            "protected_hash_report": protected_report,
        }
        self.events.write_snapshot(package, path=package_path)
        record.update({"status": "packed", "package_path": str(package_path), "package_archive_path": str(archive_path), "package_archive_sha256": archive_sha, "updated_at": utc_now()})
        self.events.write_snapshot(record, path=loaded["path"])
        TrajectoryStore(self.layout).update_variant(quest_id=str(record["quest_id"]), trajectory_id=str(record["trajectory_id"]), variant={"status": "packed", "package_path": str(package_path), "package_archive_path": str(archive_path), "package_archive_sha256": archive_sha})
        self.events.append("variant.packed", {"quest_id": record["quest_id"], "env_id": record["env_id"], "trajectory_id": record["trajectory_id"], "variant_id": record["variant_id"], "archive_sha256": archive_sha})
        return {"ok": True, "variant_id": record["variant_id"], "archive_path": str(archive_path), "archive_sha256": archive_sha, "package_path": str(package_path)}

    def _baseline_root(self, manifest: dict[str, Any]) -> Path | dict[str, Any]:
        raw = str((manifest.get("baseline") or {}).get("repo_path") or ".")
        rel = Path(raw)
        if rel.is_absolute() or any(part in {"", ".."} for part in rel.parts):
            return _error("invalid_path", f"baseline.repo_path must be project-relative: {raw!r}", recoverable=False)
        target = (self.layout.project_root / rel).resolve()
        try:
            target.relative_to(self.layout.project_root.resolve())
        except ValueError:
            return _error("invalid_path", f"baseline.repo_path escapes project root: {raw!r}", recoverable=False)
        return target

    def _variant_path(self, *, quest_id: str, variant_id: str) -> Path:
        safe_variant_id = _safe_segment(variant_id, label="variant_id")
        return self.layout.quest_detail_path(quest_id, Path("variants") / safe_variant_id / "variant.json")

    def _read_variant(self, *, quest_id: str, variant_id: str) -> dict[str, Any]:
        try:
            path = self._variant_path(quest_id=quest_id, variant_id=variant_id)
        except ValueError as exc:
            return _error("invalid_path", str(exc), recoverable=False)
        if not path.exists():
            return _error("variant_not_found", f"Variant not found: {variant_id}", recoverable=True)
        try:
            return {"ok": True, "variant": _json_load(path), "path": path}
        except (json.JSONDecodeError, ValueError) as exc:
            return _error("invalid_schema", str(exc), recoverable=True)

    def _run_smoke_command(self, *, command: list[str], workspace: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                cwd=workspace,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            return subprocess.CompletedProcess(command, 127, stdout="", stderr=str(exc))
        except subprocess.TimeoutExpired as exc:
            stdout = self._coerce_output(exc.stdout)
            stderr = self._coerce_output(exc.stderr) or f"smoke command timed out after {timeout}s"
            return subprocess.CompletedProcess(command, 124, stdout=stdout, stderr=stderr)
        except OSError as exc:
            return subprocess.CompletedProcess(command, 126, stdout="", stderr=str(exc))

    def _coerce_output(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _smoke_record(self, *, command: list[Any], completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        return {
            "command": [str(part) for part in command],
            "exit_code": completed.returncode,
            "stdout_tail": stdout[-4000:],
            "stderr_tail": stderr[-4000:],
            "sha256": hashlib.sha256((stdout + "\n" + stderr).encode("utf-8", errors="replace")).hexdigest(),
        }

    def _classify_smoke_failure(self, text: str) -> str:
        if any(marker in text for marker in ("SyntaxError", "IndentationError", "TabError")):
            return "syntax_fail"
        if "ModuleNotFoundError" in text or "ImportError" in text:
            return "import_fail"
        return "smoke_fail"

    def _json_sha256(self, payload: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _workspace_diff_matches_record(self, *, workspace: Path, record: dict[str, Any]) -> dict[str, Any]:
        intent = self._mark_intent_to_add(workspace=workspace, paths=list(record.get("changed_paths") or []))
        if intent.get("ok") is not True:
            return _error("patch_fail", "git add --intent-to-add failed", recoverable=True, **intent)
        diff = _run_git(["diff", "HEAD", "--binary", "--no-ext-diff"], cwd=workspace)
        if diff.returncode != 0:
            return _error("patch_fail", "git diff snapshot failed", recoverable=True, stderr_tail=diff.stderr[-4000:])
        expected = str(record.get("workspace_diff_sha256") or _text_sha256(""))
        actual = _text_sha256(diff.stdout)
        if actual != expected:
            return _error("patch_drift", "workspace diff no longer matches recorded patch state", recoverable=True, expected_sha256=expected, actual_sha256=actual)
        unrecorded = self._unrecorded_package_paths(workspace=workspace, recorded_paths=list(record.get("changed_paths") or []))
        if unrecorded.get("ok") is not True:
            return unrecorded
        return {"ok": True, "workspace_diff_sha256": actual}

    def _unrecorded_package_paths(self, *, workspace: Path, recorded_paths: list[str]) -> dict[str, Any]:
        recorded = set(recorded_paths)
        status = _run_git(["status", "--porcelain", "--untracked-files=all", "--ignored"], cwd=workspace)
        if status.returncode != 0:
            return _error("patch_fail", "git status failed", recoverable=True, stderr_tail=status.stderr[-4000:])
        unrecorded: list[str] = []
        for line in status.stdout.splitlines():
            if not line.startswith(("?? ", "!! ")):
                continue
            rel = line[3:].strip().strip('"')
            if not rel or rel in recorded or self._exclude_from_package(rel):
                continue
            unrecorded.append(rel)
        if unrecorded:
            return _error("patch_drift", "workspace contains unrecorded package files", recoverable=True, unrecorded_paths=sorted(unrecorded))
        return {"ok": True}

    def _write_deterministic_archive(self, *, workspace: Path, archive_path: Path) -> None:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with archive_path.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w") as archive:
                    for path in sorted(item for item in workspace.rglob("*") if item.is_file()):
                        rel = path.relative_to(workspace).as_posix()
                        if self._exclude_from_package(rel):
                            continue
                        info = archive.gettarinfo(str(path), arcname=rel)
                        info.uid = 0
                        info.gid = 0
                        info.uname = ""
                        info.gname = ""
                        info.mtime = 0
                        mode = stat.S_IMODE(path.stat().st_mode)
                        info.mode = 0o755 if mode & 0o111 else 0o644
                        with path.open("rb") as handle:
                            archive.addfile(info, handle)

    def _exclude_from_package(self, rel_path: str) -> bool:
        parts = rel_path.split("/")
        blocked_dirs = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "CodexScientist", ".cache", "cache", "caches", "secrets", ".secrets"}
        if any(part in blocked_dirs for part in parts):
            return True
        name = parts[-1].lower()
        if name.endswith((".pyc", ".pyo", ".key", ".pem", ".p12")) or name in {".env", ".env.local", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}:
            return True
        return any(marker in name for marker in ("secret", "token", "credential", "password"))

    def _strip_baseline_prefix(self, environment: dict[str, Any], raw_path: str) -> str:
        path = str(raw_path or "").replace("\\", "/").strip("/")
        prefix = str((environment.get("baseline") or {}).get("repo_path") or ".").replace("\\", "/").strip("/")
        if not prefix or prefix == ".":
            return path
        if path == prefix:
            return ""
        if path.startswith(prefix + "/"):
            return path[len(prefix) + 1 :]
        return path

    def _environment_path_patterns(self, environment: dict[str, Any], items: list[Any]) -> list[str]:
        patterns: list[str] = []
        for item in items:
            raw = item.get("path") if isinstance(item, dict) else item
            value = self._strip_baseline_prefix(environment, str(raw or ""))
            if value:
                patterns.append(value)
        return patterns

    def _readonly_guard(self, *, environment: dict[str, Any], changed_paths: list[str]) -> dict[str, Any]:
        mutable = self._environment_path_patterns(environment, list(environment.get("mutable_allowlist") or []))
        protected = self._environment_path_patterns(environment, list(environment.get("protected_files") or []))
        datasets = self._environment_path_patterns(environment, list(environment.get("datasets") or []))
        if changed_paths and not mutable:
            return {"ok": False, "blocked_paths": sorted(changed_paths)}
        guard = check_readonly_changes(changed_paths=changed_paths, editable_paths=mutable, readonly_paths=protected + datasets, eval_paths=protected)
        if guard.get("ok") is not True:
            return {"ok": False, "blocked_paths": guard.get("blocked_paths", [])}
        outside_mutable = [path for path in changed_paths if mutable and not any(fnmatch(path, pattern) for pattern in mutable)]
        if outside_mutable:
            return {"ok": False, "blocked_paths": outside_mutable}
        return {"ok": True, "blocked_paths": []}

    def _changed_paths_from_patch(self, patch_path: Path) -> list[str]:
        paths: set[str] = set()
        for line in patch_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("diff --git "):
                parts = line.split()
                for raw in parts[2:4]:
                    if raw.startswith("a/") or raw.startswith("b/"):
                        raw = raw[2:]
                    if raw and raw != "/dev/null":
                        paths.add(raw)
                continue
            if line.startswith("+++ ") or line.startswith("--- "):
                raw = line[4:].split("\t", 1)[0].strip()
                if raw == "/dev/null":
                    continue
                if raw.startswith("a/") or raw.startswith("b/"):
                    raw = raw[2:]
                if raw:
                    paths.add(raw)
        return sorted(paths)

    def _mark_intent_to_add(self, *, workspace: Path, paths: list[str]) -> dict[str, Any]:
        existing = [path for path in paths if path and (workspace / path).exists()]
        if not existing:
            return {"ok": True}
        result = _run_git(["add", "-f", "--intent-to-add", "--", *existing], cwd=workspace)
        if result.returncode != 0:
            return {"ok": False, "stderr_tail": result.stderr[-4000:]}
        return {"ok": True}

    def _workspace_protected_hashes_ok(self, *, environment: dict[str, Any], workspace: Path) -> dict[str, Any]:
        for item in environment.get("protected_files") or []:
            if not isinstance(item, dict):
                continue
            rel = self._strip_baseline_prefix(environment, str(item.get("path") or ""))
            expected = str(item.get("sha256") or "")
            target = (workspace / rel).resolve()
            try:
                target.relative_to(workspace.resolve())
            except ValueError:
                return _error("invalid_path", f"protected file escapes workspace: {rel}", recoverable=False)
            if not target.exists() or not target.is_file():
                return _error("protected_hash_mismatch", f"protected file missing after patch: {rel}", recoverable=False, path=rel)
            actual = _sha256(target)
            if actual != expected:
                return _error("protected_hash_mismatch", f"protected hash mismatch after patch: {rel}", recoverable=False, path=rel, expected_sha256=expected, actual_sha256=actual)
        return {"ok": True}

    def _patch_failure(self, *, record: dict[str, Any], loaded_path: Path, error_type: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _error(error_type, message, recoverable=True, **(extra or {}))
        record["status"] = "failed_patch"
        record["updated_at"] = utc_now()
        self.events.write_snapshot(record, path=loaded_path)
        TrajectoryStore(self.layout).update_patch(
            quest_id=str(record.get("quest_id")),
            trajectory_id=str(record.get("trajectory_id")),
            patch={"status": "failed", "failure_class": error_type, "failure_message": message},
        )
        self.events.append("variant.patch_failed", {"quest_id": record.get("quest_id"), "env_id": record.get("env_id"), "trajectory_id": record.get("trajectory_id"), "variant_id": record.get("variant_id"), "error_type": error_type})
        return payload

    def _is_git_repo(self, root: Path) -> bool:
        result = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=root)
        return result.returncode == 0 and result.stdout.strip() == "true"

    def _cleanup_variant(self, *, variant_dir: Path, workspace: Path, baseline_root: Path, git_repo: bool) -> None:
        if git_repo and workspace.exists():
            _run_git(["worktree", "remove", "--force", str(workspace)], cwd=baseline_root)
        shutil.rmtree(workspace, ignore_errors=True)
        shutil.rmtree(variant_dir, ignore_errors=True)

    def _create_git_worktree(self, *, baseline_root: Path, workspace: Path, commit: str) -> dict[str, Any]:
        result = _run_git(["worktree", "add", "--detach", str(workspace), commit], cwd=baseline_root)
        if result.returncode != 0:
            return _error("variant_create_failed", "git worktree add failed", recoverable=True, stderr_tail=result.stderr[-4000:])
        resolved = _run_git(["rev-parse", "HEAD"], cwd=workspace)
        if resolved.returncode != 0:
            return _error("variant_create_failed", "git rev-parse failed after worktree create", recoverable=True, stderr_tail=resolved.stderr[-4000:])
        return {"ok": True, "baseline_commit": resolved.stdout.strip()}

    def _create_snapshot_worktree(self, *, baseline_root: Path, workspace: Path) -> dict[str, Any]:
        shutil.copytree(
            baseline_root,
            workspace,
            ignore=shutil.ignore_patterns(".git", "CodexScientist", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"),
        )
        init = _run_git(["init"], cwd=workspace)
        if init.returncode != 0:
            return _error("variant_create_failed", "git init failed", recoverable=True, stderr_tail=init.stderr[-4000:])
        add = _run_git(["add", "-A"], cwd=workspace)
        if add.returncode != 0:
            return _error("variant_create_failed", "git add failed", recoverable=True, stderr_tail=add.stderr[-4000:])
        commit = _run_git(
            ["-c", "user.name=CodexScientist", "-c", "user.email=codexscientist@example.invalid", "commit", "--allow-empty", "-m", "baseline snapshot"],
            cwd=workspace,
        )
        if commit.returncode != 0:
            return _error("variant_create_failed", "git commit failed", recoverable=True, stderr_tail=commit.stderr[-4000:])
        resolved = _run_git(["rev-parse", "HEAD"], cwd=workspace)
        if resolved.returncode != 0:
            return _error("variant_create_failed", "git rev-parse failed after snapshot create", recoverable=True, stderr_tail=resolved.stderr[-4000:])
        return {"ok": True, "baseline_commit": resolved.stdout.strip(), "baseline_snapshot_sha256": _tree_snapshot_sha256(workspace)}
