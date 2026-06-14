import json
import re
from pathlib import Path

CANONICAL_TOOL_NAMES = {
    "idea_spark_room_create",
    "idea_spark_room_join",
    "idea_spark_room_status",
    "idea_spark_message_post",
    "idea_spark_message_read",
    "idea_spark_round_wait",
    "idea_spark_artifact_create",
    "idea_spark_artifact_read",
    "idea_spark_artifact_link",
    "idea_spark_artifact_status_update",
    "idea_spark_gate_record",
    "idea_spark_need_create",
    "idea_spark_need_update",
    "idea_spark_room_export",
}

README_SECTIONS = [
    "## What Idea-Spark is",
    "## What it is not",
    "## Tool list",
    "## Data model",
    "## Install",
    "## Enable and restart",
    "## Quick smoke test",
    "## Realtime browser dashboard",
    "## Parent protocol",
    "## Child protocol",
    "## Failure modes",
    "## Safety boundary",
    "## Development and tests",
    "## Phase locks",
]


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def test_examples_use_only_canonical_tool_names():
    text = "\n".join(
        [
            read_text("README.md"),
            read_text("examples/ml_idea_review_prompt.md"),
            read_text("examples/delegate_task_template.json"),
        ]
    )
    mentioned = set(re.findall(r"\bidea_spark_[a-z_]+\b", text))

    assert CANONICAL_TOOL_NAMES <= mentioned
    assert mentioned <= CANONICAL_TOOL_NAMES
    assert "idea-spark_" not in text
    assert "old-prefix" not in text


def test_child_protocol_forces_room_join_before_other_actions():
    text = read_text("examples/ml_idea_review_prompt.md")

    join_pos = text.index("idea_spark_room_join")
    for later_tool in ["idea_spark_artifact_create", "idea_spark_message_post", "idea_spark_round_wait"]:
        assert join_pos < text.index(later_tool)


def test_examples_include_gate_decision_before_final_consensus_rule():
    text = read_text("examples/ml_idea_review_prompt.md")

    assert text.index("idea_spark_gate_record") < text.index("Final conclusions require")
    assert "no consensus without GateDecision" in text


def test_readme_documents_restart_or_reset_after_enabling_plugin():
    text = read_text("README.md")

    assert "fresh Hermes process or session reset" in text
    assert "hermes plugins enable idea-spark" in text
    assert "$HERMES_HOME/idea-spark/idea_spark.sqlite3" in text
    assert "IDEA_SPARK_DB" in text
    assert "IDEA_SPARK_EXPORT_DIR" in text


def test_readme_and_bundled_skill_document_realtime_dashboard():
    readme = read_text("README.md")
    skill = read_text("idea_spark/resources/skills/idea-spark-usage/SKILL.md")
    combined = f"{readme}\n{skill}"

    assert "python3 -m idea_spark.dashboard" in combined
    assert "http://127.0.0.1:" in combined
    assert "read-only" in combined.lower()
    assert "EventSource" in combined or "SSE" in combined
    assert "subagent" in combined.lower()
    assert "EN" in combined
    assert "中文" in combined
    assert "local storage" in combined.lower()


def test_bundled_skill_documents_round_based_subagent_work_mode():
    skill = read_text("idea_spark/resources/skills/idea-spark-usage/SKILL.md")

    assert "## Recommended round-based work mode" in skill
    assert "short-lived workers" in skill
    assert "persistent chat-room members" in skill
    assert "Use the Idea-Spark room as the durable shared memory" in skill
    for phase in ["r0/seed", "r1/review", "r2/rebuttal", "r3/gate"]:
        assert phase in skill
    for role in ["PriorArtBreaker", "FeasibilityBreaker", "AuthorAdvocate", "Gatekeeper"]:
        assert role in skill
    for artifact_type in ["Rebuttal", "RevisionPlan", "ScoreCard", "MetaReview"]:
        assert artifact_type in skill
    assert "For live-room readability" in skill
    assert "idea_spark_message_post" in skill
    assert "persistent multi-process runner" in skill


