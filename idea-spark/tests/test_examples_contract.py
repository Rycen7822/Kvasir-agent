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


def test_delegate_task_template_is_valid_and_mentions_idea_spark_toolset():
    data = json.loads(read_text("examples/delegate_task_template.json"))

    assert data["toolsets"] == ["idea_spark"]
    assert "room_id" in data["context"]
    assert "idea_spark_room_join" in data["goal"]
