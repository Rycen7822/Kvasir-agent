from __future__ import annotations

import importlib
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_state_dirs_are_not_repository_source_or_hidden():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/Kvasir-agent/" not in gitignore
    assert "/DeepScientist/" not in gitignore

    tracked = subprocess.check_output(
        ["git", "ls-files", "Kvasir-agent", "DeepScientist"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    assert tracked == []
    assert not (ROOT / "Kvasir-agent").exists()
    assert not (ROOT / "DeepScientist").exists()


def test_runtime_source_lives_under_main_plugin_package():
    assert not (ROOT / "kvasiragent_native").exists()
    assert (ROOT / "kvasir_agent" / "runtime" / "__init__.py").exists()
    assert (ROOT / "kvasir_agent" / "runtime" / "resources").is_dir()
    assert (ROOT / "kvasir_agent" / "runtime" / "vendor").is_dir()

    runtime = importlib.import_module("kvasir_agent.runtime")
    assert runtime.__name__ == "kvasir_agent.runtime"


def test_root_pyproject_declares_minimal_project_metadata():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["build-system"]["build-backend"] == "hatchling.build"
    project = data["project"]
    assert project["name"] == "kvasir-agent"
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
