from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "skills" / "kvasir-agent" / "SKILL.md"


def test_codex_router_skill_stays_thin_and_points_to_recovery_tools():
    text = ROUTER.read_text(encoding="utf-8")
    lower = text.lower()

    assert len(text) < 6000
    assert "ka_skill_search" not in text
    assert "ka_skill_load" not in text
    assert "ka_research_read" in text
    assert "ka_research_read" in text
    assert "ka_checkpoint" in text
    assert "ka_log_digest" in text
    assert "ka_artifact_index" in text
    assert "Load at most one stage/support skill" not in text
    assert "allow_full=true" not in text
    assert "native skill mechanism" in text
    assert "without loading full logs" in lower
    assert "Codex owns" in text
    assert "scientific validity" in text
    assert text.count("```") <= 2


def test_codex_router_skill_frontmatter_remains_valid_and_bounded():
    text = ROUTER.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter = text.split("---\n", 2)[1]
    assert "name: kvasir-agent" in frontmatter
    description = next(line for line in frontmatter.splitlines() if line.startswith("description:"))
    assert len(description.split(":", 1)[1].strip()) <= 1024


def test_public_skills_do_not_advertise_hidden_tool_families_by_default():
    forbidden_phrases = [
        "queues, trials",
        "wiki/frontier records",
        "Kvasir-agent/config/hermes-native.yaml",
    ]
    forbidden_concept_words = {"wiki", "trial", "trials"}
    offenders: list[str] = []
    for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        for phrase in forbidden_phrases:
            if phrase in text:
                offenders.append(f"{path.relative_to(ROOT)} contains {phrase}")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if any(re.search(rf"\b{re.escape(word)}\b", line, flags=re.IGNORECASE) for word in forbidden_concept_words):
                offenders.append(f"{path.relative_to(ROOT)}:{line_no}: {line.strip()}")
    assert offenders == []
