from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.event_store import EventStore
from codex_scientist.services.project_state import ProjectLayout
from codex_scientist.services.trajectory import TrajectoryStore


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _make_baseline_repo(project_root: Path, *, git_repo: bool) -> tuple[Path, str]:
    repo = project_root / "repo"
    (repo / "MATH").mkdir(parents=True, exist_ok=True)
    (repo / "train.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "evaluate.py").write_text("print('eval')\n", encoding="utf-8")
    (repo / "MATH" / "test.jsonl").write_text("{}\n", encoding="utf-8")
    if not git_repo:
        return repo, "local-snapshot"
    _run(["git", "init"], repo)
    _run(["git", "add", "train.py", "evaluate.py", "MATH/test.jsonl"], repo)
    _run(["git", "-c", "user.name=CodexScientist", "-c", "user.email=codexscientist@example.invalid", "commit", "-m", "baseline"], repo)
    commit = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    return repo, commit


def _manifest(project_root: Path, *, git_repo: bool = True, quest_id: str = "QVAR") -> dict:
    repo, commit = _make_baseline_repo(project_root, git_repo=git_repo)
    evaluate = repo / "evaluate.py"
    data = repo / "MATH" / "test.jsonl"
    return {
        "schema_version": 1,
        "env_id": "env_variant",
        "quest_id": quest_id,
        "title": "Variant toy environment",
        "problem": "Validate isolated variants",
        "baseline": {
            "repo_path": "repo",
            "commit": commit,
            "baseline_id": "baseline_main",
            "baseline_metric": {"name": "score", "value": 0.5, "direction": "maximize"},
        },
        "mutable_allowlist": ["repo/train.py"],
        "protected_files": [{"path": "repo/evaluate.py", "sha256": _sha256(evaluate), "role": "evaluator"}],
        "datasets": [{"path": "repo/MATH/test.jsonl", "sha256": _sha256(data), "split": "validation"}],
        "commands": {
            "setup": [["python", "-V"]],
            "smoke": [["python", "-m", "py_compile", "train.py"]],
            "run": [["python", "train.py"]],
            "evaluate": [["python", "evaluate.py"]],
        },
        "primary_metric": {"name": "score", "direction": "maximize", "parser": "json_path", "path": "metrics.score"},
        "sample_metrics": {"metrics": {"score": 0.75}},
        "secondary_metrics": [],
        "resources": {"gpu_count": 0, "gpu_min_memory_gb": 0, "max_wall_time_sec": 60},
        "budget": {"max_gpu_hours": 0.0, "max_usd": 0.0},
        "security": {"network_policy": "restricted", "forbid_metric_logging_changes": True, "clean_room_revalidation_required_for_top_k": True},
    }


def _registered_trajectory(project_root: Path, *, git_repo: bool = True) -> tuple[ProjectLayout, str, dict]:
    layout = ProjectLayout.from_project_root(project_root)
    manifest = _manifest(project_root, git_repo=git_repo)
    assert EnvironmentService(layout).register(quest_id="QVAR", manifest=manifest)["ok"] is True
    trajectory = TrajectoryStore(layout).create(
        quest_id="QVAR",
        env_id="env_variant",
        idea={"idea_id": "idea_variant", "title": "Variant idea"},
        strategy="manual",
    )
    assert trajectory["ok"] is True
    return layout, trajectory["trajectory_id"], manifest


def test_variant_create_uses_quest_worktree_for_git_baseline(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, trajectory_id, manifest = _registered_trajectory(tmp_path, git_repo=True)
    result = VariantService(layout).create(
        quest_id="QVAR",
        env_id="env_variant",
        trajectory_id=trajectory_id,
        idea_id="idea_variant",
    )

    assert result["ok"] is True
    assert result["variant_id"].startswith("var_")
    workspace = Path(result["workspace_path"])
    assert workspace.is_dir()
    assert workspace.is_relative_to(tmp_path / "CodexScientist" / "quests" / "QVAR" / "runtime" / "worktrees")
    assert (workspace / "train.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert _run(["git", "rev-parse", "HEAD"], workspace).stdout.strip() == manifest["baseline"]["commit"]

    variant_path = tmp_path / "CodexScientist" / "quests" / "QVAR" / "variants" / result["variant_id"] / "variant.json"
    record = json.loads(variant_path.read_text(encoding="utf-8"))
    required_fields = {
        "schema_version",
        "variant_id",
        "quest_id",
        "env_id",
        "idea_id",
        "trajectory_id",
        "baseline_commit",
        "workspace_path",
        "patch_path",
        "patch_sha256",
        "changed_paths",
        "protected_hashes_ok",
        "mutable_allowlist_ok",
        "smoke_status",
        "package_path",
        "status",
    }
    assert required_fields <= set(record), sorted(required_fields - set(record))
    assert record["baseline_commit"] == manifest["baseline"]["commit"]
    assert record["patch_sha256"] is None
    assert record["changed_paths"] == []
    assert record["protected_hashes_ok"] is True
    assert record["mutable_allowlist_ok"] is True
    assert record["smoke_status"] == "not_run"
    assert record["package_path"] is None
    assert record["strategy"] == "worktree"

    trajectory = json.loads((tmp_path / "CodexScientist" / "quests" / "QVAR" / "trajectories" / f"{trajectory_id}.json").read_text(encoding="utf-8"))
    assert trajectory["variant"]["variant_id"] == result["variant_id"]
    assert trajectory["variant"]["workspace_path"] == result["workspace_path"]
    assert any(event.get("event_type") == "variant.created" for event in EventStore(layout).read_events())


def test_variant_create_copies_non_git_baseline_and_records_snapshot(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, trajectory_id, _manifest = _registered_trajectory(tmp_path, git_repo=False)
    result = VariantService(layout).create(
        quest_id="QVAR",
        env_id="env_variant",
        trajectory_id=trajectory_id,
        idea_id="idea_variant",
    )

    assert result["ok"] is True
    workspace = Path(result["workspace_path"])
    assert (workspace / ".git").is_dir()
    assert (workspace / "train.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert not (workspace / "CodexScientist").exists()
    assert len(result["baseline_snapshot_sha256"]) == 64
    assert _run(["git", "status", "--short"], workspace).stdout == ""


def test_variant_create_blocks_invalid_environment_before_workspace_write(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, trajectory_id, _manifest = _registered_trajectory(tmp_path, git_repo=True)
    (tmp_path / "repo" / "evaluate.py").write_text("print('changed')\n", encoding="utf-8")

    result = VariantService(layout).create(
        quest_id="QVAR",
        env_id="env_variant",
        trajectory_id=trajectory_id,
        idea_id="idea_variant",
    )

    assert result["ok"] is False
    assert result["error_type"] == "protected_hash_mismatch"
    worktree_root = tmp_path / "CodexScientist" / "quests" / "QVAR" / "runtime" / "worktrees"
    assert list(worktree_root.iterdir()) == []


def test_variant_create_fails_closed_when_git_baseline_commit_missing_or_symbolic(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = _manifest(tmp_path, git_repo=True)
    manifest["baseline"].pop("commit")
    assert EnvironmentService(layout).register(quest_id="QVAR", manifest=manifest)["ok"] is True
    trajectory_id = TrajectoryStore(layout).create(
        quest_id="QVAR",
        env_id="env_variant",
        idea={"idea_id": "idea_variant", "title": "Variant idea"},
    )["trajectory_id"]

    result = VariantService(layout).create(quest_id="QVAR", env_id="env_variant", trajectory_id=trajectory_id, idea_id="idea_variant")

    assert result["ok"] is False
    assert result["error_type"] == "baseline_commit_required"
    assert list((tmp_path / "CodexScientist" / "quests" / "QVAR" / "variants").iterdir()) == []

    symbolic = json.loads(json.dumps(manifest))
    symbolic["env_id"] = "env_symbolic"
    symbolic["baseline"]["commit"] = "HEAD"
    assert EnvironmentService(layout).register(quest_id="QVAR", manifest=symbolic)["ok"] is True
    symbolic_trajectory_id = TrajectoryStore(layout).create(
        quest_id="QVAR",
        env_id="env_symbolic",
        idea={"idea_id": "idea_variant", "title": "Variant idea"},
    )["trajectory_id"]

    symbolic_result = VariantService(layout).create(quest_id="QVAR", env_id="env_symbolic", trajectory_id=symbolic_trajectory_id, idea_id="idea_variant")
    assert symbolic_result["ok"] is False
    assert symbolic_result["error_type"] == "baseline_commit_required"


def test_variant_create_rejects_trajectory_env_or_idea_mismatch(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, trajectory_id, _registered_manifest = _registered_trajectory(tmp_path, git_repo=True)
    other = json.loads(json.dumps(_registered_manifest))
    other["env_id"] = "env_other"
    other["baseline"]["commit"] = _run(["git", "rev-parse", "HEAD"], tmp_path / "repo").stdout.strip()
    assert EnvironmentService(layout).register(quest_id="QVAR", manifest=other)["ok"] is True

    env_mismatch = VariantService(layout).create(
        quest_id="QVAR",
        env_id="env_other",
        trajectory_id=trajectory_id,
        idea_id="idea_variant",
    )
    assert env_mismatch["ok"] is False
    assert env_mismatch["error_type"] == "trajectory_mismatch"

    idea_mismatch = VariantService(layout).create(
        quest_id="QVAR",
        env_id="env_variant",
        trajectory_id=trajectory_id,
        idea_id="idea_other",
    )
    assert idea_mismatch["ok"] is False
    assert idea_mismatch["error_type"] == "trajectory_mismatch"


def _created_variant(tmp_path: Path) -> tuple[ProjectLayout, str, str]:
    from codex_scientist.services.variant import VariantService

    layout, trajectory_id, _manifest = _registered_trajectory(tmp_path, git_repo=True)
    created = VariantService(layout).create(quest_id="QVAR", env_id="env_variant", trajectory_id=trajectory_id, idea_id="idea_variant")
    assert created["ok"] is True
    return layout, trajectory_id, created["variant_id"]


def _created_variant_with_mutable(tmp_path: Path, mutable_allowlist: list[str]) -> tuple[ProjectLayout, str, str]:
    from codex_scientist.services.variant import VariantService

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = _manifest(tmp_path, git_repo=True)
    manifest["mutable_allowlist"] = mutable_allowlist
    assert EnvironmentService(layout).register(quest_id="QVAR", manifest=manifest)["ok"] is True
    trajectory_id = TrajectoryStore(layout).create(quest_id="QVAR", env_id="env_variant", idea={"idea_id": "idea_variant", "title": "Variant idea"})["trajectory_id"]
    created = VariantService(layout).create(quest_id="QVAR", env_id="env_variant", trajectory_id=trajectory_id, idea_id="idea_variant")
    assert created["ok"] is True
    return layout, trajectory_id, created["variant_id"]


def _write_patch(path: Path, *, file_path: str = "train.py", old: str = "VALUE = 1", new: str = "VALUE = 2") -> None:
    path.write_text(
        f"diff --git a/{file_path} b/{file_path}\n"
        f"--- a/{file_path}\n"
        f"+++ b/{file_path}\n"
        "@@ -1 +1 @@\n"
        f"-{old}\n"
        f"+{new}\n",
        encoding="utf-8",
    )


def test_variant_apply_patch_records_changed_paths_and_exports_diff(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, trajectory_id, variant_id = _created_variant(tmp_path)
    patch_path = tmp_path / "change.diff"
    _write_patch(patch_path)

    applied = VariantService(layout).apply_patch(quest_id="QVAR", variant_id=variant_id, patch_path=str(patch_path))

    assert applied["ok"] is True
    assert applied["changed_paths"] == ["train.py"]
    assert len(applied["patch_sha256"]) == 64
    variant_record = json.loads((tmp_path / "CodexScientist" / "quests" / "QVAR" / "variants" / variant_id / "variant.json").read_text(encoding="utf-8"))
    assert variant_record["status"] == "patched"
    assert variant_record["patch_sha256"] == applied["patch_sha256"]
    assert variant_record["changed_paths"] == ["train.py"]
    assert variant_record["protected_hashes_ok"] is True
    assert variant_record["mutable_allowlist_ok"] is True
    trajectory = json.loads((tmp_path / "CodexScientist" / "quests" / "QVAR" / "trajectories" / f"{trajectory_id}.json").read_text(encoding="utf-8"))
    assert trajectory["patch"]["status"] == "applied"

    exported = VariantService(layout).export_patch(quest_id="QVAR", variant_id=variant_id)
    assert exported["ok"] is True
    exported_text = Path(exported["patch_path"]).read_text(encoding="utf-8")
    assert "diff --git a/train.py b/train.py" in exported_text
    assert "+VALUE = 2" in exported_text


def test_variant_apply_patch_blocks_protected_evaluator(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant(tmp_path)
    patch_path = tmp_path / "eval.diff"
    _write_patch(patch_path, file_path="evaluate.py", old="print('eval')", new="print('changed')")

    result = VariantService(layout).apply_patch(quest_id="QVAR", variant_id=variant_id, patch_path=str(patch_path))

    assert result["ok"] is False
    assert result["error_type"] == "readonly_or_eval_changed"
    assert "evaluate.py" in result["blocked_paths"]
    workspace = tmp_path / "CodexScientist" / "quests" / "QVAR" / "runtime" / "worktrees" / variant_id
    assert (workspace / "evaluate.py").read_text(encoding="utf-8") == "print('eval')\n"


def test_variant_apply_patch_bad_hunk_returns_patch_fail(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, trajectory_id, variant_id = _created_variant(tmp_path)
    patch_path = tmp_path / "bad.diff"
    _write_patch(patch_path, file_path="train.py", old="MISSING = 1", new="VALUE = 3")

    result = VariantService(layout).apply_patch(quest_id="QVAR", variant_id=variant_id, patch_path=str(patch_path))

    assert result["ok"] is False
    assert result["error_type"] == "patch_fail"
    trajectory = json.loads((tmp_path / "CodexScientist" / "quests" / "QVAR" / "trajectories" / f"{trajectory_id}.json").read_text(encoding="utf-8"))
    assert trajectory["patch"]["status"] == "failed"


def test_variant_apply_patch_preserves_subdirectory_paths(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = _manifest(tmp_path, git_repo=True)
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True, exist_ok=True)
    (repo / "pkg" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    _run(["git", "add", "pkg/module.py"], repo)
    _run(["git", "-c", "user.name=CodexScientist", "-c", "user.email=codexscientist@example.invalid", "commit", "-m", "add module"], repo)
    commit = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    manifest["baseline"]["commit"] = commit
    manifest["mutable_allowlist"] = ["repo/train.py", "repo/pkg/module.py"]
    assert EnvironmentService(layout).register(quest_id="QVAR", manifest=manifest)["ok"] is True
    trajectory_id = TrajectoryStore(layout).create(quest_id="QVAR", env_id="env_variant", idea={"idea_id": "idea_variant", "title": "Variant idea"})["trajectory_id"]
    created = VariantService(layout).create(quest_id="QVAR", env_id="env_variant", trajectory_id=trajectory_id, idea_id="idea_variant")
    assert created["ok"] is True

    patch_path = tmp_path / "subdir.diff"
    _write_patch(patch_path, file_path="pkg/module.py")
    applied = VariantService(layout).apply_patch(quest_id="QVAR", variant_id=created["variant_id"], patch_path=str(patch_path))
    assert applied["ok"] is True
    assert applied["changed_paths"] == ["pkg/module.py"]


def test_variant_apply_patch_blocks_binary_new_file_outside_mutable_allowlist(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant(tmp_path)
    patch_repo = tmp_path / "patch_repo"
    _run(["git", "clone", str(tmp_path / "repo"), str(patch_repo)], tmp_path)
    (patch_repo / "secret.bin").write_bytes(b"\x00\x01secret")
    _run(["git", "add", "--intent-to-add", "secret.bin"], patch_repo)
    patch_text = _run(["git", "diff", "--binary", "--no-ext-diff", "--", "secret.bin"], patch_repo).stdout
    patch_path = tmp_path / "binary-new.diff"
    patch_path.write_text(patch_text, encoding="utf-8")

    result = VariantService(layout).apply_patch(quest_id="QVAR", variant_id=variant_id, patch_path=str(patch_path))

    assert result["ok"] is False
    assert result["error_type"] == "readonly_or_eval_changed"
    assert result["blocked_paths"] == ["secret.bin"]


def test_variant_apply_patch_exports_allowed_new_file(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant_with_mutable(tmp_path, ["repo/train.py", "repo/new.py"])
    patch_path = tmp_path / "new-file.diff"
    patch_path.write_text(
        "diff --git a/new.py b/new.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/new.py\n"
        "@@ -0,0 +1 @@\n"
        "+NEW_VALUE = 1\n",
        encoding="utf-8",
    )

    applied = VariantService(layout).apply_patch(quest_id="QVAR", variant_id=variant_id, patch_path=str(patch_path))
    assert applied["ok"] is True
    assert applied["changed_paths"] == ["new.py"]

    exported = VariantService(layout).export_patch(quest_id="QVAR", variant_id=variant_id)
    assert exported["ok"] is True
    assert "diff --git a/new.py b/new.py" in Path(exported["patch_path"]).read_text(encoding="utf-8")


def test_variant_apply_patch_exports_allowed_gitignored_new_file(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = _manifest(tmp_path, git_repo=True)
    repo = tmp_path / "repo"
    (repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    _run(["git", "add", ".gitignore"], repo)
    _run(["git", "-c", "user.name=CodexScientist", "-c", "user.email=codexscientist@example.invalid", "commit", "-m", "add gitignore"], repo)
    manifest["baseline"]["commit"] = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    manifest["mutable_allowlist"] = ["repo/train.py", "repo/ignored.txt"]
    assert EnvironmentService(layout).register(quest_id="QVAR", manifest=manifest)["ok"] is True
    trajectory_id = TrajectoryStore(layout).create(quest_id="QVAR", env_id="env_variant", idea={"idea_id": "idea_variant", "title": "Variant idea"})["trajectory_id"]
    created = VariantService(layout).create(quest_id="QVAR", env_id="env_variant", trajectory_id=trajectory_id, idea_id="idea_variant")
    assert created["ok"] is True

    patch_path = tmp_path / "ignored-file.diff"
    patch_path.write_text(
        "diff --git a/ignored.txt b/ignored.txt\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/ignored.txt\n"
        "@@ -0,0 +1 @@\n"
        "+VISIBLE = 1\n",
        encoding="utf-8",
    )
    applied = VariantService(layout).apply_patch(quest_id="QVAR", variant_id=created["variant_id"], patch_path=str(patch_path))
    assert applied["ok"] is True
    assert applied["changed_paths"] == ["ignored.txt"]

    exported = VariantService(layout).export_patch(quest_id="QVAR", variant_id=created["variant_id"])
    assert exported["ok"] is True
    assert "diff --git a/ignored.txt b/ignored.txt" in Path(exported["patch_path"]).read_text(encoding="utf-8")


def test_variant_export_patch_blocks_protected_workspace_drift(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant(tmp_path)
    workspace = tmp_path / "CodexScientist" / "quests" / "QVAR" / "runtime" / "worktrees" / variant_id
    (workspace / "evaluate.py").write_text("print('drift')\n", encoding="utf-8")

    result = VariantService(layout).export_patch(quest_id="QVAR", variant_id=variant_id)

    assert result["ok"] is False
    assert result["error_type"] in {"readonly_or_eval_changed", "protected_hash_mismatch"}


def test_variant_apply_patch_fails_closed_when_mutable_allowlist_empty(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant_with_mutable(tmp_path, [])
    patch_path = tmp_path / "change.diff"
    _write_patch(patch_path)

    result = VariantService(layout).apply_patch(quest_id="QVAR", variant_id=variant_id, patch_path=str(patch_path))

    assert result["ok"] is False
    assert result["error_type"] == "readonly_or_eval_changed"
    assert result["blocked_paths"] == ["train.py"]


def test_variant_check_success_and_pack_excludes_git_cache_and_secrets(tmp_path: Path):
    import tarfile

    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant(tmp_path)
    patch_path = tmp_path / "change.diff"
    _write_patch(patch_path)
    assert VariantService(layout).apply_patch(quest_id="QVAR", variant_id=variant_id, patch_path=str(patch_path))["ok"] is True

    checked = VariantService(layout).check(quest_id="QVAR", variant_id=variant_id)

    assert checked["ok"] is True
    assert checked["smoke_status"] == "passed"
    assert checked["exit_code"] == 0
    checks_path = tmp_path / "CodexScientist" / "quests" / "QVAR" / "variants" / variant_id / "checks.json"
    checks = json.loads(checks_path.read_text(encoding="utf-8"))
    assert checks["smoke_status"] == "passed"
    assert checks["commands"][0]["exit_code"] == 0
    assert len(checks["commands"][0]["sha256"]) == 64

    workspace = tmp_path / "CodexScientist" / "quests" / "QVAR" / "runtime" / "worktrees" / variant_id
    (workspace / "secret.key").write_text("token=secret\n", encoding="utf-8")
    (workspace / "__pycache__").mkdir(exist_ok=True)
    (workspace / "__pycache__" / "x.pyc").write_bytes(b"cache")

    packed = VariantService(layout).pack(quest_id="QVAR", variant_id=variant_id)

    assert packed["ok"] is True
    assert len(packed["archive_sha256"]) == 64
    with tarfile.open(packed["archive_path"], "r:gz") as archive:
        names = archive.getnames()
    assert "train.py" in names
    assert not any(name.startswith(".git/") or "/.git/" in name for name in names)
    assert "secret.key" not in names
    assert not any("__pycache__" in name for name in names)
    package = json.loads(Path(packed["package_path"]).read_text(encoding="utf-8"))
    assert package["changed_paths"] == ["train.py"]
    assert package["patch_sha256"]
    assert package["protected_hash_report"]["ok"] is True
    first_sha = packed["archive_sha256"]
    second = VariantService(layout).pack(quest_id="QVAR", variant_id=variant_id)
    assert second["ok"] is True
    assert second["archive_sha256"] == first_sha


def test_variant_pack_blocks_protected_workspace_drift(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant(tmp_path)
    checked = VariantService(layout).check(quest_id="QVAR", variant_id=variant_id)
    assert checked["ok"] is True
    workspace = tmp_path / "CodexScientist" / "quests" / "QVAR" / "runtime" / "worktrees" / variant_id
    (workspace / "evaluate.py").write_text("print('packed drift')\n", encoding="utf-8")

    result = VariantService(layout).pack(quest_id="QVAR", variant_id=variant_id)

    assert result["ok"] is False
    assert result["error_type"] in {"readonly_or_eval_changed", "protected_hash_mismatch"}


def test_variant_pack_requires_passed_smoke_check(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant(tmp_path)

    result = VariantService(layout).pack(quest_id="QVAR", variant_id=variant_id)

    assert result["ok"] is False
    assert result["error_type"] == "invalid_state"


def test_variant_check_missing_command_returns_structured_smoke_failure(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = _manifest(tmp_path, git_repo=True)
    manifest["commands"]["smoke"] = [["definitely_missing_command_for_codexscientist_smoke"]]
    assert EnvironmentService(layout).register(quest_id="QVAR", manifest=manifest)["ok"] is True
    trajectory_id = TrajectoryStore(layout).create(quest_id="QVAR", env_id="env_variant", idea={"idea_id": "idea_variant", "title": "Variant idea"})["trajectory_id"]
    created = VariantService(layout).create(quest_id="QVAR", env_id="env_variant", trajectory_id=trajectory_id, idea_id="idea_variant")
    assert created["ok"] is True

    result = VariantService(layout).check(quest_id="QVAR", variant_id=created["variant_id"])

    assert result["ok"] is False
    assert result["error_type"] == "smoke_fail"
    checks_path = tmp_path / "CodexScientist" / "quests" / "QVAR" / "variants" / created["variant_id"] / "checks.json"
    checks = json.loads(checks_path.read_text(encoding="utf-8"))
    assert checks["smoke_status"] == "failed"
    assert checks["commands"][0]["exit_code"] == 127


def test_variant_check_classifies_indentation_error_as_syntax_fail(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant(tmp_path)
    workspace = tmp_path / "CodexScientist" / "quests" / "QVAR" / "runtime" / "worktrees" / variant_id
    (workspace / "train.py").write_text("def broken():\n  x = 1\n    y = 2\n", encoding="utf-8")

    result = VariantService(layout).check(quest_id="QVAR", variant_id=variant_id)

    assert result["ok"] is False
    assert result["error_type"] == "syntax_fail"


def test_variant_pack_excludes_common_cache_and_secret_paths(tmp_path: Path):
    import tarfile

    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant(tmp_path)
    assert VariantService(layout).check(quest_id="QVAR", variant_id=variant_id)["ok"] is True
    workspace = tmp_path / "CodexScientist" / "quests" / "QVAR" / "runtime" / "worktrees" / variant_id
    for rel in [".cache/tool.bin", "cache/local.txt", "secrets/config.txt", "id_rsa", "password.txt"]:
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("must-not-package\n", encoding="utf-8")

    packed = VariantService(layout).pack(quest_id="QVAR", variant_id=variant_id)

    assert packed["ok"] is True
    with tarfile.open(packed["archive_path"], "r:gz") as archive:
        names = archive.getnames()
    assert not any(name in names for name in [".cache/tool.bin", "cache/local.txt", "secrets/config.txt", "id_rsa", "password.txt"])


def test_variant_pack_blocks_workspace_drift_after_check(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant(tmp_path)
    patch_path = tmp_path / "change.diff"
    _write_patch(patch_path)
    assert VariantService(layout).apply_patch(quest_id="QVAR", variant_id=variant_id, patch_path=str(patch_path))["ok"] is True
    assert VariantService(layout).check(quest_id="QVAR", variant_id=variant_id)["ok"] is True
    workspace = tmp_path / "CodexScientist" / "quests" / "QVAR" / "runtime" / "worktrees" / variant_id
    (workspace / "train.py").write_text("print('unrecorded drift')\n", encoding="utf-8")

    result = VariantService(layout).pack(quest_id="QVAR", variant_id=variant_id)

    assert result["ok"] is False
    assert result["error_type"] == "patch_drift"


def test_variant_pack_blocks_unrecorded_new_file_after_check(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant(tmp_path)
    assert VariantService(layout).check(quest_id="QVAR", variant_id=variant_id)["ok"] is True
    workspace = tmp_path / "CodexScientist" / "quests" / "QVAR" / "runtime" / "worktrees" / variant_id
    (workspace / "unrecorded_extra.py").write_text("print('extra')\n", encoding="utf-8")

    result = VariantService(layout).pack(quest_id="QVAR", variant_id=variant_id)

    assert result["ok"] is False
    assert result["error_type"] == "patch_drift"
    assert result["unrecorded_paths"] == ["unrecorded_extra.py"]


def test_variant_pack_blocks_staged_tracked_drift_after_check(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant(tmp_path)
    assert VariantService(layout).check(quest_id="QVAR", variant_id=variant_id)["ok"] is True
    workspace = tmp_path / "CodexScientist" / "quests" / "QVAR" / "runtime" / "worktrees" / variant_id
    (workspace / "train.py").write_text("print('staged drift')\n", encoding="utf-8")
    _run(["git", "add", "train.py"], workspace)

    result = VariantService(layout).pack(quest_id="QVAR", variant_id=variant_id)

    assert result["ok"] is False
    assert result["error_type"] == "patch_drift"


def test_variant_pack_blocks_staged_new_file_after_check(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout, _trajectory_id, variant_id = _created_variant(tmp_path)
    assert VariantService(layout).check(quest_id="QVAR", variant_id=variant_id)["ok"] is True
    workspace = tmp_path / "CodexScientist" / "quests" / "QVAR" / "runtime" / "worktrees" / variant_id
    (workspace / "staged_extra.py").write_text("print('extra')\n", encoding="utf-8")
    _run(["git", "add", "staged_extra.py"], workspace)

    result = VariantService(layout).pack(quest_id="QVAR", variant_id=variant_id)

    assert result["ok"] is False
    assert result["error_type"] == "patch_drift"


def test_variant_apply_patch_blocks_preexisting_staged_nonmutable_drift(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = _manifest(tmp_path, git_repo=True)
    repo = tmp_path / "repo"
    (repo / "config.yaml").write_text("value: 1\n", encoding="utf-8")
    _run(["git", "add", "config.yaml"], repo)
    _run(["git", "-c", "user.name=CodexScientist", "-c", "user.email=codexscientist@example.invalid", "commit", "-m", "add config"], repo)
    manifest["baseline"]["commit"] = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    assert EnvironmentService(layout).register(quest_id="QVAR", manifest=manifest)["ok"] is True
    trajectory_id = TrajectoryStore(layout).create(quest_id="QVAR", env_id="env_variant", idea={"idea_id": "idea_variant", "title": "Variant idea"})["trajectory_id"]
    created = VariantService(layout).create(quest_id="QVAR", env_id="env_variant", trajectory_id=trajectory_id, idea_id="idea_variant")
    assert created["ok"] is True
    workspace = Path(created["workspace_path"])
    (workspace / "config.yaml").write_text("value: drift\n", encoding="utf-8")
    _run(["git", "add", "config.yaml"], workspace)
    patch_path = tmp_path / "change.diff"
    _write_patch(patch_path)

    result = VariantService(layout).apply_patch(quest_id="QVAR", variant_id=created["variant_id"], patch_path=str(patch_path))

    assert result["ok"] is False
    assert result["error_type"] == "readonly_or_eval_changed"
    assert "config.yaml" in result["blocked_paths"]


def test_variant_check_failure_updates_trajectory_failure(tmp_path: Path):
    from codex_scientist.services.variant import VariantService

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = _manifest(tmp_path, git_repo=True)
    manifest["commands"]["smoke"] = [["python", "-c", "import module_that_should_not_exist_123"]]
    assert EnvironmentService(layout).register(quest_id="QVAR", manifest=manifest)["ok"] is True
    trajectory_id = TrajectoryStore(layout).create(quest_id="QVAR", env_id="env_variant", idea={"idea_id": "idea_variant", "title": "Variant idea"})["trajectory_id"]
    created = VariantService(layout).create(quest_id="QVAR", env_id="env_variant", trajectory_id=trajectory_id, idea_id="idea_variant")
    assert created["ok"] is True

    result = VariantService(layout).check(quest_id="QVAR", variant_id=created["variant_id"])

    assert result["ok"] is False
    assert result["error_type"] == "import_fail"
    trajectory = json.loads((tmp_path / "CodexScientist" / "quests" / "QVAR" / "trajectories" / f"{trajectory_id}.json").read_text(encoding="utf-8"))
    assert trajectory["result"]["status"] == "failed"
    assert trajectory["failure"]["class"] == "import_fail"
