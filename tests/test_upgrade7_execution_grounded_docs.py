from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / "docs" / "ARCHITECTURE.md"
MCP = ROOT / "docs" / "MCP.md"
ROUTER = ROOT / "skills" / "kvasir-agent" / "SKILL.md"
EGR = ROOT / "docs" / "EXECUTION_GROUNDED_RESEARCH.md"


def test_architecture_documents_execution_grounded_boundary():
    text = ARCH.read_text(encoding="utf-8")
    assert "## Execution-grounded extension boundary" in text
    assert "execution-grounded" in text
    assert "default `copilot`" in text
    assert "does not automatically invent, implement, schedule, or execute ideas" in text
    assert "explicit user request or manifest" in text


def test_mcp_documents_execution_planning_and_executor_profiles():
    text = MCP.read_text(encoding="utf-8")
    assert "execution_planning" in text
    assert "executor_local" in text
    assert "KVASIR_AGENT_ENABLE_EXECUTOR_MCP=1" in text
    assert "ka_evolutionary_plan_round" in (ROOT / "docs/TOOL_MIGRATION.md").read_text()
    assert "ka_variant_create" in text
    assert "not registered by default" in text


def test_codex_router_documents_execution_grounded_gate():
    text = ROUTER.read_text(encoding="utf-8")
    assert "Autonomous idea improvement" in text
    assert "explicit user request" in text
    assert "Executor tools require explicit authorization" in text
    assert "environment/manifest gates" in text


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
