from __future__ import annotations

import os
from pathlib import Path

from .shared import ensure_dir


def _looks_like_repo_root(path: Path) -> bool:
    return (
        (path / "pyproject.toml").exists()
        and (path / "src" / "deepscientist").exists()
        and (path / "src" / "skills").exists()
    )


def repo_root() -> Path:
    configured = str(os.environ.get("DEEPSCIENTIST_REPO_ROOT") or "").strip()
    if configured:
        candidate = Path(configured).expanduser().resolve()
        if _looks_like_repo_root(candidate):
            return candidate

    cwd = Path.cwd().resolve()
    if _looks_like_repo_root(cwd):
        return cwd

    candidate = Path(__file__).resolve().parents[2]
    if _looks_like_repo_root(candidate):
        return candidate
    return candidate


def default_home() -> Path:
    return Path.home() / "DeepScientist"


def ensure_home_layout(home: Path) -> dict[str, Path]:
    runtime = ensure_dir(home / "runtime")
    ensure_dir(runtime / "bundle")
    ensure_dir(runtime / "tools")
    ensure_dir(runtime / "python")
    ensure_dir(runtime / "uv-cache")

    config = ensure_dir(home / "config")
    ensure_dir(config / "baselines")
    ensure_dir(config / "baselines" / "entries")

    memory = ensure_dir(home / "memory")
    for kind in ("papers", "ideas", "decisions", "episodes", "knowledge", "templates"):
        ensure_dir(memory / kind)

    quests = ensure_dir(home / "quests")
    plugins = ensure_dir(home / "plugins")
    logs = ensure_dir(home / "logs")
    cache = ensure_dir(home / "cache")
    ensure_dir(cache / "skills")

    return {
        "home": home,
        "runtime": runtime,
        "config": config,
        "memory": memory,
        "quests": quests,
        "plugins": plugins,
        "logs": logs,
        "cache": cache,
    }
