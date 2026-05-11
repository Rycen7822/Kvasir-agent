from __future__ import annotations

import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PLUGIN_ROOT / "skills"

FORBIDDEN_ACTIVE_SKILL_PATTERNS = [
    re.compile(r"artifact\.[A-Za-z_]"),
    re.compile(r"memory\.[A-Za-z_]"),
    re.compile(r"bash_exec\(mode\s*="),
    re.compile(r"所有 shell"),
    re.compile(r"All shell", re.IGNORECASE),
    re.compile(r"every shell", re.IGNORECASE),
    re.compile(r"must go through backend", re.IGNORECASE),
]


def test_active_skill_files_are_compact_and_free_of_legacy_tool_surface():
    offenders: list[str] = []
    oversized: list[str] = []
    for path in sorted(SKILLS_ROOT.rglob("SKILL.md")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(PLUGIN_ROOT)
        for pattern in FORBIDDEN_ACTIVE_SKILL_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{rel}: {pattern.pattern}")
        if len(text) > 12000:
            oversized.append(f"{rel}: {len(text)} chars")
    assert offenders == []
    assert oversized == []


def test_legacy_long_playbooks_are_preserved_as_references_not_active_prompts():
    legacy_refs = sorted(SKILLS_ROOT.glob("*/references/legacy-playbook.md"))
    assert legacy_refs, "expected long playbooks with legacy wording to be moved into references/"
    for path in legacy_refs[:5]:
        text = path.read_text(encoding="utf-8")
        assert "Legacy playbook" in text
        assert "Do not execute old API names directly" in text
