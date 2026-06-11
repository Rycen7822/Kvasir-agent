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

from .store import default_db_path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_POLL_INTERVAL_S = 0.75
DEFAULT_LIMIT = 200


def _loads(value: str | None, default):
    if not value:
        return default
    return json.loads(value)


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


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
        return item

    @staticmethod
    def _artifact_dict(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item.pop("_rowid", None)
        item["content"] = _loads(item.pop("content_json"), {})
        item["metadata"] = _loads(item.pop("metadata_json"), {})
        return item

    @staticmethod
    def _gate_dict(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["input_artifact_ids"] = _loads(item.pop("input_artifact_ids_json"), [])
        item["score"] = _loads(item.pop("score_json"), {})
        item["metadata"] = _loads(item.pop("metadata_json"), {})
        return item

    @staticmethod
    def _need_dict(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["metadata"] = _loads(item.pop("metadata_json"), {})
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

        expected = self._expected_agents(room)
        joined = {participant["agent_id"] for participant in participants}
        missing = [agent for agent in expected if agent not in joined]
        timeline = self._timeline(messages, artifacts, gates, open_needs)
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
            "counts": counts,
            "cursor": counts,
            "db_path": str(self.db_path),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
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
                    "artifact_ids": message.get("artifact_ids", []),
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
                    "title": artifact.get("title") or artifact["artifact_type"],
                    "status": artifact["status"],
                    "content": artifact.get("content"),
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
                    "title": f"gate: {gate['decision']}",
                    "content": gate["rationale"],
                    "input_artifact_ids": gate.get("input_artifact_ids", []),
                    "score": gate.get("score", {}),
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
                    "title": need["query"],
                    "status": need["status"],
                    "pressure_score": need["pressure_score"],
                    "content": need["rationale"],
                }
            )
        order = {"message": 0, "artifact": 1, "gate": 2, "open_need": 3}
        return sorted(events, key=lambda event: (event.get("created_at") or "", order.get(event["kind"], 99), event["id"]))


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
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Idea-Spark Live Room</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #050505;
      --panel: #111111;
      --panel-2: #181818;
      --ink: #f1f1f1;
      --muted: #9b9b9b;
      --line: #2a2a2a;
      --accent: #ffd166;
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
        radial-gradient(circle at top left, rgba(255, 209, 102, .14), transparent 30rem),
        radial-gradient(circle at 90% 10%, rgba(94, 234, 212, .11), transparent 24rem),
        linear-gradient(135deg, #020202 0%, var(--bg) 45%, #0b0b0b 100%);
      color: var(--ink);
      font-family: var(--body);
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 5;
      backdrop-filter: blur(18px);
      background: rgba(5, 5, 5, .82);
      border-bottom: 1px solid var(--line);
      padding: 18px 24px;
    }}
    .wrap {{ max-width: 1440px; margin: 0 auto; padding: 24px; }}
    .brand {{ display: flex; gap: 14px; align-items: baseline; flex-wrap: wrap; }}
    h1 {{ margin: 0; font-size: clamp(28px, 4vw, 54px); letter-spacing: -.06em; }}
    .badge {{ border: 1px solid var(--line); border-radius: 999px; padding: 6px 10px; color: var(--muted); font-family: var(--mono); font-size: 12px; }}
    .grid {{ display: grid; grid-template-columns: 330px minmax(0, 1fr); gap: 18px; align-items: start; }}
    .panel {{ background: rgba(17, 17, 17, .88); border: 1px solid var(--line); border-radius: 18px; box-shadow: 0 20px 80px rgba(0,0,0,.35); overflow: hidden; }}
    .panel h2 {{ margin: 0; padding: 16px 18px; border-bottom: 1px solid var(--line); font-size: 14px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }}
    .panel-body {{ padding: 16px 18px; }}
    .rooms a {{ display: block; color: var(--ink); text-decoration: none; padding: 13px; border: 1px solid var(--line); border-radius: 14px; margin-bottom: 10px; background: var(--panel-2); }}
    .rooms a:hover {{ border-color: var(--accent); }}
    .room-title {{ font-weight: 700; }}
    .small {{ color: var(--muted); font-size: 12px; line-height: 1.5; }}
    .stats {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin: 0 0 18px; }}
    .stat {{ padding: 14px; background: var(--panel); border: 1px solid var(--line); border-radius: 16px; }}
    .stat strong {{ display: block; font-size: 28px; }}
    .stat span {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    .status-line {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 18px; }}
    .pill {{ border: 1px solid var(--line); border-radius: 999px; padding: 7px 10px; font-size: 12px; color: var(--muted); background: rgba(255,255,255,.03); }}
    .pill.hot {{ color: #111; background: var(--accent); border-color: var(--accent); }}
    .pill.ok {{ color: #06140b; background: var(--ok); border-color: var(--ok); }}
    .timeline {{ display: flex; flex-direction: column; gap: 12px; }}
    .event {{ border: 1px solid var(--line); border-radius: 17px; background: linear-gradient(180deg, rgba(255,255,255,.045), rgba(255,255,255,.018)); padding: 14px; }}
    .event.message {{ border-left: 4px solid var(--accent-2); }}
    .event.artifact {{ border-left: 4px solid var(--accent); }}
    .event.gate {{ border-left: 4px solid var(--bad); }}
    .event.open_need {{ border-left: 4px solid #a78bfa; }}
    .event-head {{ display: flex; gap: 10px; justify-content: space-between; align-items: start; margin-bottom: 8px; }}
    .event-title {{ font-weight: 760; }}
    .event-meta {{ color: var(--muted); font-family: var(--mono); font-size: 12px; }}
    .event-content {{ white-space: pre-wrap; line-height: 1.55; color: #e8e8e8; }}
    .agents {{ display: grid; gap: 10px; }}
    .agent {{ display: flex; justify-content: space-between; gap: 12px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel-2); }}
    .empty {{ color: var(--muted); border: 1px dashed var(--line); border-radius: 14px; padding: 16px; }}
    code {{ font-family: var(--mono); color: var(--accent); }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} .stats {{ grid-template-columns: repeat(2, 1fr); }} }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <h1>Idea-Spark Live Room</h1>
      <span id="connection" class="badge">connecting</span>
      <span class="badge">read-only · localhost</span>
    </div>
  </header>
  <main class="wrap">
    <div class="grid">
      <aside class="panel">
        <h2>Rooms</h2>
        <div class="panel-body rooms" id="rooms"></div>
      </aside>
      <section class="panel">
        <h2 id="room-heading">Live monitor</h2>
        <div class="panel-body">
          <div id="summary"></div>
          <div class="status-line" id="status-line"></div>
          <div id="agents" class="agents"></div>
          <div style="height: 18px"></div>
          <div id="timeline" class="timeline"></div>
        </div>
      </section>
    </div>
  </main>
<script>
const ROOM_ID = {room_json};
const $ = (id) => document.getElementById(id);
function node(tag, className, text) {{
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined && text !== null) el.textContent = text;
  return el;
}}
function asText(value) {{
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}}
function setConnection(text, cls) {{
  const el = $('connection');
  el.textContent = text;
  el.className = 'badge ' + (cls || '');
}}
async function loadRooms() {{
  const res = await fetch('/api/rooms', {{cache: 'no-store'}});
  const data = await res.json();
  const box = $('rooms');
  box.replaceChildren();
  if (!data.rooms || data.rooms.length === 0) {{
    box.appendChild(node('div', 'empty', 'No Idea-Spark rooms found yet.'));
    return;
  }}
  for (const room of data.rooms) {{
    const a = node('a');
    a.href = '/room/' + encodeURIComponent(room.room_id);
    const title = node('div', 'room-title', room.title || room.room_id);
    const meta = node('div', 'small', `${{room.room_id}} · messages ${{room.counts.messages}} · artifacts ${{room.counts.artifacts}}`);
    a.append(title, meta);
    box.appendChild(a);
  }}
}}
function renderSnapshot(data) {{
  if (!data.success) {{
    $('summary').replaceChildren(node('div', 'empty', data.error || 'No snapshot'));
    return;
  }}
  document.title = `${{data.room.title || data.room.room_id}} · Idea-Spark Live Room`;
  $('room-heading').textContent = data.room.title || data.room.room_id;
  const stats = node('div', 'stats');
  for (const [label, value] of Object.entries(data.counts)) {{
    const card = node('div', 'stat');
    card.append(node('strong', null, String(value)), node('span', null, label));
    stats.appendChild(card);
  }}
  $('summary').replaceChildren(stats);

  const status = $('status-line');
  status.replaceChildren();
  status.append(node('span', 'pill hot', data.room.status));
  status.append(node('span', 'pill', `room ${{data.room.room_id}}`));
  status.append(node('span', 'pill', `updated ${{data.generated_at}}`));
  if (data.missing_expected_agents.length === 0) status.append(node('span', 'pill ok', 'all expected agents joined'));
  else status.append(node('span', 'pill', `missing ${{data.missing_expected_agents.join(', ')}}`));

  const agents = $('agents');
  agents.replaceChildren();
  if (data.participants.length === 0) agents.appendChild(node('div', 'empty', 'No child agents have joined this room.'));
  for (const participant of data.participants) {{
    const row = node('div', 'agent');
    row.append(node('span', null, `${{participant.agent_id}} · ${{participant.role || 'agent'}}`));
    row.append(node('span', 'small', participant.last_seen_at));
    agents.appendChild(row);
  }}

  const timeline = $('timeline');
  timeline.replaceChildren();
  if (data.timeline.length === 0) timeline.appendChild(node('div', 'empty', 'No messages or artifacts yet.'));
  for (const event of data.timeline) {{
    const card = node('article', 'event ' + event.kind);
    const head = node('div', 'event-head');
    head.append(node('div', 'event-title', `${{event.kind}} · ${{event.title || event.id}}`));
    head.append(node('div', 'event-meta', `${{event.created_at || '-'}} · ${{event.actor || '-'}} · ${{event.role || '-'}}`));
    card.appendChild(head);
    card.appendChild(node('div', 'event-content', asText(event.content)));
    timeline.appendChild(card);
  }}
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
  source.addEventListener('open', () => setConnection('live via SSE', 'ok'));
  source.addEventListener('snapshot', (event) => renderSnapshot(JSON.parse(event.data)));
  source.addEventListener('error', () => {{
    setConnection('SSE reconnecting', '');
  }});
}}
loadRooms().catch(err => setConnection('rooms failed: ' + err.message));
if (ROOM_ID) connectEvents();
else setConnection('select a room', '');
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

    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = "IdeaSparkDashboard/0.1"

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - inherited API
            return

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Allow", "GET, HEAD, OPTIONS")
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
            self._reject_mutation()

        def _reject_mutation(self) -> None:
            _json_response(self, {"success": False, "error": "dashboard is read-only"}, HTTPStatus.METHOD_NOT_ALLOWED)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            if path == "/health":
                _json_response(self, {"status": "ok", "read_only": True, "db_path": str(reader.db_path)})
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
        description="Idea-Spark realtime dashboard: local read-only browser monitor for room messages, artifacts, gates, and open needs."
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
    print("Idea-Spark realtime dashboard (read-only)", flush=True)
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
