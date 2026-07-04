from pathlib import Path

try:
    from .config import tools_enabled
    from .schemas import TOOL_NAMES, TOOLSET
    from .tools import HANDLERS, schema_for
except ImportError:  # source-root import, including pytest parent-package collection
    from config import tools_enabled
    from schemas import TOOL_NAMES, TOOLSET
    from tools import HANDLERS, schema_for

SKILL_NAME = "idea-spark-usage"
SKILL_DESCRIPTION = "Use Idea-Spark shared-ledger debate rooms with Hermes delegate_task child agents, continuous r1-r4 gates, and standalone handoff reports."
CLI_NAME = "idea-spark"
CLI_DESCRIPTION = "Manage Idea-Spark ledger operations and tool-mode config."


def _skill_path() -> Path:
    return Path(__file__).resolve().parent / "resources" / "skills" / SKILL_NAME / "SKILL.md"


def _register_bundled_skill(ctx) -> None:
    if not hasattr(ctx, "register_skill"):
        return
    path = _skill_path()
    if path.exists():
        ctx.register_skill(SKILL_NAME, path, SKILL_DESCRIPTION)


def _register_cli(ctx) -> None:
    if not hasattr(ctx, "register_cli_command"):
        return
    from .cli import hermes_main_from_args, setup_parser

    ctx.register_cli_command(
        name=CLI_NAME,
        help=CLI_DESCRIPTION,
        setup_fn=setup_parser,
        handler_fn=hermes_main_from_args,
        description="Idea-Spark shared-ledger CLI",
    )


def _register_tools(ctx) -> None:
    for name in TOOL_NAMES:
        ctx.register_tool(
            name=name,
            toolset=TOOLSET,
            schema=schema_for(name),
            handler=HANDLERS[name],
        )


def register(ctx):
    _register_bundled_skill(ctx)
    _register_cli(ctx)
    if tools_enabled():
        _register_tools(ctx)
