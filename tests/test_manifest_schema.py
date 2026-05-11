from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_csctl(*args: str, project_root: Path) -> dict:
    proc = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "csctl.py"), "--project-root", str(project_root), *args],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(proc.stdout)


def test_manifest_init_validate_show_cli_creates_project_local_research_yaml(tmp_path: Path):
    init_payload = run_csctl("manifest", "init", "--name", "Demo", "--goal", "Improve result", "--format", "json", project_root=tmp_path)

    manifest_path = tmp_path / "DeepScientist" / "research.yaml"
    assert init_payload["ok"] is True
    assert init_payload["path"] == str(manifest_path)
    assert manifest_path.exists()

    validate_payload = run_csctl("manifest", "validate", "--format", "json", project_root=tmp_path)
    assert validate_payload["ok"] is True
    assert validate_payload["manifest"]["autonomy"]["mode"] == "copilot"
    assert validate_payload["baseline_ready"] is False
    assert validate_payload["errors"] == []

    show_payload = run_csctl("manifest", "show", "--format", "json", project_root=tmp_path)
    assert show_payload["ok"] is True
    assert show_payload["manifest"]["project"]["name"] == "Demo"
    assert show_payload["manifest"]["goal"]["title"] == "Improve result"


def test_manifest_validation_rejects_missing_primary_metric(tmp_path: Path):
    from codex_scientist.services.manifest import ManifestService
    from codex_scientist.services.project_state import ProjectLayout

    service = ManifestService(ProjectLayout.from_project_root(tmp_path))
    manifest = service.default_manifest(name="Bad", goal="Missing metric")
    manifest["metrics"].pop("primary")
    service.write(manifest)

    result = service.validate()
    assert result["ok"] is False
    assert "metrics.primary" in result["errors"]
