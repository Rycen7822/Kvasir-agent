from __future__ import annotations

from pathlib import Path

from codex_scientist.mcp.context import CodexScientistMcpContext
from codex_scientist.mcp.tool_registry import call_tool, tools_list_payload
from codex_scientist.profiles import DEFAULT_PROFILE_NAME, PROFILES

REQUIRED_GOAL_TOOLS = {
    "cs_goal_context",
    "cs_tool_schema",
    "cs_new_quest",
    "cs_record_user_requirement",
    "cs_create_local_baseline",
    "cs_confirm_baseline",
    "cs_submit_idea",
    "cs_record_main_experiment",
    "cs_create_analysis_campaign",
    "cs_record_analysis_slice",
    "cs_get_method_scoreboard",
    "cs_get_optimization_frontier",
    "cs_checkpoint",
    "cs_resume_brief",
    "cs_manifest_init",
    "cs_manifest_validate",
    "cs_queue_submit",
    "cs_queue_status",
    "cs_runner_start",
    "cs_runner_status",
    "cs_trial_propose",
    "cs_trial_plan",
    "cs_trial_show",
}

FORBIDDEN = ("scripts/csctl.py", "CLI fallback")


def test_mcp_context_reads_goal_environment(monkeypatch, tmp_path: Path):
    quest_root = tmp_path / "CodexScientist" / "quests" / "Q1"
    monkeypatch.setenv("CODEXSCIENTIST_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("CS_HOME", str(tmp_path / "CodexScientist"))
    monkeypatch.setenv("CS_QUEST_ID", "Q1")
    monkeypatch.setenv("CS_QUEST_ROOT", str(quest_root))
    monkeypatch.setenv("CS_RUN_ID", "R0001")
    monkeypatch.setenv("CS_ACTIVE_STAGE", "experiment")
    monkeypatch.setenv("CS_CONVERSATION_ID", "conv-1")
    monkeypatch.setenv("CS_WORKTREE_ROOT", str(tmp_path / "worktree"))

    context = CodexScientistMcpContext.from_env()

    assert context.require_project_root() == tmp_path
    assert context.quest_id == "Q1"
    assert context.require_quest_root() == quest_root
    assert context.run_id == "R0001"
    assert context.active_stage == "experiment"
    assert context.conversation_id == "conv-1"
    assert context.worktree_root == tmp_path / "worktree"
    assert context.resolve_project_layout().state_root == tmp_path / "CodexScientist"


def test_goal_profile_tools_are_explicit_annotated_and_cli_free():
    assert DEFAULT_PROFILE_NAME == "core"
    assert "goal" in PROFILES
    assert "all" not in PROFILES or not PROFILES["all"].registers_mcp

    payload = tools_list_payload({"profile": "goal"})
    names = {tool["name"] for tool in payload["tools"]}

    assert REQUIRED_GOAL_TOOLS.issubset(names)
    assert len(names) < 48
    for tool in payload["tools"]:
        assert tool["name"].startswith("cs_")
        assert tool["group"]
        assert isinstance(tool["required_context_keys"], list)
        assert set(tool["annotations"]) == {
            "readOnlyHint",
            "destructiveHint",
            "idempotentHint",
            "openWorldHint",
        }
        combined = f"{tool['name']}\n{tool['description']}"
        for forbidden in FORBIDDEN:
            assert forbidden not in combined


def test_tools_list_is_compact_and_schema_is_lazy():
    listed = tools_list_payload({"profile": "goal"})
    submit_card = next(tool for tool in listed["tools"] if tool["name"] == "cs_submit_idea")

    assert submit_card["inputSchema"] == {"type": "object", "additionalProperties": True}
    assert "properties" not in submit_card["inputSchema"]

    schema = call_tool("cs_tool_schema", {"name": "cs_submit_idea"})
    assert schema["ok"] is True
    assert schema["schema"]["name"] == "cs_submit_idea"
    assert "properties" in schema["schema"]["input_schema"]
    assert "title" in schema["schema"]["input_schema"]["properties"]


def test_goal_stage_subset_filters_heavy_tools():
    analysis = tools_list_payload({"profile": "goal", "stage": "analysis"})
    names = {tool["name"] for tool in analysis["tools"]}

    assert "cs_goal_context" in names
    assert "cs_create_analysis_campaign" in names
    assert "cs_record_analysis_slice" in names
    assert "cs_paper_fetch" not in names
    assert len(names) < 24

    context = call_tool("cs_goal_context", {"active_stage": "analysis"})
    assert context["ok"] is True
    assert "cs_create_analysis_campaign" in context["allowed_tools_for_stage"]
    assert "cs_paper_fetch" not in context["allowed_tools_for_stage"]
