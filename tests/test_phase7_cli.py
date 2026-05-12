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


def test_migration_and_soak_cli_surface(tmp_path: Path):
    legacy = tmp_path / "CodexScientist" / "quests" / "legacy-001"
    legacy.mkdir(parents=True)
    (legacy / "quest.yaml").write_text("title: Legacy Quest\ngoal: Improve method\n", encoding="utf-8")

    migrated = run_csctl("migrate", "legacy-quests", "--format", "json", project_root=tmp_path)
    assert migrated["migrated_count"] == 1

    soak = run_csctl("soak", "accelerated", "--days", "10", "--inject-failures", "--format", "json", project_root=tmp_path)
    assert soak["accelerated"]["verdict"] == "pass"
    assert soak["wall_clock"]["verdict"] == "not_run"
