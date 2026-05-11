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


def test_baseline_confirm_and_trial_cli_reaches_ready(tmp_path: Path):
    run_csctl("manifest", "init", "--name", "Demo", "--goal", "Improve", "--format", "json", project_root=tmp_path)

    baseline = run_csctl("baseline", "confirm", "--id", "b1", "--metric-contract", "primary", "--format", "json", project_root=tmp_path)
    assert baseline["ok"] is True
    assert baseline["baseline"]["status"] == "confirmed"

    baseline_show = run_csctl("baseline", "show", "--format", "json", project_root=tmp_path)
    assert baseline_show["baseline_ready"] is True

    proposed = run_csctl(
        "trial",
        "propose",
        "--quest-id",
        "q1",
        "--idea-id",
        "i1",
        "--hypothesis",
        "h",
        "--mechanism",
        "m",
        "--format",
        "json",
        project_root=tmp_path,
    )
    assert proposed["trial"]["trial_id"] == "T0001"
    assert proposed["trial"]["status"] == "proposed"

    planned = run_csctl("trial", "plan", "T0001", "--metric-contract", "primary", "--novelty", "allow", "--format", "json", project_root=tmp_path)
    assert planned["trial"]["status"] == "planned"

    ready = run_csctl("trial", "ready", "T0001", "--format", "json", project_root=tmp_path)
    assert ready["ok"] is True
    assert ready["trial"]["status"] == "ready"

    shown = run_csctl("trial", "show", "T0001", "--format", "json", project_root=tmp_path)
    assert shown["trial"]["status"] == "ready"


def test_baseline_waive_makes_manifest_baseline_ready(tmp_path: Path):
    run_csctl("manifest", "init", "--name", "Demo", "--goal", "Improve", "--format", "json", project_root=tmp_path)

    waived = run_csctl("baseline", "waive", "--id", "w1", "--reason", "No comparable baseline for smoke", "--format", "json", project_root=tmp_path)
    assert waived["ok"] is True
    assert waived["baseline"]["status"] == "waived"
    assert waived["baseline"]["waiver_reason"] == "No comparable baseline for smoke"

    validate = run_csctl("manifest", "validate", "--format", "json", project_root=tmp_path)
    assert validate["ok"] is True
    assert validate["baseline_ready"] is True
