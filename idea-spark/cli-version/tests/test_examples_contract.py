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
    "## Default CLI-first mode",
    "## Explicit tool-mode",
    "## Tool list",
    "## Data model",
    "## Install",
    "## Enable and restart",
    "## CLI quick smoke test",
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


def skill_reference_texts():
    base = Path("idea_spark/resources/skills/idea-spark-usage")
    return [read_text(path) for path in sorted((base / "references").glob("*.md"))]


def test_examples_use_only_canonical_tool_names():
    text = "\n".join(
        [
            read_text("README.md"),
            read_text("idea_spark/resources/skills/idea-spark-usage/SKILL.md"),
            *skill_reference_texts(),
            read_text("examples/ml_idea_review_prompt.md"),
            read_text("examples/delegate_task_template.json"),
            read_text("examples/discussion_until_gate_template.json"),
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
    assert "message-only gate is not final" in text


def test_readme_documents_default_cli_first_and_config_gated_tools():
    text = read_text("README.md")

    assert "Default CLI-first mode" in text
    assert "does **not** register the 14 `idea_spark_*` tools by default" in text
    assert "$HERMES_HOME/idea-spark/config.json" in text
    assert "hermes idea-spark config set-tools true" in text
    assert "hermes idea-spark config set-tools false" in text
    assert "fresh Hermes process or session reset" in text
    assert "platform_toolsets" in text
    assert "tools.enabled=true" in text
    assert "hermes plugins enable idea-spark" in text
    assert "$HERMES_HOME/idea-spark/idea_spark.sqlite3" in text
    assert "IDEA_SPARK_DB" in text
    assert "IDEA_SPARK_EXPORT_DIR" in text


def test_readme_and_bundled_skill_document_realtime_dashboard():
    readme = read_text("README.md")
    skill = read_text("idea_spark/resources/skills/idea-spark-usage/SKILL.md")
    cli_dashboard = read_text("idea_spark/resources/skills/idea-spark-usage/references/cli-dashboard.md")
    combined = f"{readme}\n{skill}\n{cli_dashboard}"

    assert "python3 -m idea_spark.dashboard" in combined
    assert "http://127.0.0.1:" in combined
    assert "read-only" in combined.lower()
    assert "EventSource" in combined or "SSE" in combined
    assert "subagent" in combined.lower()
    assert "EN" in combined
    assert "中文" in combined
    assert "local storage" in combined.lower()
    assert "room_delete_enabled" in combined


def test_bundled_skill_documents_round_based_subagent_work_mode():
    skill = read_text("idea_spark/resources/skills/idea-spark-usage/SKILL.md")
    parent_ref = read_text("idea_spark/resources/skills/idea-spark-usage/references/parent-controller.md")
    combined = f"{skill}\n{parent_ref}"

    assert "Thin workflow router" in skill
    assert "**[PARENT-ONLY] Parent/main agent:**" in skill
    assert "**[SUBAGENT-ONLY] Subagent/child agent:**" in skill
    assert "## Role routing — choose exactly one lane first" in skill
    assert "## [PARENT-ONLY] Mandatory phase re-read checkpoint" in skill
    assert "## Hard boundary: [PARENT-ONLY] vs [SUBAGENT-ONLY]" in skill
    assert "Do not follow this section from a subagent prompt" in skill
    for phase in ["r0/seed", "r1/review", "r2/rebuttal", "r3/re-review", "r4/gate", "final/handoff"]:
        assert phase in combined
    for role in ["PriorArtBreaker", "FeasibilityBreaker", "AuthorAdvocate", "Gatekeeper"]:
        assert role in skill
    for artifact_type in ["Rebuttal", "RevisionPlan", "ScoreCard", "MetaReview"]:
        assert artifact_type in skill
    assert "re-read this SKILL.md" in skill
    assert "idea_spark_message_post" in skill


def test_bundled_skill_is_thin_router_with_parent_and_subagent_references():
    base = Path("idea_spark/resources/skills/idea-spark-usage")
    skill = read_text(base / "SKILL.md")
    refs = {path.name: read_text(path) for path in sorted((base / "references").glob("*.md"))}

    assert len(skill.encode("utf-8")) < 9000
    assert set(refs) == {"cli-dashboard.md", "handoff-report.md", "parent-controller.md", "subagent-contract.md"}
    assert skill.count("[PARENT-ONLY]") >= 5
    assert skill.count("[SUBAGENT-ONLY]") >= 4
    assert "references/parent-controller.md" in skill
    assert "references/subagent-contract.md" in skill
    assert "references/cli-dashboard.md" in skill
    assert "references/handoff-report.md" in skill
    assert "If a plugin-bundled reference request returns this main SKILL again" in skill
    assert "The parent must keep the phase loop moving" in refs["parent-controller.md"]
    assert "A subagent performs one assigned role in one phase" in refs["subagent-contract.md"]
    assert "use `read_file` on `idea_spark/resources/skills/idea-spark-usage/references/subagent-contract.md`" in refs["subagent-contract.md"]
    assert "not automatically suitable as a human handoff report" in refs["handoff-report.md"]
    assert "Optional tool-mode" in refs["cli-dashboard.md"]


def test_examples_do_not_document_legacy_aliases_or_internal_execution():
    text = "\n".join(
        [
            read_text("README.md"),
            read_text("examples/ml_idea_review_prompt.md"),
            read_text("examples/delegate_task_template.json"),
            read_text("examples/discussion_until_gate_template.json"),
        ]
    ).lower()

    for forbidden in ["legacy alias", "automatic forwarding", "plugin-internal web", "plugin-internal terminal"]:
        assert forbidden not in text


def test_readme_sections_are_complete_and_ordered():
    text = read_text("README.md")

    positions = [text.index(section) for section in README_SECTIONS]
    assert positions == sorted(positions)


def test_delegate_task_template_is_valid_and_cli_first_by_default():
    data = json.loads(read_text("examples/delegate_task_template.json"))
    combined = f"{data['goal']}\n{data['context']}"

    assert data["toolsets"] == ["terminal", "file", "skills"]
    assert "room_id" in data["context"]
    assert "idea_spark_room_join" in combined
    assert "hermes idea-spark call" in combined
    assert "skill_view" in data["goal"]
    assert "idea-spark:idea-spark-usage" in data["goal"]
    assert 'toolsets=["idea_spark", "skills"]' in combined


def test_bundled_skill_requires_skills_toolset_and_explicit_tool_mode_for_tools():
    skill = read_text("idea_spark/resources/skills/idea-spark-usage/SKILL.md")
    cli_dashboard = read_text("idea_spark/resources/skills/idea-spark-usage/references/cli-dashboard.md")
    subagent_contract = read_text("idea_spark/resources/skills/idea-spark-usage/references/subagent-contract.md")
    combined = f"{skill}\n{cli_dashboard}\n{subagent_contract}"

    assert 'toolsets=["terminal", "file", "skills"]' in combined
    assert 'toolsets=["idea_spark", "skills"]' in combined
    assert "hermes idea-spark config set-tools true" in combined
    assert 'skill_view(name="idea-spark:idea-spark-usage")' in combined
    assert "Do not call `skill_manage`" in combined or "not to call `skill_manage`" in combined


def test_bundled_skill_documents_discussion_until_gate_controller_contract():
    skill = read_text("idea_spark/resources/skills/idea-spark-usage/SKILL.md")
    parent_ref = read_text("idea_spark/resources/skills/idea-spark-usage/references/parent-controller.md")
    handoff_ref = read_text("idea_spark/resources/skills/idea-spark-usage/references/handoff-report.md")
    cli_dashboard = read_text("idea_spark/resources/skills/idea-spark-usage/references/cli-dashboard.md")
    subagent_contract = read_text("idea_spark/resources/skills/idea-spark-usage/references/subagent-contract.md")
    combined = f"{skill}\n{parent_ref}\n{handoff_ref}\n{cli_dashboard}\n{subagent_contract}"

    required = [
        "discussion-until-gate",
        "Seed / Framing",
        "Novelty Attack",
        "r1 / Novelty Attack",
        "r2 / Author Rebuttal / Improvement Draft",
        "r3 / Re-review / Cross-examination",
        "r4 / Gate",
        "Author Rebuttal / Improvement Draft",
        "Re-review / Cross-examination",
        "Gate",
        "has_terminal_gate",
        "Gatekeeper must call `idea_spark_gate_record`",
        "message-only gate is not final",
        "Round-continuity rule",
        "Standalone handoff report contract",
        'toolsets=["terminal", "file", "skills"]',
        'toolsets=["idea_spark", "skills"]',
        "Do not call `skill_manage`",
    ]
    for text in required:
        assert text in combined


def test_readme_and_prompt_document_discussion_until_gate_without_scheduler_claims():
    readme = read_text("README.md")
    prompt = read_text("examples/ml_idea_review_prompt.md")
    combined = f"{readme}\n{prompt}".lower()

    assert 'toolsets=["terminal", "file", "skills"]' in readme
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


def test_discussion_until_gate_template_is_valid_cli_first_and_bounded():
    data = json.loads(read_text("examples/discussion_until_gate_template.json"))
    combined = f"{data['goal']}\n{data['context']}"

    assert data["role"] == "orchestrator"
    assert data["toolsets"] == ["terminal", "file", "skills"]
    assert "hermes idea-spark call" in combined
    assert 'toolsets=["idea_spark", "skills"]' in combined
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
