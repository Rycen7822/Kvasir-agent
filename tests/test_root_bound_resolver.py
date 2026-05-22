from __future__ import annotations

from pathlib import Path

import pytest

from codex_scientist.services.project_state import ProjectRootResolver


def test_project_root_resolver_explicit_project_wins_over_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    cwd_repo = tmp_path / "cwd_repo" / "src" / "pkg"
    cwd_repo.mkdir(parents=True)
    (tmp_path / "cwd_repo" / ".git").mkdir()
    monkeypatch.chdir(cwd_repo)

    resolved = ProjectRootResolver.resolve({"project": str(explicit)})

    assert resolved == explicit.resolve()


def test_project_root_resolver_env_used_only_without_explicit_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    explicit = tmp_path / "explicit"
    env_root = tmp_path / "env_root"
    explicit.mkdir()
    env_root.mkdir()
    monkeypatch.setenv("CODEXSCIENTIST_PROJECT_ROOT", str(env_root))

    assert ProjectRootResolver.resolve({}) == env_root.resolve()
    assert ProjectRootResolver.resolve({"project_root": str(explicit)}) == explicit.resolve()


def test_project_root_resolver_prefers_nearest_research_manifest_over_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    nested_project = repo / "experiments" / "run1"
    cwd = nested_project / "src"
    cwd.mkdir(parents=True)
    (repo / ".git").mkdir()
    state_root = nested_project / "CodexScientist"
    state_root.mkdir()
    (state_root / "research.yaml").write_text("schema_version: 2\nlayout_mode: root_bound\n", encoding="utf-8")
    monkeypatch.chdir(cwd)

    assert ProjectRootResolver.resolve({}) == nested_project.resolve()


def test_project_root_resolver_falls_back_to_nearest_git_then_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    cwd = repo / "src" / "pkg"
    cwd.mkdir(parents=True)
    (repo / ".git").mkdir()
    monkeypatch.chdir(cwd)
    assert ProjectRootResolver.resolve({}) == repo.resolve()

    fresh = tmp_path / "fresh"
    fresh.mkdir()
    monkeypatch.chdir(fresh)
    monkeypatch.setattr(ProjectRootResolver, "_nearest_parent_with", staticmethod(lambda start, relative: None))
    assert ProjectRootResolver.resolve({}) == fresh.resolve()


def test_project_root_resolver_rejects_empty_and_unsafe_explicit_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ProjectRootResolver.resolve({"project": ""})
    with pytest.raises(ValueError):
        ProjectRootResolver.resolve({"project": str(tmp_path / "missing" / "..")})
