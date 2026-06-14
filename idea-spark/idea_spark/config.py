from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def hermes_home() -> Path:
    configured = os.getenv("HERMES_HOME")
    if configured:
        return Path(configured)
    return Path.home() / ".hermes"


def config_path() -> Path:
    return hermes_home() / "idea-spark" / "config.json"


def _default_config() -> dict[str, Any]:
    return {"tools": {"enabled": False}}


def _merge_defaults(data: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(data) if isinstance(data, dict) else {}
    raw_tools = data.get("tools") if isinstance(data, dict) else None
    tools = dict(raw_tools) if isinstance(raw_tools, dict) else {}
    tools["enabled"] = raw_tools.get("enabled") is True if isinstance(raw_tools, dict) else False
    merged["tools"] = tools
    return merged


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return _default_config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_config()
    if not isinstance(data, dict):
        return _default_config()
    return _merge_defaults(data)


def tools_enabled() -> bool:
    return load_config()["tools"]["enabled"] is True


def save_config(config: dict[str, Any]) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _merge_defaults(config)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def set_tools_enabled(enabled: bool) -> Path:
    config = load_config()
    tools = config.get("tools")
    if not isinstance(tools, dict):
        tools = {}
    tools["enabled"] = bool(enabled)
    config["tools"] = tools
    return save_config(config)
