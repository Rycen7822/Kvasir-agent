from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _run(script: str, *args: str) -> dict:
    proc = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / script), *args],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(proc.stdout)


def test_doctor_accepts_legacy_json_output_flag_for_final_acceptance_commands():
    for script in ["csctl.py", "csctl.py"]:
        payload = _run(script, "doctor", "--json")
        assert payload["ok"] is True
        assert payload["transport"] == "codex-native-cli"
        assert payload["mcp"] is False


def test_csctl_accepts_legacy_project_and_json_flags_after_subcommand(tmp_path: Path):
    init = _run("csctl.py", "manifest", "init", "--project", str(tmp_path), "--name", "Demo", "--goal", "Improve", "--json")
    assert init["ok"] is True

    validate = _run("csctl.py", "manifest", "validate", "--project", str(tmp_path), "--json")
    assert validate["ok"] is True

    runner = _run("csctl.py", "runner", "start", "--project", str(tmp_path), "--command", "python train.py", "--dry-run", "--json")
    assert runner["ok"] is True
    assert runner["run"]["status"] == "dry_run"
