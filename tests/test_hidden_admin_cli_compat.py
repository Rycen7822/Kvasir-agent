from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from kvasir_agent.mcp import surface_allowlist

ROOT = Path(__file__).resolve().parents[1]


def test_hidden_admin_cli_paths_are_explicitly_allowlisted():
    allowed = {str(path) for path in surface_allowlist.allowed_cli_reference_paths()}
    expected = {
        "scripts/kactl.py",
        "scripts/ka_native_cli.py",
        "docs/ADMIN_CLI.md",
    }
    assert expected <= allowed


def test_admin_cli_remains_available_for_human_debug_and_ci():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "kactl.py"), "doctor", "--format", "json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
