from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / "docs" / "ARCHITECTURE.md"
MCP = ROOT / "docs" / "MCP.md"
ROUTER = ROOT / "skills" / "kvasir-agent" / "SKILL.md"
EGR = ROOT / "docs" / "EXECUTION_GROUNDED_RESEARCH.md"


def test_execution_grounded_research_doc_exists_and_lists_forbidden_aar_patterns():
    text = EGR.read_text(encoding="utf-8")
    for required in (
        "ResearchEnvironment",
        "FeedbackIngest",
        "TrajectoryStore",
        "EvolutionaryRoundPlan",
        "Do not treat W&B or output.log as primary metric truth",
        "Do not expose executor tools in the default MCP surface",
    ):
        assert required in text
