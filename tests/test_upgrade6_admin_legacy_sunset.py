from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from codex_scientist.runtime import schemas

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_legacy_alias_not_in_public_schema_or_default_native_call(tmp_path: Path):
    public_names = {schema["name"] for schema in schemas.PUBLIC_SCHEMAS}
    assert not any(name.startswith("codexscientist_") for name in public_names)

    completed = subprocess.run(
        [
            PYTHON,
            str(ROOT / "scripts" / "cs_native_cli.py"),
            "--project-root",
            str(tmp_path),
            "--format",
            "json",
            "call",
            "codexscientist_doctor",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode != 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload.get("ok") is False, payload
    assert payload.get("error_type") in {"legacy_alias_disabled", "unknown_tool"}, payload
    assert payload.get("canonical_tool") in {None, "cs_doctor"}


def test_csctl_admin_only_not_referenced_by_agent_docs():
    targets = [
        ROOT / ".codex-plugin" / "plugin.json",
        ROOT / "README.md",
        ROOT / "docs" / "USAGE.md",
        ROOT / "skills" / "codexscientist-codex" / "SKILL.md",
    ]
    forbidden = (
        "scripts/csctl.py",
        "queue submit",
        "runner start",
        "trial propose",
        " soak",
        " cost",
    )

    violations: list[tuple[str, str]] = []
    for path in targets:
        text = path.read_text(encoding="utf-8", errors="replace")
        lowered = text.lower()
        for term in forbidden:
            if term.lower() in lowered:
                violations.append((str(path.relative_to(ROOT)), term.strip()))

    assert violations == []
