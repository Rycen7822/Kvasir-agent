from pathlib import Path

from .schemas import TOOL_NAMES, TOOLSET
from .tools import HANDLERS, schema_for

SKILL_NAME = "idea-spark-usage"
SKILL_DESCRIPTION = "Use Idea-Spark shared-ledger debate rooms with Hermes delegate_task child agents."


def _skill_path() -> Path:
    return Path(__file__).resolve().parent / "resources" / "skills" / SKILL_NAME / "SKILL.md"


def _register_bundled_skill(ctx) -> None:
    if not hasattr(ctx, "register_skill"):
        return
    path = _skill_path()
    if path.exists():
        ctx.register_skill(SKILL_NAME, path, SKILL_DESCRIPTION)


def register(ctx):
    for name in TOOL_NAMES:
        ctx.register_tool(
            name=name,
            toolset=TOOLSET,
            schema=schema_for(name),
            handler=HANDLERS[name],
        )
    _register_bundled_skill(ctx)
