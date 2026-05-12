from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from codex_scientist.mcp import surface_allowlist
from codex_scientist.mcp.skill_index import load_skill

ROOT = Path(__file__).resolve().parents[1]


def test_hidden_admin_cli_paths_are_explicitly_allowlisted():
    allowed = {str(path) for path in surface_allowlist.allowed_cli_reference_paths()}
    expected = {
        "scripts/csctl.py",
        "scripts/cs_native_cli.py",
        "docs/ADMIN_CLI.md",
    }
    assert expected <= allowed


def test_admin_cli_remains_available_for_human_debug_and_ci():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "csctl.py"), "doctor", "--format", "json"],
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


def test_admin_skill_view_marks_cli_material_non_agent_facing():
    payload = load_skill({"skill_id": "codexscientist-codex", "view": "admin", "max_chars": 16000})
    assert payload["ok"] is True
    assert payload["view"] == "admin"
    assert payload["agent_facing"] is False
    assert "scripts/csctl.py" in payload["content"]
    assert "not part of the default agent research path" in payload["content"]


def test_runtime_skill_view_does_not_load_admin_cli_material():
    payload = load_skill({"skill_id": "codexscientist-codex", "view": "runtime", "max_chars": 16000})
    assert payload["ok"] is True
    assert payload.get("agent_facing") is not False
    assert "scripts/csctl.py" not in payload["content"]
    assert "CLI fallback" not in payload["content"]
