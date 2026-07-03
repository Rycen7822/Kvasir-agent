from __future__ import annotations

from pathlib import Path

try:
    from .commands import start_ponder_forge_command
except ImportError:
    from commands import start_ponder_forge_command

SKILL_NAME = "ponder-forge-usage"
SKILL_DESCRIPTION = "Operate Ponder-Forge complex-problem workflows through the pure CLI."
COMMAND_NAME = "ponder-forge"
COMMAND_DESCRIPTION = "Start a Ponder-Forge CLI-backed workflow."


def _skill_path() -> Path:
    return Path(__file__).resolve().parent / "resources" / "skills" / SKILL_NAME / "SKILL.md"


def register(ctx) -> None:
    ctx.register_command(
        name=COMMAND_NAME,
        handler=lambda raw: start_ponder_forge_command(ctx, raw),
        description=COMMAND_DESCRIPTION,
        args_hint="<complex problem>",
    )

    skill = _skill_path()
    if skill.exists():
        ctx.register_skill(SKILL_NAME, skill, SKILL_DESCRIPTION)
