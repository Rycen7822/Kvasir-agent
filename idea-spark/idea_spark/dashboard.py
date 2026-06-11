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

from .store import IdeaSparkStore, default_db_path, with_retry
from .tools import _latest_gate, _open_need_summary, _room_cursors


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
        for table in ("participants", "messages", "artifacts", "gates", "open_needs"):
            counts[table] = conn.execute(f"select count(*) as n from {table} where room_id = ?", (room_id,)).fetchone()["n"]
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
  <title>Idea-Spark Live Room</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #041c1c;
      --panel: color-mix(in srgb, #ffe6cb 5%, #041c1c);
      --panel-2: color-mix(in srgb, #ffe6cb 8%, #041c1c);
      --ink: #f6efe5;
      --muted: rgba(255, 230, 203, .62);
      --line: rgba(255, 230, 203, .20);
      --line-soft: rgba(255, 230, 203, .10);
      --accent: #ffe6cb;
      --accent-2: #5eead4;
      --bad: #fb7185;
      --ok: #86efac;
      --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
      --body: "Aptos", "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at top left, rgba(255, 230, 203, .12), transparent 30rem),
        radial-gradient(circle at 92% 8%, rgba(94, 234, 212, .14), transparent 26rem),
        linear-gradient(135deg, #020707 0%, var(--bg) 48%, #062222 100%);
      color: var(--ink);
      font-family: var(--body);
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 5;
      backdrop-filter: blur(18px);
      background: rgba(4, 28, 28, .88);
      border-bottom: 1px solid var(--line-soft);
      padding: 18px 24px;
    }}
    .wrap {{ width: 100%; max-width: min(1880px, calc(100vw - 24px)); margin: 0 auto; padding: 22px clamp(12px, 2.4vw, 36px); }}
    .topbar {{ display: flex; justify-content: space-between; align-items: center; gap: 16px; }}
    .brand {{ display: flex; gap: 14px; align-items: baseline; flex-wrap: wrap; }}
    h1 {{ margin: 0; font-size: clamp(28px, 4vw, 54px); letter-spacing: -.06em; }}
    .badge {{ border: 1px solid var(--line); border-radius: 4px; padding: 6px 10px; color: var(--muted); font-family: var(--mono); font-size: 12px; }}
    .language-switch {{ display: flex; gap: 4px; align-items: center; border: 1px solid var(--line); border-radius: 6px; padding: 3px; background: rgba(255,255,255,.03); }}
    .lang-button {{ border: 1px solid transparent; border-radius: 4px; padding: 6px 9px; background: transparent; color: var(--muted); font-family: var(--mono); font-size: 12px; cursor: pointer; }}
    .lang-button.active {{ background: var(--accent); border-color: var(--accent); color: #041c1c; }}
    .lang-button:focus-visible {{ outline: 1px solid var(--accent); outline-offset: 2px; }}
    .grid {{ display: grid; grid-template-columns: minmax(260px, 340px) minmax(0, 1fr); gap: 24px; align-items: start; }}
    .panel {{ background: color-mix(in srgb, var(--accent) 5%, var(--bg)); border: 1px solid var(--line-soft); border-radius: 8px; box-shadow: 0 16px 60px rgba(0,0,0,.24); overflow: hidden; }}
    .grid > section.panel {{ background: transparent; border: 0; box-shadow: none; overflow: visible; }}
    .grid > section.panel .panel-body {{ padding: 0; }}
    .panel h2 {{ margin: 0; padding: 15px 16px; border-bottom: 1px solid var(--line-soft); font-size: 14px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }}
    .grid > section.panel > h2 {{ padding: 0 0 12px; border-bottom: 1px solid var(--line-soft); }}
    .panel-body {{ padding: 14px 16px; }}
    .room-tools {{ display: grid; gap: 6px; padding: 11px 16px; border-bottom: 1px solid var(--line-soft); }}
    .room-tools label {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }}
    .room-tools select {{ width: 100%; border: 1px solid var(--line); border-radius: 5px; background: #082323; color: var(--ink); padding: 8px 9px; font-family: var(--body); }}
    .room-section {{ border-bottom: 1px solid var(--line-soft); padding: 4px 0; }}
    .room-section:last-child {{ border-bottom: 0; }}
    .room-section h3, .room-folder-header {{ margin: 0; padding: 9px 0 5px; color: var(--muted); font-family: var(--mono); font-size: 11px; letter-spacing: .12em; text-transform: uppercase; }}
    .room-folder-header {{ cursor: context-menu; display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
    .room-folder-header::before {{ content: '▾'; color: var(--accent); font-size: 10px; }}
    .room-entry {{ display: block; border-bottom: 1px solid var(--line-soft); cursor: context-menu; }}
    .room-entry:last-child {{ border-bottom: 0; }}
    .rooms a {{ display: block; color: var(--ink); text-decoration: none; padding: 12px 0; border: 0; border-radius: 0; margin-bottom: 0; background: transparent; }}
    .rooms a:hover, .room-entry.menu-open a {{ color: var(--accent); background: rgba(255,230,203,.045); }}
    .rooms a.active {{ color: var(--accent); background: rgba(255,230,203,.07); box-shadow: inset 3px 0 0 var(--accent); padding-left: 12px; padding-right: 10px; }}
    .rooms a.active .small {{ color: rgba(255,230,203,.78); }}
    .room-entry.pinned .room-title::before {{ content: '★ '; color: var(--accent); }}
    .room-title-row {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
    .current-room-badge {{ flex: 0 0 auto; border: 1px solid var(--accent); border-radius: 4px; color: #041c1c; background: var(--accent); padding: 2px 5px; font-family: var(--mono); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }}
    .room-folder-empty {{ margin: 4px 0 8px; border-color: var(--line-soft); padding: 10px 0; }}
    .context-menu {{ position: fixed; z-index: 50; min-width: 178px; display: grid; gap: 2px; padding: 6px; border: 1px solid var(--line); border-radius: 7px; background: rgba(4, 28, 28, .98); box-shadow: 0 18px 45px rgba(0,0,0,.35); }}
    .context-menu[hidden] {{ display: none; }}
    .context-menu button {{ width: 100%; border: 0; border-radius: 5px; background: transparent; color: var(--ink); cursor: pointer; font: 12px var(--body); text-align: left; padding: 8px 10px; }}
    .context-menu button:hover {{ color: #041c1c; background: var(--accent); }}
    .context-menu button.danger {{ color: var(--bad); }}
    .context-menu button.danger:hover {{ color: #fff; background: rgba(251,113,133,.78); }}
    .room-title {{ font-weight: 700; overflow-wrap: anywhere; }}
    .small {{ color: var(--muted); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }}
    .stats {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0; margin: 0 0 18px; border-top: 1px solid var(--line-soft); border-bottom: 1px solid var(--line-soft); }}
    .stat {{ padding: 10px 14px; background: transparent; border: 0; border-right: 1px solid var(--line-soft); border-radius: 0; }}
    .stat:last-child {{ border-right: 0; }}
    .stat strong {{ display: block; font-size: 28px; }}
    .stat span {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    .status-line {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 18px; }}
    .controls {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin: 0 0 16px; padding: 0 0 14px; border: 0; border-bottom: 1px solid var(--line-soft); border-radius: 0; background: transparent; }}
    .control-field {{ display: grid; gap: 5px; min-width: 0; }}
    .control-field label, .check-field {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }}
    .control-field select {{ width: 100%; border: 1px solid var(--line); border-radius: 5px; background: #0b0b0b; color: var(--ink); padding: 8px 9px; font-family: var(--body); }}
    .check-field {{ display: flex; gap: 8px; align-items: center; padding-top: 19px; }}
    .check-field input {{ accent-color: var(--accent); }}
    .pagination {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 0 0 14px; }}
    .pager-buttons {{ display: flex; gap: 8px; }}
    .pager-buttons button {{ border: 1px solid var(--line); border-radius: 5px; background: rgba(255,255,255,.04); color: var(--ink); padding: 8px 11px; cursor: pointer; }}
    .pager-buttons button:disabled {{ opacity: .45; cursor: not-allowed; }}
    .pill {{ border: 1px solid var(--line); border-radius: 4px; padding: 7px 10px; font-size: 12px; color: var(--muted); background: rgba(255,255,255,.03); }}
    .pill.hot {{ color: #041c1c; background: var(--accent); border-color: var(--accent); }}
    .pill.ok {{ color: #06140b; background: var(--ok); border-color: var(--ok); }}
    .timeline {{ display: flex; flex-direction: column; gap: 0; border-top: 1px solid var(--line-soft); }}
    .event {{ position: relative; border: 0; border-bottom: 1px solid var(--line-soft); border-radius: 0; background: transparent; padding: 16px 4px 16px 18px; }}
    .event::before {{ content: ''; position: absolute; left: 0; top: 10px; bottom: 10px; width: 3px; border-radius: 2px; background: var(--event-bar, var(--line)); }}
    .event:hover {{ background: rgba(255,230,203,.035); }}
    .event.message {{ --event-bar: var(--accent-2); }}
    .event.artifact {{ --event-bar: var(--accent); }}
    .event.gate {{ --event-bar: var(--bad); }}
    .event.open_need {{ --event-bar: #a78bfa; }}
    .event-head {{ display: flex; gap: 10px; justify-content: space-between; align-items: start; margin-bottom: 8px; }}
    .event-title {{ font-weight: 760; }}
    .event-meta {{ color: var(--muted); font-family: var(--mono); font-size: 12px; }}
    .event-tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 0; }}
    .tag {{ border: 1px solid var(--line); border-radius: 4px; padding: 3px 6px; color: var(--muted); font-family: var(--mono); font-size: 11px; background: rgba(255,255,255,.028); }}
    .agent-group {{ display: grid; gap: 0; margin-bottom: 18px; }}
    .agent-group h3 {{ margin: 16px 0 0; padding: 8px 0; border: 0; border-bottom: 1px solid var(--line-soft); border-radius: 0; background: transparent; color: var(--accent-2); font-family: var(--mono); font-size: 13px; }}
    .event-markdown {{ line-height: 1.58; color: #e8e8e8; overflow-wrap: anywhere; }}
    .event-markdown p {{ margin: 0 0 10px; }}
    .event-markdown p:last-child {{ margin-bottom: 0; }}
    .event-markdown h1, .event-markdown h2, .event-markdown h3 {{ margin: 12px 0 8px; line-height: 1.2; letter-spacing: -.02em; }}
    .event-markdown h1 {{ font-size: 21px; }}
    .event-markdown h2 {{ font-size: 18px; }}
    .event-markdown h3 {{ font-size: 15px; }}
    .event-markdown ul, .event-markdown ol {{ margin: 6px 0 10px 20px; padding: 0; }}
    .event-markdown li {{ margin: 4px 0; }}
    .event-markdown blockquote {{ margin: 8px 0; padding: 7px 10px; border-left: 3px solid var(--accent); background: rgba(255,230,203,.06); color: #f4f4f4; }}
    .event-markdown pre {{ margin: 8px 0; padding: 10px; border: 1px solid var(--line-soft); border-radius: 6px; background: rgba(0,0,0,.24); overflow-x: auto; }}
    .event-markdown code {{ font-family: var(--mono); color: var(--accent); }}
    .agents {{ display: grid; gap: 0; margin: 0 0 18px; border-top: 1px solid var(--line-soft); }}
    .agent {{ display: flex; justify-content: space-between; gap: 12px; padding: 9px 0; border: 0; border-bottom: 1px solid var(--line-soft); border-radius: 0; background: transparent; }}
    .empty {{ color: var(--muted); border: 1px dashed var(--line); border-radius: 6px; padding: 16px; }}
    code {{ font-family: var(--mono); color: var(--accent); }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} .stats {{ grid-template-columns: repeat(2, 1fr); }} .controls {{ grid-template-columns: 1fr 1fr; }} }}
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <div class="brand">
        <h1 data-i18n="appTitle">Idea-Spark Live Room</h1>
        <span id="connection" class="badge">connecting</span>
        <span class="badge" data-i18n="readonlyLocal">read-only · localhost</span>
      </div>
      <div id="language-switch" class="language-switch" role="group" aria-label="Language">
        <button type="button" class="lang-button" data-lang-option="en" aria-pressed="false">EN</button>
        <button type="button" class="lang-button" data-lang-option="zh" aria-pressed="false">中文</button>
      </div>
    </div>
  </header>
  <main class="wrap">
    <div class="grid">
      <aside class="panel">
        <h2 data-i18n="roomsHeading">Rooms</h2>
        <div class="room-tools">
          <label for="room-group-mode" data-i18n="groupRoomsLabel">Group rooms</label>
          <select id="room-group-mode">
            <option value="none" data-i18n="groupRoomsNone">No grouping</option>
            <option value="status" data-i18n="groupRoomsStatus">Status</option>
            <option value="creator" data-i18n="groupRoomsCreator">Creator</option>
            <option value="protocol" data-i18n="groupRoomsProtocol">Protocol</option>
            <option value="day" data-i18n="groupRoomsDay">Created day</option>
          </select>
        </div>
        <div class="panel-body rooms" id="rooms"></div>
        <div id="room-area-menu" class="context-menu" role="menu" hidden>
          <button id="menu-create-folder" type="button" role="menuitem" data-i18n="createFolder">New folder</button>
        </div>
        <div id="room-context-menu" class="context-menu" role="menu" hidden>
          <button id="menu-pin-room" type="button" role="menuitem" data-i18n="pinRoom">Pin</button>
          <button id="menu-add-room-folder" type="button" role="menuitem" data-i18n="addToFolder">Add to group</button>
          <button id="menu-delete-room" class="danger" type="button" role="menuitem" data-i18n="deleteRoom">Delete room</button>
        </div>
        <div id="room-folder-menu" class="context-menu" role="menu" hidden>
          <button id="menu-rename-folder" type="button" role="menuitem" data-i18n="renameFolder">Rename folder</button>
          <button id="menu-delete-folder" class="danger" type="button" role="menuitem" data-i18n="deleteFolder">Delete folder</button>
        </div>
      </aside>
      <section class="panel">
        <h2 id="room-heading" data-i18n="liveMonitor">Live monitor</h2>
        <div class="panel-body">
          <div id="summary"></div>
          <div class="status-line" id="status-line"></div>
          <div class="status-line" id="discussion-state">
            <span class="pill" id="current-phase"></span>
            <span class="pill" id="latest-gate"></span>
            <span class="pill" id="open-need-summary"></span>
          </div>
          <div id="agents" class="agents"></div>
          <div style="height: 18px"></div>
          <div id="timeline-controls" class="controls" hidden>
            <div class="control-field">
              <label for="kind-filter" data-i18n="kindFilterLabel">Kind</label>
              <select id="kind-filter"></select>
            </div>
            <div class="control-field">
              <label for="agent-filter" data-i18n="agentFilterLabel">Subagent</label>
              <select id="agent-filter"></select>
            </div>
            <div class="control-field">
              <label for="tag-filter" data-i18n="tagFilterLabel">Tag</label>
              <select id="tag-filter"></select>
            </div>
            <div class="control-field">
              <label for="page-size" data-i18n="pageSizeLabel">Page size</label>
              <select id="page-size">
                <option value="10" selected>10</option>
                <option value="20">20</option>
                <option value="50">50</option>
                <option value="100">100</option>
              </select>
            </div>
            <label class="check-field" for="group-by-agent">
              <input id="group-by-agent" type="checkbox">
              <span data-i18n="groupByAgentLabel">Group by subagent</span>
            </label>
          </div>
          <div id="timeline-pagination" class="pagination" hidden>
            <span id="page-info" class="small"></span>
            <div class="pager-buttons">
              <button id="page-prev" type="button" data-i18n="prevPage">Prev</button>
              <button id="page-next" type="button" data-i18n="nextPage">Next</button>
            </div>
          </div>
          <div id="timeline-prototype" class="event-markdown" hidden></div>
          <div id="timeline" class="timeline"></div>
        </div>
      </section>
    </div>
  </main>
<script>
const ROOM_ID = {room_json};
const LANGUAGE_KEY = 'ideaSparkDashboardLanguage';
const ROOM_PIN_KEY = 'ideaSparkDashboardPinnedRooms';
const ROOM_GROUP_KEY = 'ideaSparkDashboardRoomGroupMode';
const ROOM_FOLDER_KEY = 'ideaSparkDashboardRoomFolders';
const TRANSLATIONS = {{
  en: {{
    appTitle: 'Idea-Spark Live Room',
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
    appTitle: 'Idea-Spark 实时房间',
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
let uiState = {{kind: 'all', agent: 'all', tag: 'all', page: 1, pageSize: 10, groupByAgent: false}};
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
  for (const raw of lines) {{
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
  controls.hidden = false;
  pagination.hidden = false;
  const options = data.filter_options || {{}};
  uiState.kind = fillSelect('kind-filter', options.kinds || [], t('allKinds'), uiState.kind, eventKindText);
  uiState.agent = fillSelect('agent-filter', options.agents || [], t('allAgents'), uiState.agent);
  uiState.tag = fillSelect('tag-filter', options.tags || [], t('allTags'), uiState.tag);
  const pageSize = $('page-size');
  if (pageSize) pageSize.value = String(uiState.pageSize);
  const group = $('group-by-agent');
  if (group) group.checked = Boolean(uiState.groupByAgent);
}}
function setupTimelineControls() {{
  const pairs = [
    ['kind-filter', 'kind'],
    ['agent-filter', 'agent'],
    ['tag-filter', 'tag'],
  ];
  for (const [id, key] of pairs) {{
    const el = $(id);
    if (el) el.addEventListener('change', () => {{ uiState[key] = el.value || 'all'; uiState.page = 1; if (lastSnapshot) renderTimelinePage(lastSnapshot); }});
  }}
  const size = $('page-size');
  if (size) size.addEventListener('change', () => {{ uiState.pageSize = Number(size.value) || 20; uiState.page = 1; if (lastSnapshot) renderTimelinePage(lastSnapshot); }});
  const group = $('group-by-agent');
  if (group) group.addEventListener('change', () => {{ uiState.groupByAgent = group.checked; uiState.page = 1; if (lastSnapshot) renderTimelinePage(lastSnapshot); }});
  const prev = $('page-prev');
  if (prev) prev.addEventListener('click', () => {{ uiState.page = Math.max(1, uiState.page - 1); if (lastSnapshot) renderTimelinePage(lastSnapshot); }});
  const next = $('page-next');
  if (next) next.addEventListener('click', () => {{ uiState.page += 1; if (lastSnapshot) renderTimelinePage(lastSnapshot); }});
}}
function filteredTimeline(data) {{
  const events = (data && data.timeline) ? data.timeline : [];
  return events.filter((event) => {{
    if (uiState.kind !== 'all' && event.kind !== uiState.kind) return false;
    if (uiState.agent !== 'all' && event.actor !== uiState.agent) return false;
    if (uiState.tag !== 'all' && !(event.tags || []).includes(uiState.tag)) return false;
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
function renderEventCard(event) {{
  const card = node('article', 'event ' + event.kind);
  const head = node('div', 'event-head');
  head.append(node('div', 'event-title', eventKindText(event.kind) + ' · ' + (event.title || event.id)));
  head.append(node('div', 'event-meta', (event.created_at || '-') + ' · ' + (event.actor || '-') + ' · ' + (event.role || '-')));
  card.appendChild(head);
  const body = node('div', 'event-markdown');
  renderMarkdown(body, event.content_text !== undefined ? event.content_text : event.content);
  card.appendChild(body);
  if ((event.tags || []).length) {{
    const tags = node('div', 'event-tags');
    for (const tag of event.tags) tags.appendChild(node('span', 'tag', tag));
    card.appendChild(tags);
  }}
  return card;
}}
function renderTimelinePage(data) {{
  const timeline = $('timeline');
  const pageInfo = $('page-info');
  const prev = $('page-prev');
  const next = $('page-next');
  timeline.replaceChildren();
  const events = filteredTimeline(data);
  const pageSize = Math.max(1, Number(uiState.pageSize) || 20);
  const pageCount = Math.max(1, Math.ceil(events.length / pageSize));
  uiState.page = Math.min(Math.max(1, uiState.page), pageCount);
  const start = (uiState.page - 1) * pageSize;
  const pageEvents = events.slice(start, start + pageSize);
  if (!pageEvents.length) {{
    timeline.appendChild(node('div', 'empty', t('noTimeline')));
  }} else if (uiState.groupByAgent) {{
    for (const [actor, group] of groupEventsByAgent(pageEvents)) {{
      const section = node('section', 'agent-group');
      section.appendChild(node('h3', null, actor));
      for (const event of group) section.appendChild(renderEventCard(event));
      timeline.appendChild(section);
    }}
  }} else {{
    for (const event of pageEvents) timeline.appendChild(renderEventCard(event));
  }}
  if (pageInfo) {{
    const end = events.length ? Math.min(events.length, start + pageEvents.length) : 0;
    const first = events.length ? start + 1 : 0;
    pageInfo.textContent = t('paginationShowing') + ' ' + first + '–' + end + ' ' + t('paginationOf') + ' ' + events.length + ' · ' + t('pageLabel') + ' ' + uiState.page + '/' + pageCount;
  }}
  if (prev) prev.disabled = uiState.page <= 1;
  if (next) next.disabled = uiState.page >= pageCount;
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
  const folderAssigned = new Set(roomPrefs.folders.flatMap((folder) => folder.roomIds));
  const pinned = rooms.filter((room) => roomPrefs.pinned.has(room.room_id));
  const others = rooms.filter((room) => !roomPrefs.pinned.has(room.room_id) && !folderAssigned.has(room.room_id));
  appendRoomSection(box, pinned.length ? t('pinnedRooms') : '', pinned);
  for (const folder of roomPrefs.folders) renderRoomFolderSection(box, folder, roomLookup);
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
  const row = node('div');
  row.className = 'room-entry';
  if (pinned) row.classList.add('pinned');
  row.dataset.roomId = room.room_id;
  row.addEventListener('contextmenu', (event) => {{
    event.preventDefault();
    event.stopPropagation();
    openRoomContextMenu(event, room);
  }});
  const a = node('a');
  a.href = '/room/' + encodeURIComponent(room.room_id);
  a.className = active ? 'room-link active' : 'room-link';
  if (active) a.setAttribute('aria-current', 'page');
  const titleRow = node('div', 'room-title-row');
  titleRow.appendChild(node('div', 'room-title', roomTitle(room)));
  if (active) titleRow.appendChild(node('span', 'current-room-badge', t('currentRoom')));
  const meta = node('div', 'small', room.room_id + ' · ' + t('stats.messages') + ' ' + room.counts.messages + ' · ' + t('stats.artifacts') + ' ' + room.counts.artifacts);
  a.append(titleRow, meta);
  row.append(a);
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
  const data = await res.json();
  renderRoomGroups(data.rooms || []);
}}
function renderSnapshot(data) {{
  lastSnapshot = data;
  if (!data.success) {{
    $('summary').replaceChildren(node('div', 'empty', data.error || t('noSnapshot')));
    return;
  }}
  document.title = (data.room.title || data.room.room_id) + ' · ' + t('appTitle');
  $('room-heading').textContent = data.room.title || data.room.room_id;
  const stats = node('div', 'stats');
  for (const [label, value] of Object.entries(data.counts)) {{
    const card = node('div', 'stat');
    card.append(node('strong', null, String(value)), node('span', null, t('stats.' + label, label)));
    stats.appendChild(card);
  }}
  $('summary').replaceChildren(stats);

  const status = $('status-line');
  status.replaceChildren();
  status.append(node('span', 'pill hot', statusText(data.room.status)));
  status.append(node('span', 'pill', t('roomPrefix') + ' ' + data.room.room_id));
  status.append(node('span', 'pill', t('updatedPrefix') + ' ' + data.generated_at));
  if (data.missing_expected_agents.length === 0) status.append(node('span', 'pill ok', t('allAgentsJoined')));
  else status.append(node('span', 'pill', t('missingPrefix') + ' ' + data.missing_expected_agents.join(', ')));

  const agents = $('agents');
  agents.replaceChildren();
  if (data.participants.length === 0) agents.appendChild(node('div', 'empty', t('noAgents')));
  for (const participant of data.participants) {{
    const row = node('div', 'agent');
    row.append(node('span', null, participant.agent_id + ' · ' + (participant.role || t('agentFallback'))));
    row.append(node('span', 'small', participant.last_seen_at));
    agents.appendChild(row);
  }}

  buildFilterControls(data);
  renderDiscussionState(data);
  renderTimelinePage(data);
}}
async function pollSnapshot() {{
  if (!ROOM_ID) return;
  const res = await fetch('/api/rooms/' + encodeURIComponent(ROOM_ID) + '/snapshot', {{cache: 'no-store'}});
  renderSnapshot(await res.json());
}}
function connectEvents() {{
  if (!ROOM_ID || !window.EventSource) {{
    setConnection('polling', '');
    setInterval(pollSnapshot, 1500);
    pollSnapshot();
    return;
  }}
  const source = new EventSource('/api/rooms/' + encodeURIComponent(ROOM_ID) + '/events');
  source.addEventListener('open', () => setConnection('liveViaSSE', 'ok'));
  source.addEventListener('snapshot', (event) => renderSnapshot(JSON.parse(event.data)));
  source.addEventListener('error', () => {{
    setConnection('sseReconnecting', '');
  }});
}}
setupLanguageSwitch();
setupRoomControls();
setupTimelineControls();
applyStaticTranslations();
renderConnection();
loadRooms().catch(() => setConnection('roomsFailed', ''));
if (ROOM_ID) connectEvents();
else setConnection('selectRoom', '');
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
