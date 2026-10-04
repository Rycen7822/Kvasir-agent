from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS: list[str] = []
EXPECTED_HOOKS: list[str] = []
OBSOLETE_HOOKS = ["subagent_start", "subagent_stop", "post_tool_call", "pre_tool_call", "pre_llm_call", "on_session_end"]


class FakeContext:
    def __init__(self):
        self.tools = []
        self.hooks = []
        self.commands = []
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

    def register_hook(self, hook_name, callback):
        self.hooks.append({"hook_name": hook_name, "callback": callback})

    def register_command(self, name, handler, description="", args_hint=""):
        self.commands.append(
            {"name": name, "handler": handler, "description": description, "args_hint": args_hint}
        )

    def register_skill(self, name, path, description=""):
        self.skills.append({"name": name, "path": Path(path), "description": description})


def _load_plugin():
    if "hermes_plugins" not in sys.modules:
        parent = types.ModuleType("hermes_plugins")
        parent.__path__ = []
        parent.__package__ = "hermes_plugins"
        sys.modules["hermes_plugins"] = parent
    init_file = ROOT / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "hermes_plugins.ponder_forge_test",
        init_file,
        submodule_search_locations=[str(ROOT)],
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _manifest_list(section: str) -> list[str]:
    text = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
    lines = text.splitlines()
    values: list[str] = []
    in_section = False
    for line in lines:
        if line.strip() == f"{section}:":
            in_section = True
            continue
        if in_section:
            if line.startswith("  - "):
                values.append(line.split("- ", 1)[1].strip())
            elif line and not line.startswith(" "):
                break
    return values


def test_manifest_declares_flat_plugin_contract():
    text = (ROOT / "plugin.yaml").read_text(encoding="utf-8")

    assert "name: ponder-forge" in text
    assert "kind: standalone" in text
    assert "provides_tools:" in text
    assert "provides_hooks:" in text
    assert _manifest_list("provides_tools") == EXPECTED_TOOLS
    assert _manifest_list("provides_hooks") == EXPECTED_HOOKS
    assert "ponder_forge_" not in text
    assert not any(name in text for name in OBSOLETE_HOOKS)
    assert not (ROOT / "ponder_forge").exists(), "plugin source must stay flat; no nested package"


def test_register_exposes_only_command_and_bundled_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    plugin = _load_plugin()
    ctx = FakeContext()

    plugin.register(ctx)

    assert ctx.tools == []
    assert ctx.hooks == []
    assert [command["name"] for command in ctx.commands] == ["ponder-forge"]
    assert ctx.commands[0]["args_hint"] == "<complex problem>"
    assert callable(ctx.commands[0]["handler"])
    assert [skill["name"] for skill in ctx.skills] == ["ponder-forge-usage"]
    assert ctx.skills[0]["path"].name == "SKILL.md"
    assert ctx.skills[0]["path"].exists()
    assert "Ponder-Forge" in ctx.skills[0]["description"]


def test_slash_command_creates_run_and_cli_next_instruction(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    plugin = _load_plugin()
    ctx = FakeContext()
    plugin.register(ctx)

    result = json.loads(ctx.commands[0]["handler"]("research source notes"))

    assert result["success"] is True
    assert result["profile"] == "research"
    assert result["next_command"] == "plan"
    assert "cli.py plan --run-id" in result["instruction"]
    assert "delegations" in result["instruction"]
    assert 'role="orchestrator"' in result["instruction"]
    assert "child_reports" in result["instruction"]
    assert "submit-report" in result["instruction"]
    assert "ponder_forge_" not in result["instruction"]
