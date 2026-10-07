from __future__ import annotations

import argparse
import json
import sqlite3
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

try:
    from .store import IdeaSparkStore, default_db_path, with_retry
    from .tools import _latest_gate, _open_need_summary, _room_cursors
except ImportError:  # source-root script execution
    from store import IdeaSparkStore, default_db_path, with_retry
    from tools import _latest_gate, _open_need_summary, _room_cursors


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_POLL_INTERVAL_S = 0.75
DEFAULT_LIMIT = 200
ROOM_DELETE_TABLES = ("artifact_links", "gates", "open_needs", "messages", "participants", "artifacts")


def _loads(value: str | None, default):
    if not value:
        return default
    return json.loads(value)


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _plain_content_text(value: Any) -> str:
    """Return human-readable dashboard text without JSON wrapper noise."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(f"- {_plain_content_text(item)}" for item in value)
    if isinstance(value, dict):
        if set(value) == {"text"}:
            return _plain_content_text(value.get("text"))
        if "text" in value and isinstance(value.get("text"), str):
            rest = {key: item for key, item in value.items() if key != "text"}
            rest_text = _plain_content_text(rest) if rest else ""
            return value["text"] if not rest_text else f"{value['text']}\n\n{rest_text}"
        lines = []
        for key, item in value.items():
            rendered = _plain_content_text(item)
            if "\n" in rendered:
                rendered = "\n".join("  " + line if line else "" for line in rendered.splitlines())
                lines.append(f"**{key}**:\n{rendered}")
            else:
                lines.append(f"**{key}**: {rendered}")
        return "\n".join(lines)
    return str(value)


def _normalized_tags(*groups: Any) -> list[str]:
    tags: set[str] = set()
    for group in groups:
        if not group:
            continue
        if isinstance(group, str):
            tags.add(group)
            continue
        if isinstance(group, dict):
            group = group.get("tags") or group.get("tag") or []
        if isinstance(group, (list, tuple, set)):
            for item in group:
                if item is not None and str(item).strip():
                    tags.add(str(item).strip())
    return sorted(tags)


class DashboardReader:
    """Read-only Idea-Spark ledger reader for the local dashboard."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path is not None else default_db_path()

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise FileNotFoundError(self.db_path)
        uri = f"file:{quote(str(self.db_path.resolve()))}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    @staticmethod
    def _room_dict(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["metadata"] = _loads(item.pop("metadata_json"), {})
        return item

    @staticmethod
    def _participant_dict(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["metadata"] = _loads(item.pop("metadata_json"), {})
        return item

    @staticmethod
    def _message_dict(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["artifact_ids"] = _loads(item.pop("artifact_ids_json"), [])
        item["content_text"] = item.get("content") or ""
        item["tags"] = _normalized_tags(
            "kind:message",
            f"agent:{item.get('agent_id')}",
            f"role:{item.get('role')}" if item.get("role") else None,
            f"phase:{item.get('phase')}" if item.get("phase") else None,
            f"round:{item.get('round_id')}" if item.get("round_id") else None,
        )
        return item

    @staticmethod
    def _artifact_dict(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item.pop("_rowid", None)
        item["content"] = _loads(item.pop("content_json"), {})
        item["metadata"] = _loads(item.pop("metadata_json"), {})
        item["content_text"] = _plain_content_text(item["content"])
        phase = item["metadata"].get("phase")
        item["phase"] = phase
        item["round_id"] = item["metadata"].get("round_id")
        item["tags"] = _normalized_tags(
            item["metadata"],
            "kind:artifact",
            f"artifact:{item.get('artifact_type')}",
            f"status:{item.get('status')}",
            f"agent:{item.get('producer_agent')}",
            f"phase:{phase}" if phase else None,
        )
        return item

    @staticmethod
    def _gate_dict(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["input_artifact_ids"] = _loads(item.pop("input_artifact_ids_json"), [])
        item["score"] = _loads(item.pop("score_json"), {})
        item["metadata"] = _loads(item.pop("metadata_json"), {})
        phase = item["metadata"].get("phase")
        item["phase"] = phase
        item["round_id"] = item["metadata"].get("round_id")
        item["content_text"] = item.get("rationale") or ""
        item["tags"] = _normalized_tags(
            item["metadata"],
            "kind:gate",
            f"gate:{item.get('gate_type')}",
            f"decision:{item.get('decision')}",
            f"agent:{item.get('created_by')}" if item.get("created_by") else None,
            f"phase:{phase}" if phase else None,
        )
        return item

    @staticmethod
    def _need_dict(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["metadata"] = _loads(item.pop("metadata_json"), {})
        item["content_text"] = item.get("rationale") or ""
        phase = item["metadata"].get("phase")
        item["phase"] = phase
        item["round_id"] = item["metadata"].get("round_id")
        actor = item.get("created_by") or item.get("claimed_by_agent")
        item["tags"] = _normalized_tags(
            item["metadata"],
            "kind:open_need",
            f"need:{item.get('target_artifact_type')}",
            f"status:{item.get('status')}",
            f"agent:{actor}" if actor else None,
            f"phase:{phase}" if phase else None,
        )
        return item

    @staticmethod
    def _expected_agents(room: dict[str, Any]) -> list[str]:
        metadata = room.get("metadata") or {}
        return [str(agent) for agent in metadata.get("expected_agents", [])]

    @staticmethod
    def _counts(conn: sqlite3.Connection, room_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for table in ("participants", "messages", "artifacts", "gates"):
            counts[table] = conn.execute(f"select count(*) as n from {table} where room_id = ?", (room_id,)).fetchone()["n"]
        counts["open_needs"] = conn.execute(
            "select count(*) as n from open_needs where room_id = ? and status in ('open', 'claimed')",
            (room_id,),
        ).fetchone()["n"]
        counts["total_needs"] = conn.execute(
            "select count(*) as n from open_needs where room_id = ?",
            (room_id,),
        ).fetchone()["n"]
        return counts

    @staticmethod
    def _current_phase(latest_gate: dict[str, Any] | None, timeline: list[dict[str, Any]]) -> str | None:
        if latest_gate:
            phase = (latest_gate.get("metadata") or {}).get("phase")
            if phase:
                return str(phase)
        for event in reversed(timeline):
            if event.get("phase"):
                return str(event["phase"])
        return None

    def list_rooms(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        with self._connect() as conn:
            rows = conn.execute("select * from rooms order by created_at desc, room_id desc limit ?", (limit,)).fetchall()
            rooms = []
            for row in rows:
                room = self._room_dict(row)
                room["expected_agents"] = self._expected_agents(room)
                room["counts"] = self._counts(conn, room["room_id"])
                rooms.append(room)
            return rooms

    def room_snapshot(self, room_id: str, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        if not self.db_path.exists():
            return {"success": False, "error": "database not found", "room_id": room_id}
        with self._connect() as conn:
            room_row = conn.execute("select * from rooms where room_id = ?", (room_id,)).fetchone()
            if not room_row:
                return {"success": False, "error": "unknown room_id", "room_id": room_id}

            room = self._room_dict(room_row)
            participants = [
                self._participant_dict(row)
                for row in conn.execute(
                    "select * from participants where room_id = ? order by coalesce(role, ''), agent_id",
                    (room_id,),
                ).fetchall()
            ]
            message_rows = conn.execute(
                """
                select * from (
                    select * from messages where room_id = ? order by message_id desc limit ?
                ) order by message_id
                """,
                (room_id, limit),
            ).fetchall()
            artifact_rows = conn.execute(
                """
                select * from (
                    select rowid as _rowid, * from artifacts where room_id = ? order by rowid desc limit ?
                ) order by _rowid
                """,
                (room_id, limit),
            ).fetchall()
            gate_rows = conn.execute(
                "select * from gates where room_id = ? order by created_at, gate_id limit ?",
                (room_id, limit),
            ).fetchall()
            need_rows = conn.execute(
                "select * from open_needs where room_id = ? order by created_at, need_id limit ?",
                (room_id, limit),
            ).fetchall()

            messages = [self._message_dict(row) for row in message_rows]
            artifacts = [self._artifact_dict(row) for row in artifact_rows]
            gates = [self._gate_dict(row) for row in gate_rows]
            open_needs = [self._need_dict(row) for row in need_rows]
            counts = self._counts(conn, room_id)
            latest_gate = _latest_gate(conn, room_id)
            open_need_summary = _open_need_summary(conn, room_id)
            cursor = {**counts, **_room_cursors(conn, room_id)}

        expected = self._expected_agents(room)
        joined = {participant["agent_id"] for participant in participants}
        missing = [agent for agent in expected if agent not in joined]
        timeline = self._timeline(messages, artifacts, gates, open_needs)
        filter_options = self._filter_options(participants, timeline)
        current_phase = self._current_phase(latest_gate, timeline)
        return {
            "success": True,
            "room": room,
            "expected_agents": expected,
            "missing_expected_agents": missing,
            "participants": participants,
            "messages": messages,
            "artifacts": artifacts,
            "gates": gates,
            "open_needs": open_needs,
            "timeline": timeline,
            "filter_options": filter_options,
            "counts": counts,
            "latest_gate": latest_gate,
            "has_terminal_gate": room.get("status") == "gated",
            "open_need_summary": open_need_summary,
            "current_phase": current_phase,
            "cursor": cursor,
            "db_path": str(self.db_path),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    @staticmethod
    def _filter_options(participants: list[dict[str, Any]], timeline: list[dict[str, Any]]) -> dict[str, list[str]]:
        agents = {participant["agent_id"] for participant in participants}
        kinds = set()
        tags: set[str] = set()
        artifact_types = set()
        phases = set()
        statuses = set()
        for event in timeline:
            if event.get("actor"):
                agents.add(str(event["actor"]))
            if event.get("kind"):
                kinds.add(str(event["kind"]))
            if event.get("role") and event.get("kind") == "artifact":
                artifact_types.add(str(event["role"]))
            if event.get("phase"):
                phases.add(str(event["phase"]))
            if event.get("status"):
                statuses.add(str(event["status"]))
            for tag in event.get("tags", []):
                tags.add(str(tag))
        return {
            "agents": sorted(agents),
            "kinds": sorted(kinds),
            "tags": sorted(tags),
            "artifact_types": sorted(artifact_types),
            "phases": sorted(phases),
            "statuses": sorted(statuses),
        }

    @staticmethod
    def _timeline(
        messages: list[dict[str, Any]],
        artifacts: list[dict[str, Any]],
        gates: list[dict[str, Any]],
        open_needs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for message in messages:
            events.append(
                {
                    "kind": "message",
                    "id": f"message:{message['message_id']}",
                    "created_at": message["created_at"],
                    "actor": message["agent_id"],
                    "role": message.get("role"),
                    "round_id": message.get("round_id"),
                    "phase": message.get("phase"),
                    "title": "message",
                    "content": message["content"],
                    "content_text": message.get("content_text") or message.get("content") or "",
                    "artifact_ids": message.get("artifact_ids", []),
                    "tags": message.get("tags", []),
                }
            )
        for artifact in artifacts:
            events.append(
                {
                    "kind": "artifact",
                    "id": artifact["artifact_id"],
                    "created_at": artifact["created_at"],
                    "actor": artifact["producer_agent"],
                    "role": artifact["artifact_type"],
                    "round_id": artifact.get("round_id"),
                    "phase": artifact.get("phase"),
                    "title": artifact.get("title") or artifact["artifact_type"],
                    "status": artifact["status"],
                    "content": artifact.get("content"),
                    "content_text": artifact.get("content_text") or _plain_content_text(artifact.get("content")),
                    "tags": artifact.get("tags", []),
                }
            )
        for gate in gates:
            events.append(
                {
                    "kind": "gate",
                    "id": gate["gate_id"],
                    "created_at": gate["created_at"],
                    "actor": gate.get("created_by"),
                    "role": gate["gate_type"],
                    "round_id": gate.get("round_id"),
                    "phase": gate.get("phase"),
                    "title": f"gate: {gate['decision']}",
                    "content": gate["rationale"],
                    "content_text": gate.get("content_text") or gate.get("rationale") or "",
                    "input_artifact_ids": gate.get("input_artifact_ids", []),
                    "score": gate.get("score", {}),
                    "tags": gate.get("tags", []),
                }
            )
        for need in open_needs:
            events.append(
                {
                    "kind": "open_need",
                    "id": need["need_id"],
                    "created_at": need["created_at"],
                    "actor": need.get("created_by") or need.get("claimed_by_agent"),
                    "role": need["target_artifact_type"],
                    "round_id": need.get("round_id"),
                    "phase": need.get("phase"),
                    "title": need["query"],
                    "status": need["status"],
                    "pressure_score": need["pressure_score"],
                    "content": need["rationale"],
                    "content_text": need.get("content_text") or need.get("rationale") or "",
                    "tags": need.get("tags", []),
                }
            )
        order = {"message": 0, "artifact": 1, "gate": 2, "open_need": 3}
        return sorted(events, key=lambda event: (event.get("created_at") or "", order.get(event["kind"], 99), event["id"]))


class DashboardMutator:
    """Narrow writable dashboard operations. Read paths stay in DashboardReader."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path is not None else default_db_path()

    def delete_room(self, room_id: str) -> dict[str, Any]:
        if not self.db_path.exists():
            return {"success": False, "error": "database not found", "room_id": room_id}

        def run() -> dict[str, Any]:
            store = IdeaSparkStore(self.db_path)
            with store.connect() as conn:
                row = conn.execute("select room_id from rooms where room_id = ?", (room_id,)).fetchone()
                if not row:
                    return {"success": False, "error": "unknown room_id", "room_id": room_id}
                deleted: dict[str, int] = {}
                for table in ROOM_DELETE_TABLES:
                    cur = conn.execute(f"delete from {table} where room_id = ?", (room_id,))
                    deleted[table] = cur.rowcount if cur.rowcount is not None else 0
                cur = conn.execute("delete from rooms where room_id = ?", (room_id,))
                deleted["rooms"] = cur.rowcount if cur.rowcount is not None else 0
                return {"success": True, "room_id": room_id, "deleted": deleted}

        return with_retry(run)


def _json_response(handler: BaseHTTPRequestHandler, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
    data = _json_dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(data)


def _text_response(handler: BaseHTTPRequestHandler, text: str, content_type: str = "text/html; charset=utf-8") -> None:
    data = text.encode("utf-8")
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(data)


def _not_found(handler: BaseHTTPRequestHandler) -> None:
    _json_response(handler, {"success": False, "error": "not found"}, HTTPStatus.NOT_FOUND)


def _index_html() -> str:
    return _page_shell(room_id=None)


def _room_html(room_id: str) -> str:
    return _page_shell(room_id=room_id)


def _page_shell(room_id: str | None) -> str:
    room_json = json.dumps(room_id)
    return rf"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Delphi</title>
  <style>

    :root {{
      color-scheme: dark;
      --bg: #232323; --sidebar: #151515; --bubble: #303030;
      --ink: #ececea; --muted: #aaa; --line: #3a3a3a; --line-soft: #303030;
      --accent: #a38bff; --accent-2: #58bca8; --bad: #ff897d; --ok: #74c69d;
      --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      --body: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    [hidden] {{ display: none !important; }}
    body {{ margin: 0; height: 100dvh; overflow: hidden; background: var(--bg); color: var(--ink); font-family: var(--body); font-size: 16px; line-height: 1.5; }}
    button, input, select {{ font: inherit; }}
    button, a, input, select, summary {{ -webkit-tap-highlight-color: transparent; }}
    button {{ cursor: pointer; }}
    button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 3px; }}
    button:disabled {{ cursor: default; opacity: .45; }}
    svg {{ flex-shrink: 0; }}
    .sr-only {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }}
    .app-shell {{ display: grid; grid-template-columns: clamp(280px, 26vw, 380px) minmax(0, 1fr); width: 100%; height: 100dvh; min-height: 0; overflow: hidden; background: var(--bg); position: relative; }}
    .sidebar {{ display: flex; flex-direction: column; min-height: 0; background: var(--sidebar); border-right: 1px solid var(--line); }}
    .sidebar-top {{ height: 78px; flex-shrink: 0; display: flex; align-items: center; gap: 14px; padding: 0 22px; }}
    .window-dots {{ display: flex; gap: 7px; }}
    .window-dots i {{ width: 10px; height: 10px; border-radius: 50%; background: #ff6058; }}
    .window-dots i:nth-child(2) {{ background: #febc2e; }}
    .window-dots i:nth-child(3) {{ background: #28c840; }}
    .brand {{ font-size: 18px; font-weight: 650; letter-spacing: -.3px; }}
    .icon-button {{ display: grid; place-items: center; width: 40px; height: 40px; flex-shrink: 0; padding: 0; border: 0; border-radius: 9px; background: transparent; color: var(--muted); }}
    .icon-button:hover, .icon-button[aria-pressed="true"] {{ background: #ffffff0a; color: var(--ink); }}
    .sidebar-top .icon-button {{ margin-left: auto; font-size: 26px; font-weight: 300; }}
    .search-box {{ display: flex; align-items: center; gap: 10px; border: 1px solid #404040; background: #252525; border-radius: 13px; padding: 11px 13px; }}
    .sidebar-search {{ margin: 0 18px 14px; }}
    .search-box svg {{ width: 20px; height: 20px; color: var(--muted); }}
    .search-box input {{ width: 100%; min-width: 0; padding: 0; border: 0; outline: none; background: transparent; color: var(--ink); font-size: 16px; }}
    .search-box:focus-within {{ border-color: #9280cd; }}
    .search-box input::placeholder {{ color: var(--muted); }}
    .navigation {{ flex: 1; min-height: 0; padding: 0 14px 16px; overflow-y: auto; scrollbar-width: thin; scrollbar-color: #444 transparent; }}
    .nav-heading {{ display: flex; align-items: center; justify-content: space-between; min-height: 36px; padding: 0 10px; gap: 8px; }}
    .nav-heading h2 {{ margin: 0; color: var(--muted); font-size: 16px; letter-spacing: .6px; text-transform: uppercase; font-weight: 600; }}
    .nav-count {{ color: var(--muted); font-size: 16px; }}
    .room-tools {{ max-width: 150px; position: relative; color: var(--muted); font-size: 16px; }}
    .room-tools summary {{ cursor: pointer; padding: 6px 0; }}
    .room-tools select {{ position: absolute; right: 0; z-index: 4; width: 150px; margin-top: 8px; padding: 9px; background: #262626; color: var(--ink); border: 1px solid var(--line); border-radius: 8px; }}
    .room-section h3, .room-folder-header {{ display: flex; gap: 8px; align-items: center; margin: 12px 10px 5px; font-size: 16px; letter-spacing: .8px; color: var(--muted); font-weight: 500; }}
    .room-folder-header {{ cursor: context-menu; }}
    .room-folder-header::before {{ content: '▾'; }}
    .room-entry {{ border-radius: 13px; cursor: context-menu; }}
    .room-link, .agent-entry {{ display: flex; align-items: center; gap: 12px; width: 100%; padding: 12px 10px; border: 0; border-radius: 13px; color: var(--ink); text-decoration: none; background: transparent; text-align: left; }}
    .room-link:hover, .agent-entry:hover, .room-entry.menu-open {{ background: #ffffff06; }}
    .room-link.active, .agent-entry.active {{ background: #292929; }}
    .nav-body {{ flex: 1; min-width: 0; }}
    .room-title-row, .agent-title-row {{ display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }}
    .room-title, .agent-name {{ min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 16px; font-weight: 560; }}
    .room-entry.pinned .room-title::before {{ content: '★ '; color: var(--accent); }}
    .nav-time {{ color: var(--muted); font-size: 16px; white-space: nowrap; }}
    .nav-preview {{ margin-top: 4px; font-size: 16px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 1.5; }}
    .current-room-badge {{ width: 5px; height: 5px; flex-shrink: 0; border-radius: 50%; background: var(--accent-2); font-size: 0; }}
    .agents-section {{ margin-top: 18px; }}
    .avatar {{ width: 39px; height: 39px; flex: 0 0 39px; display: inline-block; position: relative; border-radius: 48% 52% 44% 56%; background: #59bca8; }}
    .avatar::before, .avatar::after {{ content: ''; position: absolute; top: 10px; width: 3px; height: 8px; border-radius: 3px; background: #172523; transform: rotate(-25deg); }}
    .avatar::before {{ right: 12px; }} .avatar::after {{ right: 7px; }}
    .avatar.tone-1 {{ background: #f5a234; border-radius: 50%; }}
    .avatar.tone-2 {{ background: #7164f5; border-radius: 12px; transform: rotate(-9deg); }}
    .avatar.tone-3 {{ background: #9264f5; border-radius: 40% 53% 42% 45%; transform: rotate(-17deg); }}
    .avatar.tone-4 {{ background: #4189ed; border-radius: 50%; }}
    .avatar.tone-5 {{ background: #ed7839; border-radius: 50% 46% 48% 44%; }}
    .avatar.room-avatar {{ background: transparent; border-radius: 0; }}
    .avatar.room-avatar::before, .avatar.room-avatar::after {{ display: none; }}
    .mini-avatar {{ position: absolute; width: 23px; height: 23px; border-radius: 50%; background: #59bca8; top: 1px; left: 9px; border: 2px solid var(--sidebar); }}
    .mini-avatar:nth-child(2) {{ top: 15px; left: 0; background: #7164f5; }}
    .mini-avatar:nth-child(3) {{ top: 15px; left: 18px; background: #9264f5; }}
    .sidebar-footer {{ display: flex; align-items: center; gap: 11px; padding: 17px 22px; border-top: 1px solid #222; }}
    .workspace-icon {{ display: grid; place-items: center; flex-shrink: 0; width: 40px; height: 40px; border-radius: 50%; background: #292929; color: #aaa; font-size: 16px; }}
    .workspace-title {{ font-size: 16px; }} .workspace-subtitle {{ margin-top: 3px; color: var(--muted); font-size: 16px; }}
    .conversation {{ display: flex; flex-direction: column; min-width: 0; min-height: 0; }}
    .conversation-header {{ display: flex; align-items: center; flex-shrink: 0; gap: 12px; min-height: 78px; padding: 14px 24px; border-bottom: 1px solid var(--line); }}
    .conversation-header .avatar {{ width: 30px; height: 30px; flex-basis: 30px; }}
    .conversation-header .mini-avatar {{ width: 18px; height: 18px; border-color: var(--bg); left: 6px; }}
    .conversation-header .mini-avatar:nth-child(2) {{ top: 11px; left: 0; }} .conversation-header .mini-avatar:nth-child(3) {{ top: 11px; left: 14px; }}
    .conversation-heading {{ flex: 1; min-width: 0; }}
    #room-heading {{ margin: 0; font-size: 18px; font-weight: 570; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; letter-spacing: -.2px; }}
    #conversation-subtitle {{ font-size: 16px; color: var(--muted); margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .badge {{ display: flex; align-items: center; gap: 6px; font-size: 16px; color: var(--muted); white-space: nowrap; }}
    .badge::before {{ content: ''; width: 7px; height: 7px; border-radius: 50%; background: #888; }}
    .badge.ok::before {{ background: var(--ok); }}
    .language-switch {{ display: flex; padding: 2px; border: 1px solid var(--line); border-radius: 7px; }}
    .lang-button {{ min-width: 40px; min-height: 36px; border: 0; border-radius: 5px; padding: 6px 10px; background: transparent; color: var(--muted); font-size: 16px; }}
    .lang-button.active {{ background: #383838; color: var(--ink); }}
    .controls {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; flex-shrink: 0; margin: 0; padding: 14px 24px; border-bottom: 1px solid var(--line); }}
    .control-field {{ display: grid; gap: 5px; min-width: 0; }}
    .control-field label, .check-field {{ color: var(--muted); font-size: 16px; }}
    .control-field select {{ width: 100%; border: 1px solid var(--line); border-radius: 6px; background: #292929; color: var(--ink); min-height: 40px; padding: 8px 10px; font-size: 16px; }}
    .check-field {{ min-height: 32px; display: flex; align-items: center; gap: 6px; grid-column: 1 / -1; }}
    .check-field input {{ width: 18px; height: 18px; margin: 0; accent-color: var(--accent); }}
    .room-details {{ flex-shrink: 0; padding: 8px 24px; border-bottom: 1px solid var(--line); color: var(--muted); font-size: 16px; }}
    .room-details > summary {{ cursor: pointer; min-height: 32px; padding: 4px 0; }}
    .room-details[open] {{ max-height: 24%; overflow: auto; }}
    .room-topic {{ margin: 12px 0; color: #b6b6b6; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }}
    .stats {{ display: flex; flex-wrap: wrap; gap: 16px; margin: 12px 0; }}
    .stat strong {{ margin-right: 5px; color: var(--ink); font-size: 16px; }}
    .stat span {{ font-size: 16px; }}
    .status-line {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }}
    .pill, .tag {{ border: 1px solid var(--line); border-radius: 6px; padding: 3px 7px; color: var(--muted); font-size: 16px; overflow-wrap: anywhere; }}
    .pill.hot {{ color: #c3b3ff; border-color: #5c5076; }} .pill.ok {{ color: var(--ok); }}
    .conversation-scroll {{ flex: 1; min-height: 0; overflow-y: auto; padding: 22px 28px; scrollbar-width: thin; scrollbar-color: #444 transparent; }}
    .timeline {{ display: flex; flex-direction: column; gap: 18px; min-height: 100%; }}
    .day-divider {{ text-align: center; padding: 7px 0; color: #8f8f8f; font-size: 16px; }}
    .event {{ display: flex; flex-direction: column; align-items: flex-start; gap: 6px; width: 100%; }}
    .event-head {{ display: flex; gap: 9px; align-items: baseline; max-width: 88%; padding: 0 4px; color: var(--muted); font-size: 16px; }}
    .event-actor {{ color: #aaa; font-weight: 500; }}
    .event-meta {{ font-size: 16px; color: var(--muted); }}
    .event-bubble {{ max-width: 88%; min-width: 0; padding: 13px 17px; border-radius: 20px; background: var(--bubble); }}
    .event.outgoing {{ align-items: flex-end; }}
    .event.outgoing .event-bubble {{ background: #e9e9e6; color: #1e1e1e; }}
    .event.outgoing .event-markdown {{ color: #1e1e1e; }}
    .event.outgoing .event-bubble .event-meta {{ color: #656565; }}
    .event.outgoing .event-kind, .event.outgoing .tag {{ color: #5f596a; border-color: #c8c6ca; }}
    .event.outgoing .event-markdown code {{ color: #645083; }}
    .event.outgoing .event-markdown th {{ color: #4c4164; }}
    .event-kind {{ color: #b4a2ee; font-size: 16px; font-weight: 550; letter-spacing: .2px; }}
    .event-title {{ margin: 5px 0 9px; font-weight: 600; font-size: 16px; overflow-wrap: anywhere; }}
    .artifact-details > summary {{ cursor: pointer; min-height: 32px; color: #c7b9ff; font-size: 16px; line-height: 1.6; overflow-wrap: anywhere; }}
    .artifact-details[open] > summary {{ margin-bottom: 10px; }}
    .event.gate .event-kind {{ color: #e9b379; }} .event.open_need .event-kind {{ color: #b6a1ec; }}
    .event-tags {{ display: flex; gap: 5px; flex-wrap: wrap; margin-top: 10px; }}
    .event-markdown {{ font-size: 16px; line-height: 1.65; color: #e6e6e4; overflow-wrap: anywhere; }}
    .event-markdown p {{ margin: 0 0 10px; }} .event-markdown p:last-child {{ margin-bottom: 0; }}
    .event-markdown h1, .event-markdown h2, .event-markdown h3 {{ margin: 10px 0 7px; font-size: 16px; line-height: 1.4; }}
    .event-markdown ul, .event-markdown ol {{ margin: 6px 0 9px; padding-left: 20px; }}
    .event-markdown li {{ margin: 4px 0; }}
    .event-markdown blockquote {{ margin: 8px 0; padding: 4px 10px; border-left: 2px solid #9481bf; }}
    .event-markdown pre {{ max-width: 100%; margin: 8px 0; padding: 10px; border-radius: 8px; background: #0002; overflow-x: auto; }}
    .event-markdown code {{ font-family: var(--mono); color: #c6b6fa; font-size: 1em; }}
    .event-markdown .table-wrap {{ max-width: 100%; overflow-x: auto; margin: 8px 0; border: 1px solid #7773; border-radius: 7px; }}
    .event-markdown table {{ width: 100%; min-width: 460px; border-collapse: collapse; font-size: 16px; }}
    .event-markdown th, .event-markdown td {{ padding: 8px 10px; border-bottom: 1px solid #7773; text-align: left; }}
    .event-markdown th {{ color: #c6b6fa; }} .event-markdown tr:last-child td {{ border-bottom: 0; }}
    .agent-group {{ display: flex; flex-direction: column; gap: 18px; }}
    .agent-group h3 {{ margin: 12px 0 0; font-size: 16px; font-weight: 500; color: var(--accent); }}
    .conversation-footer {{ flex-shrink: 0; padding: 0 24px 20px; }}
    .pagination {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 0; }}
    .small {{ font-size: 16px; color: var(--muted); overflow-wrap: anywhere; }}
    .pager-buttons {{ display: flex; gap: 5px; }}
    .pager-buttons button {{ border: 0; border-radius: 5px; background: transparent; color: var(--muted); font-size: 16px; min-height: 36px; padding: 6px 10px; }}
    .pager-buttons button:not(:disabled):hover {{ color: var(--ink); background: #ffffff08; }}
    #timeline-latest.active {{ color: var(--accent-2); }}
    .conversation-search {{ border-radius: 24px; padding: 12px 15px; background: transparent; }}
    .conversation-search input {{ font-size: 16px; }}
    .conversation-search .icon-button {{ width: 36px; height: 36px; font-size: 18px; }}
    .empty {{ padding: 20px 12px; color: var(--muted); font-size: 16px; line-height: 1.7; }}
    .timeline > .empty {{ margin: auto; max-width: 330px; text-align: center; }}
    .context-menu {{ position: fixed; z-index: 50; min-width: 178px; display: grid; gap: 2px; padding: 6px; border: 1px solid var(--line); border-radius: 10px; background: #242424; box-shadow: 0 18px 45px #0005; }}
    .context-menu button {{ width: 100%; border: 0; border-radius: 5px; background: transparent; color: var(--ink); font-size: 16px; text-align: left; min-height: 40px; padding: 8px 10px; }}
    .context-menu button:hover {{ background: #ffffff0c; }}
    .context-menu button.danger {{ color: var(--bad); }}
    .mobile-toggle, .sidebar-backdrop {{ display: none; }}
    @media (max-width: 1050px) {{ .app-shell {{ grid-template-columns: 280px minmax(0, 1fr); }} .conversation-header {{ gap: 8px; padding: 14px 18px; }} }}
    @media (max-width: 740px) {{
      .app-shell {{ display: block; }}
      .conversation {{ height: 100%; }} .sidebar {{ position: absolute; top: 0; bottom: 0; left: 0; width: min(320px, 86vw); z-index: 25; transform: translateX(-100%); transition: transform .18s ease; }}
      .sidebar-open .sidebar {{ transform: translateX(0); }} .sidebar-open .sidebar-backdrop {{ display: block; position: absolute; inset: 0; z-index: 24; border: 0; background: #0008; }}
      .mobile-toggle {{ display: grid; }} .conversation-header {{ padding: 12px; min-height: 64px; }} .conversation-heading {{ max-width: calc(100% - 160px); }}
      #conversation-avatar {{ display: none; }} #room-heading {{ font-size: 16px; }} .conversation-scroll {{ padding: 18px 14px; }}
      .event-bubble, .event-head {{ max-width: 94%; }} .event-markdown {{ font-size: 16px; }} .conversation-footer {{ padding: 0 14px 14px; }}
      .controls {{ grid-template-columns: 1fr 1fr; padding: 12px 14px; }} .room-details {{ padding: 8px 14px; }} .pagination {{ align-items: flex-start; }}
      .pager-buttons {{ flex-shrink: 0; }} .language-switch {{ border: 0; }} .lang-button {{ padding: 4px; }}
    }}
    @media (prefers-reduced-motion: reduce) {{ .sidebar {{ transition: none; }} }}
  </style>
</head>
<body>
  <main class="app-shell" id="app-shell">
    <button class="sidebar-backdrop" id="sidebar-backdrop" type="button" data-i18n-aria="closeNavigation" tabindex="-1"></button>
    <aside class="sidebar" id="sidebar" aria-label="Rooms and agents">
      <div class="sidebar-top">
        <span class="window-dots" aria-hidden="true"><i></i><i></i><i></i></span>
        <span class="brand">Delphi</span>
        <button class="icon-button" id="new-folder" type="button" data-i18n-aria="createFolder">+</button>
      </div>
      <label class="search-box sidebar-search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg>
        <span class="sr-only" data-i18n="navigationSearch">Search rooms and agents</span>
        <input id="navigation-search" type="search" autocomplete="off" data-i18n-placeholder="navigationSearch" placeholder="Search rooms and agents">
      </label>
      <nav class="navigation" aria-label="Research conversations">
        <div class="nav-heading">
          <h2 data-i18n="roomsHeading">Rooms</h2>
          <details class="room-tools">
            <summary data-i18n="groupRoomsLabel">Group rooms</summary>
            <label class="sr-only" for="room-group-mode" data-i18n="groupRoomsLabel">Group rooms</label>
            <select id="room-group-mode">
              <option value="none" data-i18n="groupRoomsNone">No grouping</option>
              <option value="status" data-i18n="groupRoomsStatus">Status</option>
              <option value="creator" data-i18n="groupRoomsCreator">Creator</option>
              <option value="protocol" data-i18n="groupRoomsProtocol">Protocol</option>
              <option value="day" data-i18n="groupRoomsDay">Created day</option>
            </select>
          </details>
        </div>
        <div class="rooms" id="rooms"></div>
        <section class="agents-section" id="agents-section" hidden>
          <div class="nav-heading"><h2 data-i18n="agentsHeading">Agents in this room</h2><span id="agent-count" class="nav-count"></span></div>
          <div id="agents" class="agents"></div>
        </section>
      </nav>
      <div class="sidebar-footer"><span class="workspace-icon" aria-hidden="true">D</span><div><div class="workspace-title" data-i18n="workspaceTitle">Research workspace</div><div class="workspace-subtitle" data-i18n="workspaceSubtitle">Idea-Spark · Delphi</div></div></div>
    </aside>
    <section class="conversation" aria-label="Conversation">
      <header class="conversation-header">
        <button class="icon-button mobile-toggle" id="navigation-toggle" type="button" aria-controls="sidebar" aria-expanded="false" data-i18n-aria="openNavigation">☰</button>
        <div id="conversation-avatar" aria-hidden="true"></div>
        <div class="conversation-heading"><h1 id="room-heading" data-i18n="selectRoom">Select a room</h1><div id="conversation-subtitle"></div></div>
        <span id="connection" class="badge" role="status">connecting</span>
        <div id="language-switch" class="language-switch" role="group" aria-label="Language">
          <button type="button" class="lang-button" data-lang-option="en" aria-pressed="false">EN</button>
          <button type="button" class="lang-button" data-lang-option="zh" aria-pressed="false">中文</button>
        </div>
        <button class="icon-button" id="filter-toggle" type="button" aria-controls="timeline-controls" aria-pressed="false" data-i18n-aria="filterToggle"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2" fill="#232323"/><circle cx="15" cy="17" r="2" fill="#232323"/></svg></button>
      </header>
      <div id="timeline-controls" class="controls" hidden>
        <div class="control-field"><label for="kind-filter" data-i18n="kindFilterLabel">Kind</label><select id="kind-filter"></select></div>
        <div class="control-field"><label for="agent-filter" data-i18n="agentFilterLabel">Subagent</label><select id="agent-filter"></select></div>
        <div class="control-field"><label for="tag-filter" data-i18n="tagFilterLabel">Tag</label><select id="tag-filter"></select></div>
        <div class="control-field"><label for="page-size" data-i18n="pageSizeLabel">Page size</label><select id="page-size"><option value="10">10</option><option value="20">20</option><option value="50" selected>50</option><option value="100">100</option></select></div>
        <label class="check-field" for="group-by-agent"><input id="group-by-agent" type="checkbox"><span data-i18n="groupByAgentLabel">Group by subagent</span></label>
      </div>
      <details id="room-details" class="room-details" hidden>
        <summary id="room-overview-label" data-i18n="roomOverview">Room overview</summary>
        <div id="room-topic" class="room-topic"></div><div id="summary"></div><div id="status-line" class="status-line"></div>
        <div id="discussion-state" class="status-line"><span class="pill" id="current-phase"></span><span class="pill" id="latest-gate"></span><span class="pill" id="open-need-summary"></span></div>
      </details>
      <div class="conversation-scroll" id="conversation-scroll" tabindex="0" data-i18n-aria="conversationLabel">
        <div id="timeline" class="timeline"><div class="empty" data-i18n="welcomeMessage">Choose a room to follow the discussion, or select an agent to inspect its work.</div></div>
      </div>
      <footer class="conversation-footer">
        <div id="timeline-pagination" class="pagination" hidden><span id="page-info" class="small"></span><div class="pager-buttons"><button id="page-prev" type="button" data-i18n="prevPage">Prev</button><button id="page-next" type="button" data-i18n="nextPage">Next</button><button id="timeline-latest" type="button" data-i18n="latestMessages">Latest</button></div></div>
        <label class="search-box conversation-search">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg>
          <span class="sr-only" data-i18n="conversationSearch">Search this conversation</span>
          <input id="timeline-search" type="search" autocomplete="off" data-i18n-placeholder="conversationSearch" placeholder="Search this conversation">
        </label>
      </footer>
    </section>
    <div id="room-area-menu" class="context-menu" role="menu" hidden><button id="menu-create-folder" type="button" role="menuitem" data-i18n="createFolder">New folder</button></div>
    <div id="room-context-menu" class="context-menu" role="menu" hidden><button id="menu-pin-room" type="button" role="menuitem" data-i18n="pinRoom">Pin</button><button id="menu-add-room-folder" type="button" role="menuitem" data-i18n="addToFolder">Add to group</button><button id="menu-delete-room" class="danger" type="button" role="menuitem" data-i18n="deleteRoom">Delete room</button></div>
    <div id="room-folder-menu" class="context-menu" role="menu" hidden><button id="menu-rename-folder" type="button" role="menuitem" data-i18n="renameFolder">Rename folder</button><button id="menu-delete-folder" class="danger" type="button" role="menuitem" data-i18n="deleteFolder">Delete folder</button></div>
  </main>
<script>
const ROOM_ID = {room_json};
const LANGUAGE_KEY = 'ideaSparkDashboardLanguage';
const ROOM_PIN_KEY = 'ideaSparkDashboardPinnedRooms';
const ROOM_GROUP_KEY = 'ideaSparkDashboardRoomGroupMode';
const ROOM_FOLDER_KEY = 'ideaSparkDashboardRoomFolders';
const TRANSLATIONS = {{
  en: {{
    agentsHeading: 'Agents in this room',
    navigationSearch: 'Search rooms and agents',
    conversationSearch: 'Search this conversation',
    conversationLabel: 'Conversation history',
    workspaceTitle: 'Research workspace',
    workspaceSubtitle: 'Idea-Spark · Delphi',
    welcomeMessage: 'Choose a room to follow the discussion, or select an agent to inspect its work.',
    roomConversation: 'Room conversation',
    roomOverview: 'Room overview',
    workRecords: 'work records',
    coordinator: 'Coordinator',
    notJoined: 'Not joined yet',
    noSearchResults: 'No matching rooms or agents.',
    latestMessages: 'Latest',
    filterToggle: 'Show or hide filters',
    openNavigation: 'Open rooms and agents',
    closeNavigation: 'Close navigation',
    appTitle: 'Delphi',
    readonlyLocal: 'local management · localhost',
    roomsHeading: 'Rooms',
    currentRoom: 'current',
    groupRoomsLabel: 'Group rooms',
    groupRoomsNone: 'No grouping',
    groupRoomsStatus: 'Status',
    groupRoomsCreator: 'Creator',
    groupRoomsProtocol: 'Protocol',
    groupRoomsDay: 'Created day',
    pinnedRooms: 'Pinned rooms',
    unpinnedRooms: 'Other rooms',
    pinRoom: 'Pin',
    unpinRoom: 'Unpin',
    deleteRoom: 'Delete room',
    addToFolder: 'Add to group',
    createFolder: 'New folder',
    renameFolder: 'Rename folder',
    deleteFolder: 'Delete folder',
    folderNamePrompt: 'Folder name',
    addToFolderPrompt: 'Type an existing group name, or a new group name',
    deleteFolderConfirm: 'Delete this group folder? Rooms will not be deleted.',
    emptyFolder: 'No rooms in this folder.',
    deleteRoomConfirm: 'Delete this Idea-Spark room and all of its local ledger records?',
    deleteRoomFailed: 'Delete failed',
    liveMonitor: 'Live monitor',
    languageAria: 'Language',
    switchTo: 'Switch to',
    connecting: 'connecting',
    liveViaSSE: 'live via SSE',
    polling: 'polling',
    sseReconnecting: 'SSE reconnecting',
    selectRoom: 'select a room',
    roomsFailed: 'rooms failed',
    noRooms: 'No Idea-Spark rooms found yet.',
    noSnapshot: 'No snapshot',
    noAgents: 'No child agents have joined this room.',
    noTimeline: 'No messages or artifacts match the current filters.',
    allKinds: 'All kinds',
    allAgents: 'All subagents',
    allTags: 'All tags',
    kindFilterLabel: 'Kind',
    agentFilterLabel: 'Subagent',
    tagFilterLabel: 'Tag',
    pageSizeLabel: 'Page size',
    groupByAgentLabel: 'Group by subagent',
    prevPage: 'Prev',
    nextPage: 'Next',
    paginationShowing: 'showing',
    paginationOf: 'of',
    pageLabel: 'page',
    roomPrefix: 'room',
    updatedPrefix: 'updated',
    missingPrefix: 'missing',
    allAgentsJoined: 'all expected agents joined',
    currentPhase: 'Current phase',
    finalGate: 'Final gate',
    unresolvedNeeds: 'Unresolved needs',
    noGate: 'no gate yet',
    agentFallback: 'agent',
    stats: {{
      artifacts: 'Artifacts',
      gates: 'Gates',
      messages: 'Messages',
      open_needs: 'Open needs',
      total_needs: 'Total needs',
      participants: 'Participants',
    }},
    eventKinds: {{
      artifact: 'artifact',
      message: 'message',
      gate: 'gate',
      open_need: 'open need',
    }},
    status: {{
      open: 'open',
      closed: 'closed',
      archived: 'archived',
    }},
  }},
  zh: {{
    agentsHeading: '当前房间的代理',
    navigationSearch: '搜索房间和代理',
    conversationSearch: '搜索当前对话',
    conversationLabel: '对话记录',
    workspaceTitle: '研究工作台',
    workspaceSubtitle: 'Idea-Spark · Delphi',
    welcomeMessage: '选择房间查看整场讨论，或选择代理查看它的工作记录。',
    roomConversation: '房间讨论',
    roomOverview: '房间概览',
    workRecords: '条工作记录',
    coordinator: '协调者',
    notJoined: '尚未加入',
    noSearchResults: '没有匹配的房间或代理。',
    latestMessages: '最新',
    filterToggle: '显示或收起筛选',
    openNavigation: '打开房间与代理列表',
    closeNavigation: '关闭导航',
    appTitle: 'Delphi 研究讨论',
    readonlyLocal: '本地管理 · localhost',
    roomsHeading: '房间',
    currentRoom: '当前',
    groupRoomsLabel: '房间分组',
    groupRoomsNone: '不分组',
    groupRoomsStatus: '按状态',
    groupRoomsCreator: '按创建者',
    groupRoomsProtocol: '按协议',
    groupRoomsDay: '按创建日期',
    pinnedRooms: '置顶房间',
    unpinnedRooms: '其他房间',
    pinRoom: '置顶',
    unpinRoom: '取消置顶',
    deleteRoom: '删除房间',
    addToFolder: '添加到分组',
    createFolder: '新建分组文件夹',
    renameFolder: '修改名称',
    deleteFolder: '删除分组文件夹',
    folderNamePrompt: '分组文件夹名称',
    addToFolderPrompt: '输入已有分组名称，或输入新的分组名称',
    deleteFolderConfirm: '删除这个分组文件夹？房间本身不会被删除。',
    emptyFolder: '这个分组文件夹中暂无房间。',
    deleteRoomConfirm: '删除这个 Idea-Spark 房间及其本地账本记录？',
    deleteRoomFailed: '删除失败',
    liveMonitor: '实时监控',
    languageAria: '语言',
    switchTo: '切换到',
    connecting: '连接中',
    liveViaSSE: 'SSE 实时连接',
    polling: '轮询中',
    sseReconnecting: 'SSE 重连中',
    selectRoom: '请选择房间',
    roomsFailed: '房间加载失败',
    noRooms: '还没有 Idea-Spark 房间。',
    noSnapshot: '暂无快照',
    noAgents: '暂无子代理加入这个房间。',
    noTimeline: '当前筛选条件下暂无消息或产物。',
    allKinds: '全部类型',
    allAgents: '全部子代理',
    allTags: '全部标签',
    kindFilterLabel: '类型',
    agentFilterLabel: '子代理',
    tagFilterLabel: '标签',
    pageSizeLabel: '每页条数',
    groupByAgentLabel: '按子代理分组',
    prevPage: '上一页',
    nextPage: '下一页',
    paginationShowing: '显示',
    paginationOf: '共',
    pageLabel: '页',
    roomPrefix: '房间',
    updatedPrefix: '更新于',
    missingPrefix: '未加入',
    allAgentsJoined: '全部预期代理已加入',
    currentPhase: '当前阶段',
    finalGate: '最终 Gate',
    unresolvedNeeds: '未解决需求',
    noGate: '尚无 Gate',
    agentFallback: '代理',
    stats: {{
      artifacts: '产物',
      gates: '门禁',
      messages: '消息',
      open_needs: '开放需求',
      total_needs: '需求总数',
      participants: '参与者',
    }},
    eventKinds: {{
      artifact: '产物',
      message: '消息',
      gate: '门禁',
      open_need: '开放需求',
    }},
    status: {{
      open: '开放',
      closed: '关闭',
      archived: '归档',
    }},
  }},
}};
const $ = (id) => document.getElementById(id);
function readStoredLanguage() {{
  try {{
    const stored = window.localStorage.getItem(LANGUAGE_KEY);
    if (stored && Object.prototype.hasOwnProperty.call(TRANSLATIONS, stored)) return stored;
  }} catch (err) {{}}
  const nav = (navigator.language || '').toLowerCase();
  return nav.startsWith('zh') ? 'zh' : 'en';
}}
let currentLanguage = readStoredLanguage();
let lastSnapshot = null;
let connectionState = {{key: 'connecting', cls: ''}};
let uiState = {{kind: 'all', agent: new URLSearchParams(location.search).get('agent') || 'all', tag: 'all', query: '', page: 1, pageSize: 50, groupByAgent: false, filtersOpen: false, followLatest: true}};
let lastRooms = [];
let roomsLoaded = false;
let navigationQuery = '';
let pollingTimer = null;
let roomPrefs = loadRoomPrefs();
let activeRoomMenuRoom = null;
let activeFolderMenuId = null;
function lookup(path, table) {{
  return path.split('.').reduce((acc, part) => (
    acc && Object.prototype.hasOwnProperty.call(acc, part) ? acc[part] : undefined
  ), table);
}}
function t(path, fallback) {{
  const value = lookup(path, TRANSLATIONS[currentLanguage] || TRANSLATIONS.en);
  if (value !== undefined) return value;
  const english = lookup(path, TRANSLATIONS.en);
  if (english !== undefined) return english;
  return fallback !== undefined ? fallback : path;
}}
function node(tag, className, text) {{
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined && text !== null) el.textContent = text;
  return el;
}}
function normalizeRoomFolders(value) {{
  if (!Array.isArray(value)) return [];
  const seen = new Set();
  return value.map((folder, index) => {{
    const rawId = folder && folder.id ? String(folder.id) : 'folder-' + index;
    const id = seen.has(rawId) ? rawId + '-' + index : rawId;
    seen.add(id);
    const name = folder && folder.name ? String(folder.name).trim() : '';
    const roomIds = Array.isArray(folder && folder.roomIds) ? folder.roomIds.filter(Boolean).map(String) : [];
    return {{id, name: name || t('folderNamePrompt') + ' ' + (index + 1), roomIds: Array.from(new Set(roomIds))}};
  }});
}}
function loadRoomPrefs() {{
  let pinned = [];
  let groupMode = 'none';
  let folders = [];
  try {{
    const parsed = JSON.parse(window.localStorage.getItem(ROOM_PIN_KEY) || '[]');
    if (Array.isArray(parsed)) pinned = parsed.filter(Boolean).map(String);
  }} catch (err) {{ pinned = []; }}
  try {{ groupMode = window.localStorage.getItem(ROOM_GROUP_KEY) || 'none'; }} catch (err) {{ groupMode = 'none'; }}
  if (!['none', 'status', 'creator', 'protocol', 'day'].includes(groupMode)) groupMode = 'none';
  try {{ folders = normalizeRoomFolders(JSON.parse(window.localStorage.getItem(ROOM_FOLDER_KEY) || '[]')); }} catch (err) {{ folders = []; }}
  return {{pinned: new Set(pinned), groupMode, folders}};
}}
function saveRoomPrefs() {{
  try {{ window.localStorage.setItem(ROOM_PIN_KEY, JSON.stringify(Array.from(roomPrefs.pinned))); }} catch (err) {{}}
  try {{ window.localStorage.setItem(ROOM_GROUP_KEY, roomPrefs.groupMode); }} catch (err) {{}}
  try {{ window.localStorage.setItem(ROOM_FOLDER_KEY, JSON.stringify(roomPrefs.folders)); }} catch (err) {{}}
}}
function roomTitle(room) {{ return room.title || room.room_id; }}
function contentText(value) {{
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map((item) => '- ' + contentText(item)).join('\n');
  if (typeof value === 'object') {{
    if (Object.prototype.hasOwnProperty.call(value, 'content_text')) return contentText(value.content_text);
    const keys = Object.keys(value);
    if (keys.length === 1 && keys[0] === 'text') return contentText(value.text);
    if (typeof value.text === 'string') {{
      const rest = Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'text'));
      const restText = Object.keys(rest).length ? contentText(rest) : '';
      return restText ? value.text + '\n\n' + restText : value.text;
    }}
    return Object.entries(value).map(([key, item]) => '**' + key + '**: ' + contentText(item)).join('\n');
  }}
  return String(value);
}}
function escapeHtml(value) {{
  return String(value).replace(/[&<>"']/g, (ch) => ({{
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }}[ch]));
}}
function inlineMarkdown(text) {{
  let html = escapeHtml(text);
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\b_([^_]+)_\b/g, '<em>$1</em>');
  return html;
}}
function splitMarkdownTableRow(line) {{
  const trimmed = line.trim();
  if (!trimmed.includes('|')) return null;
  let body = trimmed;
  if (body.startsWith('|')) body = body.slice(1);
  if (body.endsWith('|')) body = body.slice(0, -1);
  const cells = [];
  let current = '';
  let escaped = false;
  for (const ch of body) {{
    if (escaped) {{ current += ch; escaped = false; continue; }}
    if (ch === '\\') {{ escaped = true; current += ch; continue; }}
    if (ch === '|') {{ cells.push(current.trim()); current = ''; continue; }}
    current += ch;
  }}
  cells.push(current.trim());
  return cells;
}}
function parseMarkdownTableAlign(cell) {{
  const text = cell.trim();
  if (!/^:?-{{3,}}:?$/.test(text)) return null;
  if (text.startsWith(':') && text.endsWith(':')) return 'center';
  if (text.endsWith(':')) return 'right';
  return 'left';
}}
function markdownTableAt(lines, index) {{
  if (index + 1 >= lines.length) return null;
  const header = splitMarkdownTableRow(lines[index]);
  const separator = splitMarkdownTableRow(lines[index + 1]);
  if (!header || !separator || header.length < 2 || separator.length !== header.length) return null;
  const alignments = separator.map(parseMarkdownTableAlign);
  if (alignments.some((align) => !align)) return null;
  return {{header: header, alignments: alignments}};
}}
function renderMarkdownTable(lines, startIndex) {{
  const table = markdownTableAt(lines, startIndex);
  if (!table) return null;
  let index = startIndex + 2;
  const rows = [];
  while (index < lines.length) {{
    const rowLine = lines[index].replace(/\s+$/, '');
    if (!rowLine.trim()) break;
    const cells = splitMarkdownTableRow(rowLine);
    if (!cells || cells.length !== table.header.length) break;
    rows.push(cells);
    index += 1;
  }}
  const alignAttr = (align) => align && align !== 'left' ? ' style="text-align:' + align + '"' : '';
  const head = '<thead><tr>' + table.header.map((cell, column) => '<th' + alignAttr(table.alignments[column]) + '>' + inlineMarkdown(cell) + '</th>').join('') + '</tr></thead>';
  const body = rows.length ? '<tbody>' + rows.map((row) => '<tr>' + row.map((cell, column) => '<td' + alignAttr(table.alignments[column]) + '>' + inlineMarkdown(cell) + '</td>').join('') + '</tr>').join('') + '</tbody>' : '';
  return {{html: '<div class="table-wrap"><table>' + head + body + '</table></div>', nextIndex: index}};
}}
function markdownToSafeHtml(value) {{
  const lines = contentText(value).replace(/\r\n/g, '\n').split('\n');
  const html = [];
  let listKind = null;
  let inCode = false;
  let codeLines = [];
  function closeList() {{
    if (listKind) {{ html.push('</' + listKind + '>'); listKind = null; }}
  }}
  function openList(kind) {{
    if (listKind !== kind) {{ closeList(); html.push('<' + kind + '>'); listKind = kind; }}
  }}
  for (let index = 0; index < lines.length; index += 1) {{
    const raw = lines[index];
    const line = raw.replace(/\s+$/, '');
    if (line.trim().startsWith('```')) {{
      if (inCode) {{
        html.push('<pre><code>' + escapeHtml(codeLines.join('\n')) + '</code></pre>');
        codeLines = [];
        inCode = false;
      }} else {{
        closeList();
        inCode = true;
      }}
      continue;
    }}
    if (inCode) {{ codeLines.push(line); continue; }}
    if (!line.trim()) {{ closeList(); continue; }}
    const table = renderMarkdownTable(lines, index);
    if (table) {{
      closeList();
      html.push(table.html);
      index = table.nextIndex - 1;
      continue;
    }}
    const heading = line.match(/^(#{{1,3}})\s+(.*)$/);
    if (heading) {{
      closeList();
      const level = heading[1].length;
      html.push('<h' + level + '>' + inlineMarkdown(heading[2]) + '</h' + level + '>');
      continue;
    }}
    const quoteMatch = line.match(/^>\s?(.*)$/);
    if (quoteMatch) {{ closeList(); html.push('<blockquote>' + inlineMarkdown(quoteMatch[1]) + '</blockquote>'); continue; }}
    const unordered = line.match(/^\s*[-*]\s+(.*)$/);
    if (unordered) {{ openList('ul'); html.push('<li>' + inlineMarkdown(unordered[1]) + '</li>'); continue; }}
    const ordered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (ordered) {{ openList('ol'); html.push('<li>' + inlineMarkdown(ordered[1]) + '</li>'); continue; }}
    closeList();
    html.push('<p>' + inlineMarkdown(line) + '</p>');
  }}
  closeList();
  if (inCode) html.push('<pre><code>' + escapeHtml(codeLines.join('\n')) + '</code></pre>');
  return html.join('');
}}
function renderMarkdown(el, value) {{
  el.innerHTML = markdownToSafeHtml(value);
}}
function applyStaticTranslations() {{
  document.documentElement.lang = currentLanguage === 'zh' ? 'zh-CN' : 'en';
  document.querySelectorAll('[data-i18n]').forEach((el) => {{
    el.textContent = t(el.dataset.i18n);
  }});
  document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => el.placeholder = t(el.dataset.i18nPlaceholder));
  document.querySelectorAll('[data-i18n-aria]').forEach((el) => {{ el.setAttribute('aria-label', t(el.dataset.i18nAria)); el.title = t(el.dataset.i18nAria); }});
  const switcher = $('language-switch');
  if (switcher) switcher.setAttribute('aria-label', t('languageAria'));
  document.querySelectorAll('[data-lang-option]').forEach((button) => {{
    const active = button.dataset.langOption === currentLanguage;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
    button.title = t('switchTo') + ' ' + button.textContent;
  }});
}}
function renderConnection() {{
  const el = $('connection');
  el.textContent = t(connectionState.key);
  el.className = 'badge ' + (connectionState.cls || '');
}}
function setConnection(key, cls) {{
  connectionState = {{key: key, cls: cls || ''}};
  renderConnection();
}}
function setLanguage(lang) {{
  if (!Object.prototype.hasOwnProperty.call(TRANSLATIONS, lang)) return;
  currentLanguage = lang;
  try {{ window.localStorage.setItem(LANGUAGE_KEY, lang); }} catch (err) {{}}
  applyStaticTranslations();
  renderConnection();
  if (lastSnapshot) renderSnapshot(lastSnapshot);
  else document.title = t('appTitle');
  loadRooms().catch(() => setConnection('roomsFailed', ''));
}}
function setupLanguageSwitch() {{
  document.querySelectorAll('[data-lang-option]').forEach((button) => {{
    button.addEventListener('click', () => setLanguage(button.dataset.langOption));
  }});
}}
function setupRoomControls() {{
  const group = $('room-group-mode');
  if (group) {{
    group.value = roomPrefs.groupMode;
    group.addEventListener('change', () => {{
      roomPrefs.groupMode = group.value || 'none';
      saveRoomPrefs();
      loadRooms().catch(() => setConnection('roomsFailed', ''));
    }});
  }}
  const rooms = $('rooms');
  if (rooms) {{
    rooms.addEventListener('contextmenu', (event) => {{
      if (event.target.closest('.room-entry') || event.target.closest('.room-folder-header')) return;
      openRoomAreaMenu(event);
    }});
  }}
  const create = $('menu-create-folder');
  if (create) create.addEventListener('click', createRoomFolder);
  $('new-folder').addEventListener('click', createRoomFolder);
  const pin = $('menu-pin-room');
  if (pin) pin.addEventListener('click', () => {{ if (activeRoomMenuRoom) toggleRoomPin(activeRoomMenuRoom.room_id); closeRoomMenus(); }});
  const add = $('menu-add-room-folder');
  if (add) add.addEventListener('click', () => {{ if (activeRoomMenuRoom) addRoomToFolder(activeRoomMenuRoom.room_id); closeRoomMenus(); }});
  const del = $('menu-delete-room');
  if (del) del.addEventListener('click', () => {{ const room = activeRoomMenuRoom; closeRoomMenus(); if (room) deleteRoom(room); }});
  const rename = $('menu-rename-folder');
  if (rename) rename.addEventListener('click', () => {{ const folderId = activeFolderMenuId; closeRoomMenus(); if (folderId) renameRoomFolder(folderId); }});
  const deleteFolderButton = $('menu-delete-folder');
  if (deleteFolderButton) deleteFolderButton.addEventListener('click', () => {{ const folderId = activeFolderMenuId; closeRoomMenus(); if (folderId) deleteRoomFolder(folderId); }});
  document.addEventListener('click', (event) => {{ if (!event.target.closest('.context-menu')) closeRoomMenus(); }});
  document.addEventListener('keydown', (event) => {{ if (event.key === 'Escape') closeRoomMenus(); }});
  window.addEventListener('resize', closeRoomMenus);
  window.addEventListener('scroll', closeRoomMenus, true);
}}
function statusText(status) {{ return t('status.' + status, status); }}
function eventKindText(kind) {{ return t('eventKinds.' + kind, kind); }}
function fillSelect(id, values, allText, selected, labelFn) {{
  const select = $(id);
  if (!select) return 'all';
  const unique = Array.from(new Set(values || [])).filter(Boolean).sort();
  select.replaceChildren();
  select.appendChild(new Option(allText, 'all'));
  for (const value of unique) select.appendChild(new Option(labelFn ? labelFn(value) : value, value));
  select.value = unique.includes(selected) ? selected : 'all';
  return select.value;
}}
function buildFilterControls(data) {{
  const controls = $('timeline-controls');
  const pagination = $('timeline-pagination');
  if (!controls || !pagination) return;
  controls.hidden = !uiState.filtersOpen;
  pagination.hidden = false;
  const options = data.filter_options || {{}};
  uiState.kind = fillSelect('kind-filter', options.kinds || [], t('allKinds'), uiState.kind, eventKindText);
  uiState.agent = fillSelect('agent-filter', [...(options.agents || []), ...(data.missing_expected_agents || [])], t('allAgents'), uiState.agent);
  uiState.tag = fillSelect('tag-filter', options.tags || [], t('allTags'), uiState.tag);
  const pageSize = $('page-size');
  if (pageSize) pageSize.value = String(uiState.pageSize);
  const group = $('group-by-agent');
  if (group) group.checked = Boolean(uiState.groupByAgent);
}}
function resetConversationView() {{
  uiState.page = 1;
  uiState.followLatest = true;
  if (lastSnapshot && lastSnapshot.success) {{
    renderAgentList(lastSnapshot);
    renderConversationHeading(lastSnapshot);
    renderTimelinePage(lastSnapshot);
  }}
}}
function syncNavigationAccessibility() {{
  const closedMobile = matchMedia('(max-width: 740px)').matches && !$('app-shell').classList.contains('sidebar-open');
  if (closedMobile && $('sidebar').contains(document.activeElement)) $('navigation-toggle').focus();
  $('sidebar').inert = closedMobile;
}}
function setNavigationOpen(open) {{
  $('app-shell').classList.toggle('sidebar-open', open);
  $('navigation-toggle').setAttribute('aria-expanded', String(open));
  syncNavigationAccessibility();
  if (open) $('navigation-search').focus();
}}
function selectAgent(agent) {{
  uiState.agent = agent || 'all';
  $('agent-filter').value = uiState.agent;
  const url = new URL(location.href);
  if (uiState.agent === 'all') url.searchParams.delete('agent');
  else url.searchParams.set('agent', uiState.agent);
  history.replaceState(null, '', url);
  resetConversationView();
  setNavigationOpen(false);
}}
function setupTimelineControls() {{
  for (const [id, key] of [['kind-filter', 'kind'], ['agent-filter', 'agent'], ['tag-filter', 'tag']]) {{
    $(id).addEventListener('change', () => {{
      if (key === 'agent') selectAgent($(id).value);
      else {{ uiState[key] = $(id).value || 'all'; resetConversationView(); }}
    }});
  }}
  $('page-size').addEventListener('change', () => {{ uiState.pageSize = Number($('page-size').value) || 50; resetConversationView(); }});
  $('group-by-agent').addEventListener('change', () => {{ uiState.groupByAgent = $('group-by-agent').checked; resetConversationView(); }});
  $('timeline-search').addEventListener('input', () => {{ uiState.query = $('timeline-search').value.trim().toLowerCase(); resetConversationView(); }});
  for (const [id, delta] of [['page-prev', -1], ['page-next', 1]]) {{
    $(id).addEventListener('click', () => {{
      uiState.page = Math.max(1, uiState.page + delta);
      uiState.followLatest = false;
      $('conversation-scroll').scrollTop = 0;
      if (lastSnapshot) renderTimelinePage(lastSnapshot);
    }});
  }}
  $('timeline-latest').addEventListener('click', resetConversationView);
  $('filter-toggle').addEventListener('click', () => {{
    uiState.filtersOpen = !uiState.filtersOpen;
    $('timeline-controls').hidden = !uiState.filtersOpen;
    $('filter-toggle').setAttribute('aria-pressed', String(uiState.filtersOpen));
  }});
  $('navigation-search').addEventListener('input', () => {{
    navigationQuery = $('navigation-search').value.trim().toLowerCase();
    renderRoomGroups(lastRooms);
    if (lastSnapshot && lastSnapshot.success) renderAgentList(lastSnapshot);
  }});
  $('navigation-toggle').addEventListener('click', () => setNavigationOpen(!$('app-shell').classList.contains('sidebar-open')));
  $('sidebar-backdrop').addEventListener('click', () => setNavigationOpen(false));
  syncNavigationAccessibility();
  window.addEventListener('resize', syncNavigationAccessibility);
  document.addEventListener('keydown', (event) => {{ if (event.key === 'Escape') setNavigationOpen(false); }});
  $('conversation-scroll').addEventListener('scroll', () => {{
    const pane = $('conversation-scroll');
    const atBottom = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 80;
    if (!atBottom) uiState.followLatest = false;
    else if (lastSnapshot && lastSnapshot.success) {{
      const pages = Math.max(1, Math.ceil(filteredTimeline(lastSnapshot).length / uiState.pageSize));
      if (uiState.page === pages) uiState.followLatest = true;
    }}
    $('timeline-latest').classList.toggle('active', uiState.followLatest);
  }});
}}

function filteredTimeline(data) {{
  const events = (data && data.timeline) ? data.timeline : [];
  return events.filter((event) => {{
    if (uiState.kind !== 'all' && event.kind !== uiState.kind) return false;
    if (uiState.agent !== 'all' && event.actor !== uiState.agent) return false;
    if (uiState.tag !== 'all' && !(event.tags || []).includes(uiState.tag)) return false;
    if (uiState.query && ![event.actor, event.role, event.title, event.content_text, contentText(event.content), ...(event.tags || [])].join(' ').toLowerCase().includes(uiState.query)) return false;
    return true;
  }});
}}
function groupEventsByAgent(events) {{
  const groups = new Map();
  for (const event of events) {{
    const actor = event.actor || '-';
    if (!groups.has(actor)) groups.set(actor, []);
    groups.get(actor).push(event);
  }}
  return Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
}}
function participantInfo(agentId, data = lastSnapshot) {{
  const participant = ((data && data.participants) || []).find((item) => item.agent_id === agentId);
  return participant || {{agent_id: agentId, display_name: agentId, role: data && data.room.created_by === agentId ? t('coordinator') : t('agentFallback')}};
}}
function avatar(identity, room = false) {{
  const identities = room ? lastRooms.map((item) => item.room_id) : ((lastSnapshot && lastSnapshot.filter_options.agents) || []);
  const color = Math.max(0, identities.indexOf(identity)) % 6;
  const el = node('span', 'avatar tone-' + color + (room ? ' room-avatar' : ''));
  el.setAttribute('aria-hidden', 'true');
  if (room) for (let n = 0; n < 3; n++) el.appendChild(node('span', 'mini-avatar'));
  return el;
}}
function displayTime(value, short = false) {{
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) return '';
  const sameDay = date.toDateString() === new Date().toDateString();
  const options = short && !sameDay ? {{month: 'short', day: 'numeric'}} : {{hour: 'numeric', minute: '2-digit'}};
  return date.toLocaleString(currentLanguage === 'zh' ? 'zh-CN' : 'en-US', options);
}}
function recordPreview(event) {{
  return event ? contentText(event.content_text !== undefined ? event.content_text : event.content).replace(/\s+/g, ' ').slice(0, 180) : '';
}}
function renderConversationHeading(data) {{
  const selected = uiState.agent !== 'all';
  const participant = selected ? participantInfo(uiState.agent, data) : null;
  const title = selected ? (participant.display_name || participant.agent_id) : roomTitle(data.room);
  $('room-heading').textContent = title;
  $('conversation-avatar').replaceChildren(avatar(selected ? uiState.agent : data.room.room_id, !selected));
  const count = (data.timeline || []).filter((event) => !selected || event.actor === uiState.agent).length;
  $('conversation-subtitle').textContent = selected ? roomTitle(data.room) + ' · ' + (participant.role || t('agentFallback')) + ' · ' + count + ' ' + t('workRecords') : t('roomConversation') + ' · ' + (data.participants || []).length + ' ' + t('stats.participants');
  document.title = title + ' · Delphi';
}}
function renderAgentList(data) {{
  const agents = $('agents');
  agents.replaceChildren();
  $('agents-section').hidden = false;
  const identities = Array.from(new Set([...(data.filter_options.agents || []), ...(data.missing_expected_agents || [])]));
  $('agent-count').textContent = identities.length;
  const addEntry = (id, label, preview, time) => {{
    const row = node('button', 'agent-entry' + (uiState.agent === id ? ' active' : ''));
    row.type = 'button'; row.dataset.agentId = id;
    row.setAttribute('aria-pressed', String(uiState.agent === id));
    row.appendChild(avatar(id));
    const body = node('div', 'nav-body');
    const title = node('div', 'agent-title-row');
    title.append(node('span', 'agent-name', label), node('time', 'nav-time', displayTime(time, true)));
    body.append(title, node('div', 'nav-preview', preview)); row.appendChild(body);
    row.addEventListener('click', () => selectAgent(id)); agents.appendChild(row);
  }};
  let visible = 0;
  for (const identity of identities) {{
    const participant = participantInfo(identity, data);
    const records = (data.timeline || []).filter((event) => event.actor === identity);
    const latest = records[records.length - 1];
    const label = participant.display_name || identity;
    if (navigationQuery && ![identity, label, participant.role, recordPreview(latest)].join(' ').toLowerCase().includes(navigationQuery)) continue;
    const missing = (data.missing_expected_agents || []).includes(identity);
    addEntry(identity, label, missing ? t('notJoined') : recordPreview(latest) || participant.role || t('agentFallback'), latest ? latest.created_at : participant.last_seen_at);
    visible++;
  }}
  if (!visible) agents.appendChild(node('div', 'empty', navigationQuery ? t('noSearchResults') : t('noAgents')));
}}
function renderEventCard(event) {{
  const outgoing = lastSnapshot && event.actor && event.actor === lastSnapshot.room.created_by;
  const card = node('article', 'event ' + event.kind + (outgoing ? ' outgoing' : ''));
  card.dataset.eventId = event.id; card.dataset.actor = event.actor || '';
  const participant = participantInfo(event.actor);
  const head = node('div', 'event-head');
  head.appendChild(node('span', 'event-actor', participant.display_name || event.actor || t('agentFallback')));
  const time = node('time', 'event-meta', displayTime(event.created_at));
  time.dateTime = event.created_at || ''; time.title = event.created_at || '';
  head.appendChild(time); card.appendChild(head);
  const bubble = node('div', 'event-bubble');
  const body = node('div', 'event-markdown');
  renderMarkdown(body, event.content_text !== undefined ? event.content_text : event.content);
  if (event.kind === 'artifact') {{
    const details = node('details', 'artifact-details');
    details.append(node('summary', null, eventKindText(event.kind) + ' · ' + (event.title || event.role || event.id)), body);
    bubble.appendChild(details);
  }} else {{
    if (event.kind !== 'message') {{
      bubble.append(node('div', 'event-kind', eventKindText(event.kind)), node('div', 'event-title', event.title || event.id));
    }}
    bubble.appendChild(body);
  }}
  const visibleTags = (event.tags || []).filter((tag) => !/^(agent|kind|phase|role|round|artifact|need|status):/.test(tag));
  if (visibleTags.length) {{
    const tags = node('div', 'event-tags');
    for (const tag of visibleTags) tags.appendChild(node('span', 'tag', tag));
    bubble.appendChild(tags);
  }}
  if (event.phase) bubble.appendChild(node('div', 'event-tags', event.phase)).classList.add('event-meta');
  card.appendChild(bubble);
  return card;
}}

function renderTimelinePage(data) {{
  const timeline = $('timeline');
  const pane = $('conversation-scroll');
  const scrollTop = pane.scrollTop;
  const openArtifacts = new Set(Array.from(timeline.querySelectorAll('.artifact-details[open]')).map((el) => el.closest('.event').dataset.eventId));
  const events = filteredTimeline(data);
  const pageSize = Math.max(1, Number(uiState.pageSize) || 50);
  const pageCount = Math.max(1, Math.ceil(events.length / pageSize));
  uiState.page = uiState.followLatest ? pageCount : Math.min(Math.max(1, uiState.page), pageCount);
  const start = (uiState.page - 1) * pageSize;
  const pageEvents = events.slice(start, start + pageSize);
  timeline.replaceChildren();
  const appendEvents = (container, list) => {{
    let lastDay = '';
    for (const event of list) {{
      const date = new Date(event.created_at);
      if (!Number.isNaN(date.getTime())) {{
        const day = date.toLocaleDateString(currentLanguage === 'zh' ? 'zh-CN' : 'en-US', {{year: 'numeric', month: 'long', day: 'numeric'}});
        if (day !== lastDay) {{ container.appendChild(node('div', 'day-divider', day)); lastDay = day; }}
      }}
      const card = renderEventCard(event);
      const details = card.querySelector('.artifact-details');
      if (details) details.open = openArtifacts.has(event.id);
      container.appendChild(card);
    }}
  }};
  if (!pageEvents.length) timeline.appendChild(node('div', 'empty', t('noTimeline')));
  else if (uiState.groupByAgent) {{
    for (const [actor, group] of groupEventsByAgent(pageEvents)) {{
      const section = node('section', 'agent-group');
      const participant = participantInfo(actor);
      section.appendChild(node('h3', null, participant.display_name || actor));
      appendEvents(section, group); timeline.appendChild(section);
    }}
  }} else appendEvents(timeline, pageEvents);
  const end = events.length ? Math.min(events.length, start + pageEvents.length) : 0;
  const first = events.length ? start + 1 : 0;
  $('page-info').textContent = t('paginationShowing') + ' ' + first + '–' + end + ' ' + t('paginationOf') + ' ' + events.length + ' · ' + t('pageLabel') + ' ' + uiState.page + '/' + pageCount;
  $('page-prev').disabled = uiState.page <= 1;
  $('page-next').disabled = uiState.page >= pageCount;
  $('timeline-latest').classList.toggle('active', uiState.followLatest);
  requestAnimationFrame(() => {{ pane.scrollTop = uiState.followLatest ? pane.scrollHeight : scrollTop; }});
}}

function renderDiscussionState(data) {{
  const currentPhase = data.current_phase || '-';
  const latestGate = data.latest_gate || null;
  const hasTerminalGate = Boolean(data.has_terminal_gate);
  const openNeedSummary = data.open_need_summary || {{}};
  const unresolved = Number(openNeedSummary.open || 0) + Number(openNeedSummary.claimed || 0);
  const phaseEl = $('current-phase');
  const gateEl = $('latest-gate');
  const needEl = $('open-need-summary');
  if (phaseEl) phaseEl.textContent = t('currentPhase') + ': ' + currentPhase;
  if (gateEl) {{
    gateEl.className = hasTerminalGate ? 'pill hot' : 'pill';
    gateEl.textContent = t('finalGate') + ': ' + (latestGate ? latestGate.decision : t('noGate'));
  }}
  if (needEl) needEl.textContent = t('unresolvedNeeds') + ': ' + unresolved;
}}
function hideRoomMenus() {{
  for (const id of ['room-area-menu', 'room-context-menu', 'room-folder-menu']) {{
    const menu = $(id);
    if (menu) menu.hidden = true;
  }}
  document.querySelectorAll('.room-entry.menu-open').forEach((row) => row.classList.remove('menu-open'));
}}
function positionMenu(menu, event) {{
  hideRoomMenus();
  event.preventDefault();
  menu.hidden = false;
  const width = menu.offsetWidth || 178;
  const height = menu.offsetHeight || 120;
  const left = Math.max(8, Math.min(event.clientX, window.innerWidth - width - 8));
  const top = Math.max(8, Math.min(event.clientY, window.innerHeight - height - 8));
  menu.style.left = left + 'px';
  menu.style.top = top + 'px';
}}
function closeRoomMenus() {{
  hideRoomMenus();
  activeRoomMenuRoom = null;
  activeFolderMenuId = null;
}}
function findRoomFolder(folderId) {{ return roomPrefs.folders.find((folder) => folder.id === folderId) || null; }}
function findOrCreateRoomFolder(name) {{
  const clean = String(name || '').trim();
  if (!clean) return null;
  const existing = roomPrefs.folders.find((folder) => folder.name.toLowerCase() === clean.toLowerCase());
  if (existing) return existing;
  const folder = {{id: 'folder-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 7), name: clean, roomIds: []}};
  roomPrefs.folders.push(folder);
  return folder;
}}
function createRoomFolder() {{
  const name = prompt(t('folderNamePrompt'), '');
  if (!name || !name.trim()) {{ closeRoomMenus(); return; }}
  findOrCreateRoomFolder(name);
  saveRoomPrefs();
  closeRoomMenus();
  loadRooms().catch(() => setConnection('roomsFailed', ''));
}}
function renameRoomFolder(folderId) {{
  const folder = findRoomFolder(folderId);
  if (!folder) return;
  const name = prompt(t('folderNamePrompt'), folder.name);
  if (!name || !name.trim()) return;
  folder.name = name.trim();
  saveRoomPrefs();
  loadRooms().catch(() => setConnection('roomsFailed', ''));
}}
function deleteRoomFolder(folderId) {{
  const folder = findRoomFolder(folderId);
  if (!folder) return;
  if (!confirm(t('deleteFolderConfirm') + '\n' + folder.name)) return;
  roomPrefs.folders = roomPrefs.folders.filter((item) => item.id !== folderId);
  saveRoomPrefs();
  loadRooms().catch(() => setConnection('roomsFailed', ''));
}}
function addRoomToFolder(roomId) {{
  const existingNames = roomPrefs.folders.map((folder) => folder.name).join(', ');
  const name = prompt(t('addToFolderPrompt') + (existingNames ? '\n' + existingNames : ''), existingNames ? roomPrefs.folders[0].name : '');
  if (!name || !name.trim()) return;
  const folder = findOrCreateRoomFolder(name);
  if (!folder) return;
  for (const item of roomPrefs.folders) item.roomIds = item.roomIds.filter((id) => id !== roomId);
  folder.roomIds.unshift(roomId);
  folder.roomIds = Array.from(new Set(folder.roomIds));
  saveRoomPrefs();
  loadRooms().catch(() => setConnection('roomsFailed', ''));
}}
function openRoomAreaMenu(event) {{
  activeRoomMenuRoom = null;
  activeFolderMenuId = null;
  positionMenu($('room-area-menu'), event);
}}
function openRoomContextMenu(event, room) {{
  activeRoomMenuRoom = room;
  activeFolderMenuId = null;
  const row = event.currentTarget;
  const pin = $('menu-pin-room');
  if (pin) pin.textContent = roomPrefs.pinned.has(room.room_id) ? t('unpinRoom') : t('pinRoom');
  positionMenu($('room-context-menu'), event);
  if (row) row.classList.add('menu-open');
}}
function openRoomFolderMenu(event, folderId) {{
  activeRoomMenuRoom = null;
  activeFolderMenuId = folderId;
  positionMenu($('room-folder-menu'), event);
}}
function roomGroupKey(room) {{
  if (roomPrefs.groupMode === 'status') return statusText(room.status || 'open');
  if (roomPrefs.groupMode === 'creator') return room.created_by || '-';
  if (roomPrefs.groupMode === 'protocol') return room.protocol || '-';
  if (roomPrefs.groupMode === 'day') return (room.created_at || '').slice(0, 10) || '-';
  return '';
}}
function appendRoomSection(box, title, rooms) {{
  if (!rooms.length) return;
  const section = node('section', 'room-section');
  if (title) section.appendChild(node('h3', null, title));
  for (const room of rooms) section.appendChild(renderRoomEntry(room));
  box.appendChild(section);
}}
function renderRoomFolderSection(box, folder, roomLookup) {{
  const section = node('section', 'room-section room-folder');
  const heading = node('h3', 'room-folder-header', folder.name);
  heading.dataset.folderId = folder.id;
  heading.addEventListener('contextmenu', (event) => {{
    event.preventDefault();
    event.stopPropagation();
    openRoomFolderMenu(event, folder.id);
  }});
  section.appendChild(heading);
  const rooms = folder.roomIds.map((roomId) => roomLookup.get(roomId)).filter(Boolean).filter((room) => !roomPrefs.pinned.has(room.room_id));
  if (!rooms.length) section.appendChild(node('div', 'empty room-folder-empty', t('emptyFolder')));
  for (const room of rooms) section.appendChild(renderRoomEntry(room));
  box.appendChild(section);
}}
function renderRoomGroups(rooms) {{
  const box = $('rooms');
  box.replaceChildren();
  const group = $('room-group-mode');
  if (group && group.value !== roomPrefs.groupMode) group.value = roomPrefs.groupMode;
  if (!rooms || rooms.length === 0) {{
    roomPrefs.pinned.clear();
    for (const folder of roomPrefs.folders) folder.roomIds = [];
    saveRoomPrefs();
    box.appendChild(node('div', 'empty', t('noRooms')));
    return;
  }}
  const roomLookup = new Map(rooms.map((room) => [room.room_id, room]));
  const existingRoomIds = new Set(roomLookup.keys());
  let prefsChanged = false;
  for (const roomId of Array.from(roomPrefs.pinned)) {{
    if (!existingRoomIds.has(roomId)) {{ roomPrefs.pinned.delete(roomId); prefsChanged = true; }}
  }}
  for (const folder of roomPrefs.folders) {{
    const kept = folder.roomIds.filter((roomId) => existingRoomIds.has(roomId));
    if (kept.length !== folder.roomIds.length) prefsChanged = true;
    folder.roomIds = Array.from(new Set(kept));
  }}
  if (prefsChanged) saveRoomPrefs();
  rooms = rooms.filter((room) => !navigationQuery || [roomTitle(room), room.topic, room.room_id].join(' ').toLowerCase().includes(navigationQuery));
  const visibleLookup = new Map(rooms.map((room) => [room.room_id, room]));
  if (!rooms.length) {{ box.appendChild(node('div', 'empty', t('noSearchResults'))); return; }}
  const folderAssigned = new Set(roomPrefs.folders.flatMap((folder) => folder.roomIds));
  const pinned = rooms.filter((room) => roomPrefs.pinned.has(room.room_id));
  const others = rooms.filter((room) => !roomPrefs.pinned.has(room.room_id) && !folderAssigned.has(room.room_id));
  appendRoomSection(box, pinned.length ? t('pinnedRooms') : '', pinned);
  for (const folder of roomPrefs.folders) renderRoomFolderSection(box, folder, visibleLookup);
  if (roomPrefs.groupMode === 'none') {{
    appendRoomSection(box, pinned.length || roomPrefs.folders.length ? t('unpinnedRooms') : '', others);
    return;
  }}
  const groups = new Map();
  for (const room of others) {{
    const key = roomGroupKey(room);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(room);
  }}
  for (const [key, groupRooms] of Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]))) {{
    appendRoomSection(box, key, groupRooms);
  }}
}}
function renderRoomEntry(room) {{
  const pinned = roomPrefs.pinned.has(room.room_id);
  const active = room.room_id === ROOM_ID;
  const row = node('div', 'room-entry' + (pinned ? ' pinned' : ''));
  row.dataset.roomId = room.room_id;
  row.addEventListener('contextmenu', (event) => {{ event.preventDefault(); event.stopPropagation(); openRoomContextMenu(event, room); }});
  const a = node('a');
  a.href = '/room/' + encodeURIComponent(room.room_id);
  a.className = active ? 'room-link active' : 'room-link';
  if (active) {{
    a.setAttribute('aria-current', 'page');
    a.addEventListener('click', (event) => {{ event.preventDefault(); selectAgent('all'); }});
  }}
  a.appendChild(avatar(room.room_id, true));
  const body = node('div', 'nav-body');
  const titleRow = node('div', 'room-title-row');
  titleRow.appendChild(node('div', 'room-title', roomTitle(room)));
  if (active) titleRow.appendChild(node('span', 'current-room-badge', t('currentRoom')));
  const latest = active && lastSnapshot && lastSnapshot.success ? lastSnapshot.timeline[lastSnapshot.timeline.length - 1] : null;
  titleRow.appendChild(node('time', 'nav-time', displayTime(latest ? latest.created_at : room.created_at, true)));
  body.append(titleRow, node('div', 'nav-preview', recordPreview(latest) || room.topic || statusText(room.status)));
  a.appendChild(body); row.appendChild(a);
  return row;
}}

function toggleRoomPin(roomId) {{
  if (roomPrefs.pinned.has(roomId)) roomPrefs.pinned.delete(roomId);
  else roomPrefs.pinned.add(roomId);
  saveRoomPrefs();
  loadRooms().catch(() => setConnection('roomsFailed', ''));
}}
async function deleteRoom(room) {{
  if (!confirm(t('deleteRoomConfirm') + '\n' + roomTitle(room) + '\n' + room.room_id)) return;
  const res = await fetch('/api/rooms/' + encodeURIComponent(room.room_id) + '?confirm=' + encodeURIComponent(room.room_id), {{method: 'DELETE'}});
  const payload = await res.json().catch(() => ({{success: false, error: res.statusText}}));
  if (!res.ok || !payload.success) {{
    alert(t('deleteRoomFailed') + ': ' + (payload.error || res.status));
    return;
  }}
  roomPrefs.pinned.delete(room.room_id);
  saveRoomPrefs();
  if (room.room_id === ROOM_ID) {{
    window.location.href = '/';
    return;
  }}
  await loadRooms();
}}
async function loadRooms() {{
  const res = await fetch('/api/rooms', {{cache: 'no-store'}});
  if (!res.ok) throw new Error('rooms request failed');
  const data = await res.json();
  lastRooms = data.rooms || [];
  roomsLoaded = true;
  if (lastSnapshot && lastSnapshot.success && !lastRooms.some((room) => room.room_id === ROOM_ID)) lastRooms.unshift({{...lastSnapshot.room, counts: lastSnapshot.counts}});
  renderRoomGroups(lastRooms);
}}
function renderSnapshot(data) {{
  lastSnapshot = data;
  if (!data.success) {{
    $('timeline').replaceChildren(node('div', 'empty', data.error || t('noSnapshot')));
    $('agents').replaceChildren(); $('agents-section').hidden = true;
    $('room-details').hidden = true; $('timeline-pagination').hidden = true;
    return;
  }}
  $('room-details').hidden = false;
  $('room-topic').textContent = data.room.topic || '';
  const stats = node('div', 'stats');
  for (const [label, value] of Object.entries(data.counts)) {{
    const stat = node('div', 'stat');
    stat.append(node('strong', null, String(value)), node('span', null, t('stats.' + label, label))); stats.appendChild(stat);
  }}
  $('summary').replaceChildren(stats);
  const status = $('status-line'); status.replaceChildren();
  status.append(node('span', 'pill hot', statusText(data.room.status)));
  if (data.missing_expected_agents.length) status.append(node('span', 'pill', t('missingPrefix') + ' ' + data.missing_expected_agents.join(', ')));
  else status.append(node('span', 'pill ok', t('allAgentsJoined')));
  buildFilterControls(data);
  renderDiscussionState(data);
  $('room-overview-label').textContent = t('roomOverview') + ' · ' + (data.current_phase || statusText(data.room.status));
  renderAgentList(data); renderConversationHeading(data); renderTimelinePage(data);
  if (roomsLoaded) renderRoomGroups(lastRooms);
}}

async function pollSnapshot() {{
  if (!ROOM_ID) return;
  const res = await fetch('/api/rooms/' + encodeURIComponent(ROOM_ID) + '/snapshot', {{cache: 'no-store'}});
  renderSnapshot(await res.json());
}}
function startPolling() {{
  if (!pollingTimer) pollingTimer = setInterval(() => pollSnapshot().catch(() => setConnection('sseReconnecting', '')), 1500);
}}
function connectEvents() {{
  if (!ROOM_ID) return;
  if (!window.EventSource) {{ setConnection('polling', ''); startPolling(); pollSnapshot().catch(() => setConnection('roomsFailed', '')); return; }}
  const source = new EventSource('/api/rooms/' + encodeURIComponent(ROOM_ID) + '/events');
  source.addEventListener('open', () => {{
    if (pollingTimer) {{ clearInterval(pollingTimer); pollingTimer = null; }}
    setConnection('liveViaSSE', 'ok');
  }});
  source.addEventListener('snapshot', (event) => renderSnapshot(JSON.parse(event.data)));
  source.addEventListener('error', () => {{ setConnection('sseReconnecting', ''); startPolling(); }});
  window.addEventListener('pagehide', () => {{ source.close(); if (pollingTimer) clearInterval(pollingTimer); }});
}}

setupLanguageSwitch();
setupRoomControls();
setupTimelineControls();
applyStaticTranslations();
renderConnection();
loadRooms().catch(() => setConnection('roomsFailed', ''));
if (ROOM_ID) connectEvents();
else setConnection('selectRoom', '');
setInterval(() => loadRooms().catch(() => {{}}), 15000);
</script>
</body>
</html>"""


class _DashboardHTTPServer(ThreadingHTTPServer):
    daemon_threads = True


def create_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    db_path: str | Path | None = None,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
) -> ThreadingHTTPServer:
    reader = DashboardReader(db_path)
    mutator = DashboardMutator(db_path)

    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = "IdeaSparkDashboard/0.1"

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - inherited API
            return

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Allow", "GET, HEAD, OPTIONS, DELETE")
            self.end_headers()

        def do_HEAD(self) -> None:
            self.do_GET()

        def do_POST(self) -> None:
            self._reject_mutation()

        def do_PUT(self) -> None:
            self._reject_mutation()

        def do_PATCH(self) -> None:
            self._reject_mutation()

        def do_DELETE(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            parts = [unquote(part) for part in path.split("/")]
            if len(parts) == 4 and parts[1] == "api" and parts[2] == "rooms":
                room_id = parts[3]
                if query.get("confirm") != [room_id]:
                    _json_response(
                        self,
                        {"success": False, "error": "confirm query parameter must match room_id", "room_id": room_id},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return
                result = mutator.delete_room(room_id)
                status = HTTPStatus.OK if result.get("success") else HTTPStatus.NOT_FOUND
                _json_response(self, result, status)
                return
            self._reject_mutation()

        def _reject_mutation(self) -> None:
            _json_response(self, {"success": False, "error": "only DELETE /api/rooms/<room_id>?confirm=<room_id> is supported"}, HTTPStatus.METHOD_NOT_ALLOWED)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            if path == "/health":
                _json_response(
                    self,
                    {
                        "status": "ok",
                        "read_only": False,
                        "room_delete_enabled": True,
                        "db_path": str(reader.db_path),
                    },
                )
                return
            if path == "/":
                _text_response(self, _index_html())
                return
            if path == "/api/rooms":
                _json_response(self, {"success": True, "rooms": reader.list_rooms()})
                return
            if path.startswith("/room/"):
                room_id = unquote(path.removeprefix("/room/"))
                _text_response(self, _room_html(room_id))
                return
            if path.startswith("/api/rooms/"):
                parts = [unquote(part) for part in path.split("/")]
                if len(parts) == 5 and parts[4] == "snapshot":
                    _json_response(self, reader.room_snapshot(parts[3]))
                    return
                if len(parts) == 5 and parts[4] == "events":
                    self._serve_events(parts[3], once=query.get("once") == ["1"])
                    return
            _not_found(self)

        def _serve_events(self, room_id: str, *, once: bool = False) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close" if once else "keep-alive")
            self.end_headers()
            last_cursor = None
            while True:
                snapshot = reader.room_snapshot(room_id)
                cursor = snapshot.get("cursor")
                if cursor != last_cursor or once:
                    payload = _json_dumps(snapshot)
                    data = f"event: snapshot\ndata: {payload}\n\n".encode("utf-8")
                    try:
                        self.wfile.write(data)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    last_cursor = cursor
                if once:
                    self.close_connection = True
                    return
                last_cursor = cursor
                time.sleep(max(0.1, poll_interval_s))

    server = _DashboardHTTPServer((host, port), DashboardHandler)
    return server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Idea-Spark local management dashboard: monitor room messages/artifacts and delete selected local rooms with confirmation."
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host. Default: 127.0.0.1 for local-only access.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Bind port. Default: {DEFAULT_PORT}.")
    parser.add_argument("--db", dest="db_path", default=None, help="Path to idea_spark.sqlite3. Defaults to IDEA_SPARK_DB or $HERMES_HOME/idea-spark/idea_spark.sqlite3.")
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL_S, help="SSE polling interval in seconds. Default: 0.75.")
    return parser


def _bound_url(server: ThreadingHTTPServer) -> str:
    address = server.server_address
    host = str(address[0])
    port = int(address[1])
    return f"http://{host}:{port}/"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    server = create_server(args.host, args.port, db_path=args.db_path, poll_interval_s=args.poll_interval)
    print("Idea-Spark local management dashboard", flush=True)
    print(f"URL: {_bound_url(server)}", flush=True)
    print(f"DB: {DashboardReader(args.db_path).db_path}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
