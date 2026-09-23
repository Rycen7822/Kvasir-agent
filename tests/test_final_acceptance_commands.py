from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(script: str, *args: str, cwd: Path | None = None) -> dict:
    proc = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / script), *args],
        cwd=str(cwd or PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(proc.stdout)


def test_planned_final_acceptance_command_group_works_with_legacy_flags(tmp_path: Path):
    run("kactl.py", "doctor", "--json")
    run("kactl.py", "doctor", "--json")
    run("kactl.py", "manifest", "init", "--project", str(tmp_path), "--name", "Demo", "--goal", "Improve", "--json")

    assert run("kactl.py", "manifest", "validate", "--project", str(tmp_path), "--json")["ok"] is True
    assert run("kactl.py", "runner", "start", "--project", str(tmp_path), "--dry-run", "--json")["ok"] is True
    assert run("kactl.py", "queue", "status", "--project", str(tmp_path), "--json")["ok"] is True
    assert run("kactl.py", "wiki", "query-pack", "--project", str(tmp_path), "--limit", "20", "--json")["ok"] is True
    assert run("kactl.py", "review", "status", "--project", str(tmp_path), "--json")["ok"] is True
    assert run("kactl.py", "cost", "status", "--project", str(tmp_path), "--json")["ok"] is True