def test_examples_do_not_document_legacy_aliases_or_internal_execution():
    text = "\n".join(
        [
            read_text("README.md"),
            read_text("examples/ml_idea_review_prompt.md"),
            read_text("examples/delegate_task_template.json"),
        ]
    ).lower()

    for forbidden in ["legacy alias", "automatic forwarding", "plugin-internal web", "plugin-internal terminal"]:
        assert forbidden not in text


def test_readme_sections_are_complete_and_ordered():
    text = read_text("README.md")

    positions = [text.index(section) for section in README_SECTIONS]
    assert positions == sorted(positions)


def test_delegate_task_template_is_valid_and_mentions_idea_spark_toolsets():
    data = json.loads(read_text("examples/delegate_task_template.json"))

    assert data["toolsets"] == ["idea_spark", "skills"]
    assert "room_id" in data["context"]
    assert "idea_spark_room_join" in data["goal"]
    assert "skill_view" in data["goal"]
    assert "idea-spark:idea-spark-usage" in data["goal"]


def test_bundled_skill_requires_skills_toolset_for_subagents():
    skill = read_text("idea_spark/resources/skills/idea-spark-usage/SKILL.md")

    assert 'toolsets=["idea_spark", "skills"' in skill
    assert 'skill_view(name="idea-spark:idea-spark-usage")' in skill
    assert "Do not call `skill_manage`" in skill


def test_bundled_skill_documents_discussion_until_gate_controller_contract():
    skill = read_text("idea_spark/resources/skills/idea-spark-usage/SKILL.md")

    required = [
        "discussion-until-gate",
        "Seed / Framing",
        "Novelty Attack",
        "Weakness / Feasibility Attack",
        "Author Rebuttal / Improvement Draft",
        "Re-review / Cross-examination",
        "Gate",
        "has_terminal_gate",
        "Gatekeeper must call idea_spark_gate_record",
        "message-only gate is not final",
        'toolsets=["idea_spark", "skills"]',
        "Do not call `skill_manage`",
    ]
    for text in required:
        assert text in skill


def test_readme_and_prompt_document_discussion_until_gate_without_scheduler_claims():
    readme = read_text("README.md")
    prompt = read_text("examples/ml_idea_review_prompt.md")
    combined = f"{readme}\n{prompt}".lower()

    assert 'toolsets=["idea_spark", "skills"]' in readme
    assert "local management dashboard" in readme
    assert "room_delete_enabled" in readme
    assert "purely read-only" not in readme.lower()
    for phase in [
        "Seed / Framing",
        "Novelty Attack",
        "Weakness / Feasibility Attack",
        "Author Rebuttal / Improvement Draft",
        "Re-review / Cross-examination",
        "Gate",
    ]:
        assert phase in prompt
    assert "message-only gate is not final" in prompt
    for forbidden in ["plugin-internal agent launcher", "auto-spawn on message_post", "persistent child polling"]:
        assert forbidden not in combined


def test_discussion_until_gate_template_is_valid_and_bounded():
    data = json.loads(read_text("examples/discussion_until_gate_template.json"))
    combined = f"{data['goal']}\n{data['context']}"

    assert data["role"] == "orchestrator"
    assert data["toolsets"] == ["idea_spark", "skills"]
    assert "max_rounds=4" in combined
    for phase in [
        "Seed / Framing",
        "Novelty Attack",
        "Weakness / Feasibility Attack",
        "Author Rebuttal / Improvement Draft",
        "Re-review / Cross-examination",
        "Gate",
    ]:
        assert phase in combined
    assert "stop only after has_terminal_gate=true" in combined
    assert "Gatekeeper must call idea_spark_gate_record" in combined
    assert "do not call skill_manage" in combined.lower()
    assert "<ROOM_ID>" in combined
    assert "<IDEA_SUMMARY>" in combined
