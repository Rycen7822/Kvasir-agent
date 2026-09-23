from __future__ import annotations

from pathlib import Path

from kvasir_agent.mcp.context import KvasirAgentMcpContext
from kvasir_agent.mcp.tool_registry import call_tool, tools_list_payload
from kvasir_agent.profiles import DEFAULT_PROFILE_NAME, PROFILES

REQUIRED_EVIDENCE_TOOLS = {
    "ka_research_read", "ka_record_user_requirement", "ka_baseline", "ka_method_record",
    "ka_record_main_experiment", "ka_analysis", "ka_checkpoint", "ka_environment",
}

FORBIDDEN = ("scripts/kactl.py", "CLI fallback")


def _names(payload: dict) -> set[str]:
    assert payload["ok"] is True, payload
    return {tool["name"] for tool in payload["tools"]}


def test_mcp_context_reads_goal_environment(monkeypatch, tmp_path: Path):
    quest_root = tmp_path / "Kvasir-agent" / "quests" / "Q1"
    monkeypatch.setenv("KVASIR_AGENT_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("KA_HOME", str(tmp_path / "Kvasir-agent"))
    monkeypatch.setenv("KA_QUEST_ID", "Q1")
    monkeypatch.setenv("KA_QUEST_ROOT", str(quest_root))
    monkeypatch.setenv("KA_RUN_ID", "R0001")
    monkeypatch.setenv("KA_ACTIVE_STAGE", "experiment")
    monkeypatch.setenv("KA_CONVERSATION_ID", "conv-1")
    monkeypatch.setenv("KA_WORKTREE_ROOT", str(tmp_path / "worktree"))

    context = KvasirAgentMcpContext.from_env()

    assert context.require_project_root() == tmp_path
    assert context.quest_id == "Q1"
    assert context.require_quest_root() == tmp_path / "Kvasir-agent"
    assert context.run_id == "R0001"
    assert context.active_stage == "experiment"
    assert context.conversation_id == "conv-1"
    assert context.worktree_root == tmp_path / "worktree"
    assert context.resolve_project_layout().state_root == tmp_path / "Kvasir-agent"


def test_goal_profile_is_deprecated_evidence_alias_and_cli_free():
    assert DEFAULT_PROFILE_NAME == "core"
    assert "goal" in PROFILES
    assert PROFILES["goal"].deprecated
    assert "all" not in PROFILES or not PROFILES["all"].registers_mcp

    payload = tools_list_payload({"profile": "goal"})
    names = _names(payload)

    assert REQUIRED_EVIDENCE_TOOLS.issubset(names)
    assert "ka_goal_context" not in names
    assert "ka_queue_submit" not in names
    assert "ka_runner_start" not in names
    assert "ka_trial_propose" not in names
    assert len(names) < 48
    assert any("profile_deprecated" in warning for warning in payload["warnings"])
    for tool in payload["tools"]:
        assert tool["name"].startswith("ka_")
        assert tool["description"]
        assert set(tool["annotations"]) == {
            "readOnlyHint",
            "destructiveHint",
            "idempotentHint",
            "openWorldHint",
        }
        combined = f"{tool['name']}\n{tool['description']}"
        for forbidden in FORBIDDEN:
            assert forbidden not in combined


def test_tools_list_supplies_callable_schema_without_lazy_lookup():
    from jsonschema import Draft202012Validator

    listed = tools_list_payload({"profile": "goal"})
    card = next(tool for tool in listed["tools"] if tool["name"] == "ka_method_record")
    schema = card["inputSchema"]
    assert "quest_id" not in schema["properties"]
    validator = Draft202012Validator(schema)
    missing_contract = {"project": "/research", "operation": "idea", "title": "Idea"}
    assert not validator.is_valid(missing_contract)
    assert validator.is_valid({**missing_contract, "novelty_contract": {
        "mechanism": "Mechanism", "related_work_refs": ["paper"], "expected_difference": "Difference",
    }})
    # Offline schema inspection agrees with the advertised aggregate schema.
    assert call_tool("ka_tool_schema", {"name": "ka_method_record"})["schema"]["input_schema"] == schema


def test_goal_stage_label_does_not_filter_tools():
    goal = tools_list_payload({"profile": "goal"})
    analysis = tools_list_payload({"profile": "goal", "stage": "analysis"})

    assert _names(analysis) == _names(goal)
    assert analysis["stage_label"] == "analysis"
    assert "stage_label_not_used_for_tool_filtering" in analysis["warnings"]
    assert "ka_goal_context" not in _names(analysis)
    assert "ka_paper_fetch" not in _names(analysis)
