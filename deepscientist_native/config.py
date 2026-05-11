"""Configuration for the Codex-native DeepScientist plugin.

This module intentionally does not resolve or require a global `ds` binary.
Codex CLI is the control plane for this native adapter.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - PyYAML is expected in Hermes env, but keep JSON-ish fallback.
    yaml = None

PLUGIN_ROOT = Path(__file__).resolve().parent
PROJECT_HOME_DIR_NAME = "DeepScientist"
PROJECT_CONFIG_FILE_NAME = "codex-native.yaml"


def _launch_workdir() -> Path:
    configured = str(os.environ.get("DEEPSCIENTIST_PROJECT_ROOT") or "").strip()
    return Path(configured).expanduser().resolve() if configured else Path.cwd().resolve()


def _default_project_home() -> Path:
    return _launch_workdir() / PROJECT_HOME_DIR_NAME


def _legacy_config_root_override() -> Path | None:
    configured = str(os.environ.get("DEEPSCIENTIST_HERMES_ROOT") or "").strip()
    return Path(configured).expanduser() if configured else None


def _default_config_root() -> Path:
    return _legacy_config_root_override() or _default_project_home()


def _default_config_path() -> Path:
    configured = str(os.environ.get("DEEPSCIENTIST_HERMES_CONFIG") or "").strip()
    if configured:
        return Path(configured).expanduser()
    legacy_root = _legacy_config_root_override()
    if legacy_root is not None:
        return legacy_root / "config.yaml"
    return _default_project_home() / "config" / PROJECT_CONFIG_FILE_NAME


# Backward-compatible snapshots for callers that import these names directly.
DEFAULT_CONFIG_ROOT = _default_config_root()
DEFAULT_CONFIG_PATH = _default_config_path()


@dataclass(frozen=True)
class NativeConfig:
    config_root: Path
    config_path: Path
    runtime_home: Path
    session_map_path: Path
    mode_default_enabled: bool = True
    auto_detect_research_tasks: bool = True
    active_quest_policy: str = "reuse_or_create_with_user_confirmation"
    stage_skill_injection: str = "active_only"
    companion_skill_injection: str = "on_demand"
    runner: str = "codex"
    allow_legacy_cli_fallback: bool = False
    allow_codex_runner_fallback: bool = False
    use_deepscientist_memory: bool = True
    sync_to_hermes_memory: bool = False
    resource_repo_root: Path | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "config_root": str(self.config_root),
            "config_path": str(self.config_path),
            "runtime_home": str(self.runtime_home),
            "session_map_path": str(self.session_map_path),
            "mode": {
                "default_enabled": self.mode_default_enabled,
                "auto_detect_research_tasks": self.auto_detect_research_tasks,
                "active_quest_policy": self.active_quest_policy,
                "stage_skill_injection": self.stage_skill_injection,
                "companion_skill_injection": self.companion_skill_injection,
            },
            "runtime": {
                "runner": self.runner,
                "allow_legacy_cli_fallback": self.allow_legacy_cli_fallback,
                "allow_codex_runner_fallback": self.allow_codex_runner_fallback,
            },
            "memory": {
                "use_deepscientist_memory": self.use_deepscientist_memory,
                "sync_to_hermes_memory": self.sync_to_hermes_memory,
            },
            "resource_repo_root": str(self.resource_repo_root) if self.resource_repo_root else None,
        }


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    if yaml is None:
        # Minimal fallback: config is optional, so fail closed with defaults.
        return {}
    data = yaml.safe_load(raw)
    return data if isinstance(data, dict) else {}


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _as_path(value: Any, default: Path) -> Path:
    text = str(value or "").strip()
    return Path(text).expanduser() if text else default


def load_config(config_path: Path | None = None) -> NativeConfig:
    path = (config_path or _default_config_path()).expanduser()
    data = _read_yaml(path)
    root = _as_path(data.get("config_root"), _default_config_root())
    runtime_home = _as_path(data.get("runtime_home"), root)
    state_data = data.get("state") if isinstance(data.get("state"), dict) else {}
    mode_data = data.get("mode") if isinstance(data.get("mode"), dict) else {}
    runtime_data = data.get("runtime") if isinstance(data.get("runtime"), dict) else {}
    memory_data = data.get("memory") if isinstance(data.get("memory"), dict) else {}
    resource_repo_root = data.get("resource_repo_root")
    return NativeConfig(
        config_root=root,
        config_path=path,
        runtime_home=runtime_home,
        session_map_path=_as_path(state_data.get("session_map_path"), runtime_home / "runtime" / "codex-session-map.json"),
        mode_default_enabled=_as_bool(mode_data.get("default_enabled"), True),
        auto_detect_research_tasks=_as_bool(mode_data.get("auto_detect_research_tasks"), True),
        active_quest_policy=str(mode_data.get("active_quest_policy") or "reuse_or_create_with_user_confirmation"),
        stage_skill_injection=str(mode_data.get("stage_skill_injection") or "active_only"),
        companion_skill_injection=str(mode_data.get("companion_skill_injection") or "on_demand"),
        runner=str(runtime_data.get("runner") or "codex"),
        allow_legacy_cli_fallback=_as_bool(runtime_data.get("allow_legacy_cli_fallback"), False),
        allow_codex_runner_fallback=_as_bool(runtime_data.get("allow_codex_runner_fallback"), False),
        use_deepscientist_memory=_as_bool(memory_data.get("use_deepscientist_memory"), True),
        sync_to_hermes_memory=_as_bool(memory_data.get("sync_to_hermes_memory"), False),
        resource_repo_root=Path(str(resource_repo_root)).expanduser() if resource_repo_root else None,
    )


def default_config_text() -> str:
    return """# By default the Codex-native adapter follows upstream `ds --here` semantics.
# Launch Codex from a project directory and DeepScientist state is stored in:
#   ./DeepScientist/
# Uncomment runtime_home only if this project intentionally needs a custom root.
# runtime_home: ./DeepScientist
mode:
  default_enabled: true
  auto_detect_research_tasks: true
  active_quest_policy: reuse_or_create_with_user_confirmation
  stage_skill_injection: active_only
  companion_skill_injection: on_demand
runtime:
  runner: codex
  allow_legacy_cli_fallback: false
  allow_codex_runner_fallback: false
state:
  # Defaults to <runtime_home>/runtime/codex-session-map.json
  # session_map_path: ./DeepScientist/runtime/codex-session-map.json
memory:
  use_deepscientist_memory: true
  sync_to_hermes_memory: false
"""
