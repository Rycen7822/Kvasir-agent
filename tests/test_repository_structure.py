from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_state_dirs_are_ignored_and_not_tracked():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/CodexScientist/" in gitignore
    assert "/DeepScientist/" in gitignore

    tracked = subprocess.check_output(
        ["git", "ls-files", "CodexScientist", "DeepScientist"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    assert tracked == []


def test_root_pyproject_declares_minimal_project_metadata():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["build-system"]["build-backend"] == "hatchling.build"
    project = data["project"]
    assert project["name"] == "codex-scientist"
    assert project["version"]
    assert project["requires-python"].startswith(">=3.")

    dev_deps = data["project"]["optional-dependencies"]["dev"]
    assert any(dep.startswith("pytest") for dep in dev_deps)
    assert any(dep.startswith("vulture") for dep in dev_deps)
    assert data["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]


def test_repository_layout_doc_names_canonical_trees():
    layout = (ROOT / "docs" / "REPOSITORY_LAYOUT.md").read_text(encoding="utf-8")
    required = [
        "codex_scientist/services",
        "codex_scientist/mcp",
        "codexscientist_native/vendor",
        "codexscientist_native/resources",
        "skills/",
        "scripts/cs_mcp.py",
        "scripts/csctl.py",
        "CodexScientist/",
    ]
    for marker in required:
        assert marker in layout


def test_ci_workflow_runs_core_local_validation_gates():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for marker in [
        "python -m pytest -q",
        "python -m vulture codex_scientist codexscientist_native scripts tests --min-confidence 100",
        "python -m compileall -q codex_scientist codexscientist_native scripts tests",
        "scripts/cs_mcp.py --stdio-smoke tools/list",
    ]:
        assert marker in workflow
