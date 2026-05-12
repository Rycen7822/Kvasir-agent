from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_csctl(*args: str) -> dict:
    completed = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "csctl.py"), *args],
        cwd=PLUGIN_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(completed.stdout)


def test_canonical_runtime_package_is_codexscientist_native():
    import codexscientist_native.schemas as schemas
    import codexscientist_native.tools as tools

    public_names = [schema["name"] for schema in schemas.PUBLIC_SCHEMAS]
    assert public_names
    assert all(name.startswith("cs_") for name in public_names)
    assert not any(name.startswith("d" + "s_") or name.startswith("codexscientist_") for name in public_names)
    assert hasattr(tools, "cs_doctor")
    assert not hasattr(tools, "d" + "s_doctor")


def test_default_cli_surface_is_cs_not_legacy_or_codexscientist():
    payload = run_csctl("list-tools", "--json")
    names = [tool["name"] for tool in payload["tools"]]
    assert payload["ok"] is True
    assert names
    assert all(name.startswith("cs_") for name in names)
    assert not any(name.startswith("d" + "s_") or name.startswith("codexscientist_") for name in names)
    assert payload["transport"] == "codex-native-cli"


def test_legacy_csctl_file_is_not_the_default_entrypoint():
    assert (PLUGIN_ROOT / "scripts" / "csctl.py").exists()
    legacy_entrypoint = "d" + "sctl.py"
    assert not (PLUGIN_ROOT / "scripts" / legacy_entrypoint).exists()
