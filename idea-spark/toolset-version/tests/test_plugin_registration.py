import importlib.util
import inspect
import json
import sys
import types
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
    assert "toolset-first" in skill["description"]
    assert "continuous r1-r4" in skill["description"]
    assert "standalone handoff reports" in skill["description"]


def test_bundled_skill_documents_toolset_role_boundaries_and_handoff_report():
    skill_text = Path("idea_spark/resources/skills/idea-spark-usage/SKILL.md").read_text(encoding="utf-8")
    parent_ref = Path("idea_spark/resources/skills/idea-spark-usage/references/parent-controller.md").read_text(encoding="utf-8")
    subagent_ref = Path("idea_spark/resources/skills/idea-spark-usage/references/subagent-contract.md").read_text(encoding="utf-8")
    handoff_ref = Path("idea_spark/resources/skills/idea-spark-usage/references/handoff-report.md").read_text(encoding="utf-8")

    assert "Thin workflow router" in skill_text
    assert "**[PARENT-ONLY] Parent/main agent:**" in skill_text
    assert "**[SUBAGENT-ONLY] Subagent/child agent:**" in skill_text
    assert "Do not stop after r1/r2/r3" in skill_text
    assert "r1 → r2 → r3 → r4" in parent_ref
    assert "Mandatory skill re-read after each phase" in parent_ref
    assert 'toolsets=["idea_spark", "skills"]' in subagent_ref
    assert "Ledger export vs handoff report" in handoff_ref
    assert "not automatically suitable as a human handoff report" in handoff_ref


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


def test_hermes_namespaced_plugin_load_can_run_store_migrations(temp_idea_spark_db):
    """Hermes loads user plugins as hermes_plugins.<slug>, not top-level packages."""
    parent_name = "hermes_plugins_test"
    module_name = f"{parent_name}.idea_spark"
    for name in list(sys.modules):
        if name == parent_name or name.startswith(f"{parent_name}."):
            sys.modules.pop(name)

    parent = types.ModuleType(parent_name)
    parent.__path__ = []  # type: ignore[attr-defined]
    parent.__package__ = parent_name
    sys.modules[parent_name] = parent

    plugin_dir = Path("idea_spark").resolve()
    spec = importlib.util.spec_from_file_location(
        module_name,
        plugin_dir / "__init__.py",
        submodule_search_locations=[str(plugin_dir)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    module.__package__ = module_name
    module.__path__ = [str(plugin_dir)]
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    ctx = FakeContext()
    module.register(ctx)
    handler = next(tool["handler"] for tool in ctx.tools if tool["name"] == "idea_spark_room_create")
    result = json.loads(
        handler(
            {
                "room_id": "namespaced-plugin-smoke",
                "title": "namespaced plugin smoke",
                "topic": "store migrations resolve relative to hermes plugin namespace",
                "created_by": "test",
            }
        )
    )

    assert result["success"] is True
    assert result["room_id"] == "namespaced-plugin-smoke"
    assert temp_idea_spark_db.exists()
