from __future__ import annotations

from codexscientist_native import schemas


def _props(schema_name: str) -> dict:
    schema = next(item for item in schemas.PUBLIC_SCHEMAS if item["name"] == schema_name)
    return schema["input_schema"]["properties"]


def test_new_quest_schema_defaults_to_copilot_and_disables_auto_idea_improvement():
    props = _props("cs_new_quest")

    assert props["workspace_mode"]["enum"] == ["copilot", "autonomous"]
    assert props["workspace_mode"]["default"] == "copilot"
    assert props["decision_policy"]["default"] == "user_gated"
    assert props["autonomous_idea_improvement"]["default"] is False
    assert "explicit" in props["autonomous_idea_improvement"]["description"].lower()


def test_submit_idea_schema_marks_auto_generation_as_explicitly_gated():
    props = _props("cs_submit_idea")

    assert props["source"]["enum"]
    assert props["autonomous_generated"]["default"] is False
    assert "explicit" in props["autonomous_generated"]["description"].lower()
