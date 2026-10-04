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
        self.cli_commands = []

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

    def register_cli_command(self, name, help, setup_fn, handler_fn=None, description=""):
        self.cli_commands.append(
            {
                "name": name,
                "help": help,
                "setup_fn": setup_fn,
                "handler_fn": handler_fn,
                "description": description,
            }
        )


class FakeContextWithoutCli:
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
    manifest = Path("plugin.yaml").read_text(encoding="utf-8").splitlines()
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


def _enable_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from idea_spark.config import set_tools_enabled

    set_tools_enabled(True)


def test_plugin_manifest_lists_optional_canonical_tool_capabilities():
    text = Path("plugin.yaml").read_text(encoding="utf-8")

    assert "name: idea-spark" in text
    assert "kind: standalone" in text
    assert "config-gated optional tools" in text
    assert "provides_tools:" in text
    assert "toolsets:" not in text
    assert not any(line == "tools:" for line in text.splitlines())
    assert _manifest_tools() == EXPECTED_TOOL_NAMES


def test_register_defaults_to_skill_and_cli_without_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    import idea_spark

    ctx = FakeContext()
    idea_spark.register(ctx)

    assert ctx.tools == []
    assert [skill["name"] for skill in ctx.skills] == ["idea-spark-usage"]
    assert ctx.skills[0]["path"].name == "SKILL.md"
    assert ctx.skills[0]["path"].exists()
    assert "delegate_task" in ctx.skills[0]["description"]
    assert "continuous r1-r4" in ctx.skills[0]["description"]
    assert "standalone handoff reports" in ctx.skills[0]["description"]
    assert [cmd["name"] for cmd in ctx.cli_commands] == ["idea-spark"]
    assert callable(ctx.cli_commands[0]["setup_fn"])
    assert callable(ctx.cli_commands[0]["handler_fn"])


def test_bundled_skill_documents_continuous_gate_and_handoff_report():
    skill_text = Path("resources/skills/idea-spark-usage/SKILL.md").read_text(encoding="utf-8")
    parent_ref = Path("resources/skills/idea-spark-usage/references/parent-controller.md").read_text(encoding="utf-8")
    handoff_ref = Path("resources/skills/idea-spark-usage/references/handoff-report.md").read_text(encoding="utf-8")

    assert "Thin workflow router" in skill_text
    assert "Do not stop after r1/r2/r3" in skill_text
    assert "Do not stop after `r1`" in parent_ref
    assert "r1 → r2 → r3 → r4" in parent_ref
    assert "Mandatory skill re-read after each phase" in parent_ref
    assert "idea_spark_phase_ledger.md" in parent_ref
    assert "Do not send a user-facing final answer after r1" in parent_ref
    assert "Ledger export vs handoff report" in handoff_ref
    assert "not automatically suitable as a human handoff report" in handoff_ref
    assert "current working directory" in handoff_ref
    assert "Do not save the standalone handoff report under `/tmp`" in handoff_ref
    assert "detailed enough that another researcher" in handoff_ref
    assert "local paths, URLs, room IDs, artifact IDs, need IDs, and gate IDs" in skill_text


def test_register_still_loads_skill_when_cli_registration_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    import idea_spark

    ctx = FakeContextWithoutCli()
    idea_spark.register(ctx)

    assert ctx.tools == []
    assert [skill["name"] for skill in ctx.skills] == ["idea-spark-usage"]


def test_register_declares_all_manifest_tools_only_when_explicit_config_enabled(tmp_path, monkeypatch):
    _enable_tools(tmp_path, monkeypatch)
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
    assert [skill["name"] for skill in ctx.skills] == ["idea-spark-usage"]
    assert [cmd["name"] for cmd in ctx.cli_commands] == ["idea-spark"]


def test_no_handler_raises_on_minimal_invalid_payload_when_tools_enabled(tmp_path, monkeypatch):
    _enable_tools(tmp_path, monkeypatch)
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


def test_hermes_namespaced_plugin_load_can_run_store_migrations(temp_idea_spark_db, tmp_path, monkeypatch):
    """Hermes loads user plugins as hermes_plugins.<slug>, not top-level packages."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    parent_name = "hermes_plugins_test"
    module_name = f"{parent_name}.idea_spark"
    for name in list(sys.modules):
        if name == parent_name or name.startswith(f"{parent_name}."):
            sys.modules.pop(name)

    parent = types.ModuleType(parent_name)
    parent.__path__ = []  # type: ignore[attr-defined]
    parent.__package__ = parent_name
    sys.modules[parent_name] = parent

    plugin_dir = Path(".").resolve()
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

    from idea_spark.config import set_tools_enabled

    set_tools_enabled(True)
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
