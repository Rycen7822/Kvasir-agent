from __future__ import annotations

from pathlib import Path
import importlib.util

try:
    from .commands import start_ponder_forge_command
    from .hooks import HOOK_HANDLERS
    from .schemas import HOOK_NAMES, TOOL_NAMES, TOOLSET, schema_for
    from .tools import HANDLERS
except ImportError:
    from schemas import HOOK_NAMES, TOOL_NAMES, TOOLSET, schema_for

    _hooks_spec = importlib.util.spec_from_file_location("ponder_forge_local_hooks", Path(__file__).resolve().parent / "hooks.py")
    if _hooks_spec is None or _hooks_spec.loader is None:
        raise
    _hooks = importlib.util.module_from_spec(_hooks_spec)
    _hooks_spec.loader.exec_module(_hooks)
    HOOK_HANDLERS = _hooks.HOOK_HANDLERS

    _tools_spec = importlib.util.spec_from_file_location("ponder_forge_local_tools", Path(__file__).resolve().parent / "tools.py")
    if _tools_spec is None or _tools_spec.loader is None:
        raise
    _tools = importlib.util.module_from_spec(_tools_spec)
    _tools_spec.loader.exec_module(_tools)
    HANDLERS = _tools.HANDLERS

    _commands_spec = importlib.util.spec_from_file_location("ponder_forge_local_commands", Path(__file__).resolve().parent / "commands.py")
    if _commands_spec is None or _commands_spec.loader is None:
        raise
    _commands = importlib.util.module_from_spec(_commands_spec)
    _commands_spec.loader.exec_module(_commands)
    start_ponder_forge_command = _commands.start_ponder_forge_command

SKILL_NAME = "ponder-forge-usage"
SKILL_DESCRIPTION = "Operate Ponder-Forge complex-problem team workflows from Hermes."
COMMAND_NAME = "ponder-forge"
COMMAND_DESCRIPTION = "Run a Ponder-Forge verification-centric team workflow."


def _skill_path() -> Path:
    return Path(__file__).resolve().parent / "resources" / "skills" / SKILL_NAME / "SKILL.md"


def _hermes_tool_handler(handler):
    def _wrapped(args=None, **_kwargs):
        return handler(args)

    return _wrapped


def register(ctx) -> None:
    for name in TOOL_NAMES:
        ctx.register_tool(
            name=name,
            toolset=TOOLSET,
            schema=schema_for(name),
            handler=_hermes_tool_handler(HANDLERS[name]),
        )

    for hook_name in HOOK_NAMES:
        ctx.register_hook(hook_name, HOOK_HANDLERS[hook_name])

    ctx.register_command(
        name=COMMAND_NAME,
        handler=lambda raw: start_ponder_forge_command(ctx, raw),
        description=COMMAND_DESCRIPTION,
        args_hint="<complex problem>",
    )

    skill = _skill_path()
    if skill.exists():
        ctx.register_skill(SKILL_NAME, skill, SKILL_DESCRIPTION)
