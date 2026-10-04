from __future__ import annotations

import os
from pathlib import Path


def hermes_home() -> Path:
    """Return the active Hermes home, honoring tests and profile-specific homes."""
    value = os.getenv("HERMES_HOME")
    if value:
        return Path(value).expanduser().resolve()
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home()).expanduser().resolve()
    except Exception:
        return Path.home() / ".hermes"


def state_dir(home: Path | None = None) -> Path:
    return (home or hermes_home()) / "ponder_forge"


def runs_dir(home: Path | None = None) -> Path:
    return state_dir(home) / "runs"


def db_path(home: Path | None = None) -> Path:
    return state_dir(home) / "state.sqlite3"
