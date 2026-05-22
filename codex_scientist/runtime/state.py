"""CodexScientist native mode state mapping for Codex sessions."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import NativeConfig, load_config


def _utc_now() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _session_id_from_context(context: Any = None, **kwargs: Any) -> str:
    for value in (kwargs.get("session_id"), kwargs.get("conversation_id"), kwargs.get("thread_id")):
        if value:
            return str(value)
    if isinstance(context, dict):
        for key in ("session_id", "conversation_id", "thread_id", "chat_id"):
            if context.get(key):
                return str(context[key])
    for attr in ("session_id", "conversation_id", "thread_id", "chat_id"):
        if context is not None and getattr(context, attr, None):
            return str(getattr(context, attr))
    return "local"


class StateStore:
    def __init__(self, config: NativeConfig | None = None) -> None:
        self.config = config or load_config()
        self.path = self.config.session_map_path.expanduser()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"sessions": {}, "global": {"mode_enabled": self.config.mode_default_enabled}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"sessions": {}, "global": {"mode_enabled": self.config.mode_default_enabled}}
        if not isinstance(data, dict):
            return {"sessions": {}, "global": {"mode_enabled": self.config.mode_default_enabled}}
        data.setdefault("sessions", {})
        data.setdefault("global", {"mode_enabled": self.config.mode_default_enabled})
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + f".{uuid4().hex}.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def session(self, session_id: str = "local") -> dict[str, Any]:
        data = self._read()
        sessions = data.setdefault("sessions", {})
        item = sessions.setdefault(session_id or "local", {})
        return dict(item)

    def set_session(self, session_id: str, **updates: Any) -> dict[str, Any]:
        data = self._read()
        sessions = data.setdefault("sessions", {})
        item = dict(sessions.get(session_id or "local") or {})
        item.update({k: v for k, v in updates.items() if v is not None})
        item["updated_at"] = _utc_now()
        sessions[session_id or "local"] = item
        self._write(data)
        return item

    def set_active_quest(
        self,
        quest_id: str,
        session_id: str = "local",
        *,
        active_stage: str | None = None,
        project_root: str | None = None,
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        if project_root:
            updates["project_root"] = str(project_root)
        if active_stage:
            updates["active_stage"] = active_stage
        return self.set_session(session_id, **updates)

    def active_quest_id(self, session_id: str = "local") -> str | None:
        return None

    def legacy_active_quest_id(self, session_id: str = "local") -> str | None:
        item = self.session(session_id)
        value = str(item.get("active_quest_id") or "").strip()
        return value or None

    def active_stage(self, session_id: str = "local") -> str | None:
        value = str(self.session(session_id).get("active_stage") or "").strip()
        return value or None

    def set_active_stage(self, stage: str, session_id: str = "local") -> dict[str, Any]:
        return self.set_session(session_id, active_stage=str(stage).strip())

    def mode_enabled(self, session_id: str = "local") -> bool:
        data = self._read()
        session = dict((data.get("sessions") or {}).get(session_id or "local") or {})
        if "mode_enabled" in session:
            return bool(session.get("mode_enabled"))
        global_state = data.get("global") if isinstance(data.get("global"), dict) else {}
        return bool(global_state.get("mode_enabled", self.config.mode_default_enabled))

    def set_mode_enabled(self, enabled: bool, session_id: str = "local") -> dict[str, Any]:
        return self.set_session(session_id, mode_enabled=bool(enabled))


def session_id_from_context(context: Any = None, **kwargs: Any) -> str:
    return _session_id_from_context(context, **kwargs)
