from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import Any


def _compact_text(value: object, *, limit: int = 240) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except TypeError:
            text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _render_tool_event_text(event: dict[str, Any]) -> str:
    tool_name = str(event.get("tool_name") or event.get("mcp_tool") or "tool").strip() or "tool"
    status = str(event.get("status") or "").strip()
    if str(event.get("type") or "") == "runner.tool_call":
        args = _compact_text(event.get("args"), limit=160)
        return " ".join(part for part in [f"[tool:start] {tool_name}", args] if part).strip()

    output = _compact_text(event.get("output"), limit=160)
    summary = " ".join(part for part in [status, output] if part).strip()
    return " ".join(part for part in [f"[tool:done] {tool_name}", summary] if part).strip()


def _render_artifact_event_text(event: dict[str, Any]) -> str:
    kind = str(event.get("kind") or "artifact").strip() or "artifact"
    summary = _compact_text(
        event.get("summary") or event.get("reason") or event.get("guidance") or event.get("artifact_id"),
        limit=180,
    )
    return " ".join(part for part in [f"[artifact:{kind}]", summary] if part).strip() or "[artifact]"


def _render_status_event_text(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or event.get("event_type") or "event")
    if event_type == "runner.turn_start":
        skill_id = str(event.get("skill_id") or "").strip()
        model = str(event.get("model") or "").strip()
        return " ".join(part for part in ["[run:start]", skill_id, model] if part).strip()
    if event_type == "runner.turn_finish":
        summary = _compact_text(event.get("summary"), limit=180)
        return " ".join(part for part in ["[run:finish]", summary] if part).strip() or "[run:finish]"
    if event_type == "runner.turn_error":
        summary = _compact_text(event.get("summary"), limit=180)
        return " ".join(part for part in ["[run:error]", summary] if part).strip() or "[run:error]"
    if event_type == "runner.turn_retry_started":
        summary = _compact_text(event.get("summary"), limit=180)
        return " ".join(part for part in ["[run:retry:start]", summary] if part).strip() or "[run:retry:start]"
    if event_type == "runner.turn_retry_scheduled":
        summary = _compact_text(event.get("summary"), limit=180)
        return " ".join(part for part in ["[run:retry:wait]", summary] if part).strip() or "[run:retry:wait]"
    if event_type == "runner.turn_retry_aborted":
        summary = _compact_text(event.get("summary"), limit=180)
        return " ".join(part for part in ["[run:retry:aborted]", summary] if part).strip() or "[run:retry:aborted]"
    if event_type == "runner.turn_retry_exhausted":
        summary = _compact_text(event.get("summary"), limit=180)
        return " ".join(part for part in ["[run:retry:exhausted]", summary] if part).strip() or "[run:retry:exhausted]"
    if event_type == "quest.control":
        action = str(event.get("action") or "control").strip()
        summary = _compact_text(event.get("summary"), limit=180)
        return " ".join(part for part in [f"[quest:{action}]", summary] if part).strip()
    return _compact_text(event, limit=240)


@dataclass(frozen=True)
class ACPBridgeStatus:
    available: bool
    module_name: str
    package_name: str
    package_version: str | None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "module_name": self.module_name,
            "package_name": self.package_name,
            "package_version": self.package_version,
            "reason": self.reason,
        }


def get_acp_bridge_status() -> ACPBridgeStatus:
    package_name = "agent-client-protocol"
    module_name = "acp"
    try:
        import_module(module_name)
        try:
            package_version = version(package_name)
        except PackageNotFoundError:
            package_version = None
        return ACPBridgeStatus(
            available=True,
            module_name=module_name,
            package_name=package_name,
            package_version=package_version,
        )
    except ModuleNotFoundError as exc:
        return ACPBridgeStatus(
            available=False,
            module_name=module_name,
            package_name=package_name,
            package_version=None,
            reason=str(exc),
        )


class OptionalACPBridge:
    def __init__(self) -> None:
        self.status = get_acp_bridge_status()
        self._module = import_module(self.status.module_name) if self.status.available else None

    def is_available(self) -> bool:
        return bool(self.status.available and self._module is not None)

    def build_sdk_notification(self, *, session_id: str, event: dict[str, Any]) -> dict[str, Any] | None:
        if not self.is_available():
            return None
        acp = self._module
        event_type = str(event.get("type") or event.get("event_type") or "event")

        if event_type == "conversation.message":
            role = str(event.get("role") or "assistant")
            text = str(event.get("content") or "")
            if role == "user":
                update = acp.update_user_message_text(text)
            else:
                update = acp.update_agent_message_text(text)
        elif event_type == "runner.delta":
            update = acp.update_agent_message_text(str(event.get("text") or ""))
        elif event_type == "runner.agent_message":
            update = acp.update_agent_message_text(str(event.get("text") or ""))
        elif event_type == "runner.reasoning":
            update = acp.update_agent_thought_text(str(event.get("text") or ""))
        elif event_type == "artifact.recorded":
            update = acp.update_agent_thought_text(_render_artifact_event_text(event))
        elif event_type == "runner.tool_call" or event_type == "runner.tool_result":
            update = acp.update_agent_thought_text(_render_tool_event_text(event))
        elif event_type in {
            "runner.turn_start",
            "runner.turn_finish",
            "runner.turn_error",
            "runner.turn_retry_started",
            "runner.turn_retry_scheduled",
            "runner.turn_retry_aborted",
            "runner.turn_retry_exhausted",
        }:
            update = acp.update_agent_thought_text(_render_status_event_text(event))
        elif event_type == "quest.control":
            update = acp.update_agent_thought_text(_render_status_event_text(event))
        else:
            rendered = _render_status_event_text(event)
            update = acp.update_agent_thought_text(rendered)

        notification = acp.session_notification(session_id, update)
        if hasattr(notification, "model_dump"):
            return notification.model_dump(by_alias=True, exclude_none=True)
        if hasattr(notification, "dict"):
            return notification.dict(by_alias=True, exclude_none=True)
        return dict(notification)
