from __future__ import annotations

import importlib
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_state_dirs_are_not_repository_source_or_hidden():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/CodexScientist/" not in gitignore
    assert "/DeepScientist/" not in gitignore

    tracked = subprocess.check_output(
        ["git", "ls-files", "CodexScientist", "DeepScientist"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    assert tracked == []
    assert not (ROOT / "CodexScientist").exists()
    assert not (ROOT / "DeepScientist").exists()


def test_plugin_doctor_does_not_create_repository_runtime_state():
    assert not (ROOT / "CodexScientist").exists()
    assert not (ROOT / "DeepScientist").exists()

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "csctl.py"), "doctor", "--format", "json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert not (ROOT / "CodexScientist").exists()
    assert not (ROOT / "DeepScientist").exists()


def test_runtime_source_lives_under_main_plugin_package():
    assert not (ROOT / "codexscientist_native").exists()
    assert (ROOT / "codex_scientist" / "runtime" / "__init__.py").exists()
    assert (ROOT / "codex_scientist" / "runtime" / "resources").is_dir()
    assert (ROOT / "codex_scientist" / "runtime" / "vendor").is_dir()

    runtime = importlib.import_module("codex_scientist.runtime")
    assert runtime.__name__ == "codex_scientist.runtime"


def test_root_pyproject_declares_minimal_project_metadata():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["build-system"]["build-backend"] == "hatchling.build"
    project = data["project"]
    assert project["name"] == "codex-scientist"
    assert project["version"]
    assert project["requires-python"].startswith(">=3.")

    deps = data["project"].get("dependencies", [])
    assert any(dep.lower().startswith("pyyaml") for dep in deps)

    dev_deps = data["project"]["optional-dependencies"]["dev"]
    assert any(dep.startswith("pytest") for dep in dev_deps)
    assert any(dep.startswith("vulture") for dep in dev_deps)
    assert data["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]


def test_ci_workflow_installs_project_with_dev_dependencies():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert 'python -m pip install -e ".[dev]"' in workflow
    assert "python -m pip install pytest vulture" not in workflow


def test_repository_layout_doc_names_default_agent_facing_trees():
    layout = (ROOT / "docs" / "REPOSITORY_LAYOUT.md").read_text(encoding="utf-8")
    required = [
        "codex_scientist/services",
        "codex_scientist/mcp",
        "codex_scientist/runtime/vendor",
        "codex_scientist/runtime/resources",
        "skills/",
        "scripts/cs_mcp.py",
        "CodexScientist/",
    ]
    for marker in required:
        assert marker in layout
    assert "scripts/csctl.py" not in layout
    assert "CLI fallback" not in layout

    admin_cli = (ROOT / "docs" / "ADMIN_CLI.md").read_text(encoding="utf-8")
    assert "scripts/csctl.py" in admin_cli
    assert "not part of the default agent research path" in admin_cli


def test_ci_workflow_runs_core_local_validation_gates():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for marker in [
        "python -m pytest -q",
        "python -m vulture codex_scientist scripts tests --min-confidence 100",
        "python -m compileall -q codex_scientist scripts tests",
        "scripts/cs_mcp.py --stdio-smoke tools/list",
    ]:
        assert marker in workflow
