import inspect
import json
from pathlib import Path

from test_schema_contract import EXPECTED_TOOL_NAMES


class FakeContext:
    def __init__(self):
        self.tools = []
        self.skills = []

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools.append(
            {
                "name": name,
                "toolset": toolset,
                "schema": schema,
                "handler": handler,
                "kwargs": kwargs,
            }
        )

    def register_skill(self, name, path, description=""):
        self.skills.append({"name": name, "path": Path(path), "description": description})


def _manifest_tools():
    manifest = Path("idea_spark/plugin.yaml").read_text(encoding="utf-8").splitlines()
    assert "provides_tools:" in manifest
    tools = []
    in_tools = False
    for line in manifest:
        if line.strip() == "provides_tools:":
            in_tools = True
            continue
        if in_tools:
            if line.startswith("  - "):
                tools.append(line.split("- ", 1)[1].strip())
            elif line and not line.startswith(" "):
                break
    return tools


def test_plugin_manifest_uses_current_provides_tools_field():
    text = Path("idea_spark/plugin.yaml").read_text(encoding="utf-8")

    assert "name: idea-spark" in text
    assert "kind: standalone" in text
    assert "provides_tools:" in text
    assert "toolsets:" not in text
    assert not any(line == "tools:" for line in text.splitlines())
    assert _manifest_tools() == EXPECTED_TOOL_NAMES


def test_register_declares_all_manifest_tools_with_idea_spark_toolset():
    import idea_spark

    ctx = FakeContext()
    idea_spark.register(ctx)

    assert [tool["name"] for tool in ctx.tools] == EXPECTED_TOOL_NAMES
    assert _manifest_tools() == [tool["name"] for tool in ctx.tools]
    assert all(tool["toolset"] == "idea_spark" for tool in ctx.tools)
    assert all(callable(tool["handler"]) for tool in ctx.tools)
    assert all(tool["schema"]["name"] == tool["name"] for tool in ctx.tools)
    assert all(tool["schema"]["parameters"].get("properties") for tool in ctx.tools)
    assert "idea-spark-usage" in ctx.tools[0]["schema"]["description"]


def test_register_declares_bundled_usage_skill():
    import idea_spark

    ctx = FakeContext()
    idea_spark.register(ctx)

    assert len(ctx.skills) == 1
    skill = ctx.skills[0]
    assert skill["name"] == "idea-spark-usage"
    assert skill["path"].name == "SKILL.md"
    assert skill["path"].exists()
    assert "delegate_task" in skill["description"]


def test_register_matches_manifest_tool_names():
    import idea_spark

    ctx = FakeContext()
    idea_spark.register(ctx)

    assert _manifest_tools() == [tool["name"] for tool in ctx.tools]


def test_no_handler_raises_on_minimal_invalid_payload():
    import idea_spark

    ctx = FakeContext()
    idea_spark.register(ctx)

    for tool in ctx.tools:
        signature = inspect.signature(tool["handler"])
        assert "args" in signature.parameters
        result = tool["handler"]({})
        assert isinstance(result, str)
        payload = json.loads(result)
        assert payload["success"] is False
        assert "error" in payload
