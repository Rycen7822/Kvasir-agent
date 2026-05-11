from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CONFIG_NAMES = ("config", "runners", "connectors", "plugins", "native_tool_servers_disabled")
REQUIRED_CONFIG_NAMES = ("config", "runners")
OPTIONAL_CONFIG_NAMES = ("connectors", "plugins", "native_tool_servers_disabled")
SYSTEM_CONNECTOR_NAMES: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConfigFileInfo:
    name: str
    path: Path
    required: bool
    exists: bool


def config_filename(name: str) -> str:
    return f"{name}.yaml"


def default_system_enabled_connectors() -> dict[str, bool]:
    return {}


def default_config(home: Path) -> dict:
    return {
        "home": str(home),
        "default_runner": "codex",
        "default_locale": "zh-CN",
        "runtime_server": {
            "session_restore_on_start": True,
            "max_concurrent_quests": 1,
            "ack_timeout_ms": 1000,
        },
        "ui": {
            "host": "0.0.0.0",
            "port": 20999,
            "auth_enabled": False,
            "auto_open_browser": False,
            "default_mode": "headless",
        },
        "logging": {
            "level": "info",
            "console": True,
            "keep_days": 30,
        },
        "git": {
            "auto_checkpoint": True,
            "auto_push": False,
            "default_remote": "origin",
            "graph_formats": ["svg", "png", "json"],
        },
        "skills": {
            "sync_global_on_init": True,
            "sync_quest_on_create": True,
            "sync_quest_on_open": True,
        },
        "bootstrap": {
            "codex_ready": False,
            "codex_last_checked_at": None,
            "codex_last_result": {},
            "locale_source": "default",
            "locale_initialized_from_browser": False,
            "locale_initialized_at": None,
            "locale_initialized_browser_locale": None,
        },
        "connectors": {
            "enabled": False,
            "auto_ack": False,
            "milestone_push": False,
            "direct_chat_enabled": False,
            "system_enabled": default_system_enabled_connectors(),
        },
        "cloud": {
            "enabled": False,
            "base_url": "https://deepscientist.cc",
            "token": None,
            "token_env": "DEEPSCIENTIST_TOKEN",
            "verify_token_on_start": False,
            "sync_mode": "disabled",
        },
        "acp": {
            "compatibility_profile": "deepscientist-acp-compat/v1",
            "events_transport": "rest-poll",
            "sdk_bridge_enabled": False,
            "sdk_module": "acp",
        },
    }


def default_runners() -> dict:
    return {
        "codex": {
            "enabled": True,
            "binary": "codex",
            "config_dir": "~/.codex",
            "profile": "",
            "model": "inherit",
            "model_reasoning_effort": "xhigh",
            "approval_policy": "never",
            "sandbox_mode": "danger-full-access",
            "retry_on_failure": True,
            "retry_max_attempts": 5,
            "retry_initial_backoff_sec": 10.0,
            "retry_backoff_multiplier": 6.0,
            "retry_max_backoff_sec": 1800.0,
            # Increase native dsctl tool timeout so codex can wait for long `ds_bash_exec` await/read operations
            # or other durable native tool calls without prematurely timing out.
            # Mirrors DS_2027's `codex.native_tool_tool_timeout_sec` default.
            "native_tool_tool_timeout_sec": 180000,
            "env": {},
        },
        "claude": {
            "enabled": False,
            "binary": "claude",
            "config_dir": "~/.claude",
            "model": "inherit",
            "model_reasoning_effort": "",
            "env": {},
            "status": "reserved_todo",
        },
    }


def default_connectors() -> dict:
    return {
        "_headless": True,
        "enabled": False,
        "_routing": {
            "primary_connector": None,
            "artifact_delivery_policy": "disabled",
        },
    }


def default_plugins(home: Path) -> dict:
    return {
        "load_paths": [str(home / "plugins")],
        "enabled": [],
        "disabled": [],
        "allow_unsigned": False,
    }


def default_native_tool_servers_disabled() -> dict:
    return {"servers": {}}


def default_payload(name: str, home: Path) -> dict:
    if name == "config":
        return default_config(home)
    if name == "runners":
        return default_runners()
    if name == "connectors":
        return default_connectors()
    if name == "plugins":
        return default_plugins(home)
    if name == "native_tool_servers_disabled":
        return default_native_tool_servers_disabled()
    raise KeyError(name)
