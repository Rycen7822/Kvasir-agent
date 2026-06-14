import json
import sqlite3
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

from idea_spark.tools import (
    idea_spark_artifact_create,
    idea_spark_gate_record,
    idea_spark_message_post,
    idea_spark_need_create,
    idea_spark_need_update,
    idea_spark_room_create,
    idea_spark_room_join,
)


def call(handler, payload):
    result = json.loads(handler(payload))
    assert result["success"] is True, result
    return result


def seed_room():
    room = call(
        idea_spark_room_create,
        {
            "room_id": "dashboard-room",
            "title": "Dashboard Room",
            "topic": "Watch subagents debate in real time",
            "created_by": "parent",
            "metadata": {"expected_agents": ["prior", "feasibility"]},
        },
    )
    call(
        idea_spark_room_join,
        {
            "room_id": room["room_id"],
            "agent_id": "prior",
            "role": "PriorArtBreaker",
            "display_name": "Prior Art Breaker",
        },
    )
    call(
        idea_spark_room_join,
        {
            "room_id": room["room_id"],
            "agent_id": "feasibility",
            "role": "FeasibilityBreaker",
            "display_name": "Feasibility Breaker",
        },
    )
    artifact = call(
        idea_spark_artifact_create,
        {
            "room_id": room["room_id"],
            "type": "AtomicClaim",
            "title": "Claim from prior",
            "content": "## Novelty note\n\n- Nearest prior art challenges the **novelty** claim.",
            "created_by": "prior",
            "metadata": {"tags": ["novelty", "prior-art"]},
        },
    )
    feasibility_artifact = call(
        idea_spark_artifact_create,
        {
            "room_id": room["room_id"],
            "type": "ExperimentPlan",
            "title": "Feasibility plan",
            "content": {"plan": "Run a fixed-candidate ablation."},
            "created_by": "feasibility",
            "metadata": {"tags": ["experiment"]},
        },
    )
    call(
        idea_spark_message_post,
        {
            "room_id": room["room_id"],
            "round_id": "r1",
            "phase": "review",
            "agent_id": "prior",
            "role": "PriorArtBreaker",
            "content": "I found a close prior-art match; recording an AtomicClaim.",
            "artifact_ids": [artifact["artifact_id"]],
        },
    )
    call(
        idea_spark_message_post,
        {
            "room_id": room["room_id"],
            "round_id": "r1",
            "phase": "review",
            "agent_id": "feasibility",
            "role": "FeasibilityBreaker",
            "content": "Feasibility depends on a fixed-candidate benchmark.",
            "artifact_ids": [feasibility_artifact["artifact_id"]],
        },
    )
    call(
        idea_spark_need_create,
        {
            "room_id": room["room_id"],
            "target_artifact_type": "PriorArtEvidence",
            "query": "Find the closest paper and official implementation.",
            "rationale": "The live monitor should show unresolved needs.",
            "pressure_score": 0.7,
            "created_by": "prior",
        },
    )
    call(
        idea_spark_gate_record,
        {
            "room_id": room["room_id"],
            "gate_type": "smoke",
            "input_artifact_ids": [artifact["artifact_id"]],
            "decision": "needs_more_evidence",
            "rationale": "Need feasibility evidence before accepting.",
            "decided_by": "gatekeeper",
        },
    )
    return room["room_id"], artifact["artifact_id"]


def read_json(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        assert response.status == 200
        return json.loads(response.read().decode("utf-8"))


def request_json(url, *, method="GET"):
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def read_http_error_json(url, *, method="GET"):
    request = urllib.request.Request(url, method=method)
    try:
        urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    raise AssertionError(f"{method} {url} should have failed")


def read_text(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        assert response.status == 200
        return response.read().decode("utf-8")


def start_server(dashboard, db_path):
    server = dashboard.create_server("127.0.0.1", 0, db_path=db_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def test_dashboard_reader_lists_rooms_and_builds_live_snapshot(temp_idea_spark_db):
    from idea_spark.dashboard import DashboardReader

    room_id, artifact_id = seed_room()
    reader = DashboardReader(temp_idea_spark_db)

    rooms = reader.list_rooms()
    assert [room["room_id"] for room in rooms] == [room_id]
    assert rooms[0]["counts"] == {"participants": 2, "messages": 2, "artifacts": 3, "gates": 1, "open_needs": 1}

    snapshot = reader.room_snapshot(room_id)
    assert snapshot["success"] is True
    assert snapshot["room"]["title"] == "Dashboard Room"
    assert snapshot["participants"][0]["agent_id"] == "feasibility"
    assert snapshot["missing_expected_agents"] == []
    assert snapshot["messages"][0]["content"].startswith("I found a close prior-art match")
    assert snapshot["artifacts"][0]["artifact_id"] == artifact_id
    assert snapshot["artifacts"][0]["content_text"].startswith("## Novelty note")
    assert "{\"text\"" not in snapshot["artifacts"][0]["content_text"]
    assert any(event["kind"] == "message" for event in snapshot["timeline"])
    assert any(event["kind"] == "artifact" for event in snapshot["timeline"])
    assert any(event["kind"] == "gate" for event in snapshot["timeline"])
    assert any(event["kind"] == "open_need" for event in snapshot["timeline"])
    assert any(event["actor"] == "feasibility" for event in snapshot["timeline"])
    assert "novelty" in snapshot["filter_options"]["tags"]
    assert "artifact:AtomicClaim" in snapshot["filter_options"]["tags"]
    assert "phase:review" in snapshot["filter_options"]["tags"]
    assert snapshot["filter_options"]["agents"] == ["feasibility", "gatekeeper", "prior"]
    assert snapshot["cursor"]["messages"] == 2


def test_dashboard_reader_exposes_discussion_gate_and_need_state(temp_idea_spark_db):
    from idea_spark.dashboard import DashboardReader

    room_id, artifact_id = seed_room()
    claimed = call(
        idea_spark_need_create,
        {
            "room_id": room_id,
            "target_artifact_type": "BenchmarkRequirement",
            "query": "Claimed benchmark gap",
            "rationale": "Needs a benchmark owner.",
            "pressure_score": 0.4,
            "created_by": "feasibility",
        },
    )
    call(
        idea_spark_need_update,
        {
            "room_id": room_id,
            "need_id": claimed["need_id"],
            "status": "claimed",
            "claimed_by_agent": "feasibility",
            "updated_by": "feasibility",
        },
    )
    resolved = call(
        idea_spark_need_create,
        {
            "room_id": room_id,
            "target_artifact_type": "PriorArtEvidence",
            "query": "Resolved prior-art gap",
            "rationale": "Need has an answer.",
            "pressure_score": 0.2,
            "created_by": "prior",
        },
    )
    call(
        idea_spark_need_update,
        {
            "room_id": room_id,
            "need_id": resolved["need_id"],
            "status": "resolved",
            "updated_by": "prior",
        },
    )
    call(
        idea_spark_gate_record,
        {
            "room_id": room_id,
            "gate_type": "final",
            "input_artifact_ids": [artifact_id],
            "decision": "needs_more_evidence",
            "rationale": "Latest gate with phase metadata.",
            "decided_by": "gatekeeper",
            "metadata": {"round_id": "r4", "phase": "Gate", "max_rounds": 4},
            "close_room": True,
        },
    )

    snapshot = DashboardReader(temp_idea_spark_db).room_snapshot(room_id)

    assert snapshot["latest_gate"]["decision"] == "needs_more_evidence"
    assert snapshot["has_terminal_gate"] is True
    assert snapshot["open_need_summary"]["open"] == 1
    assert snapshot["open_need_summary"]["claimed"] == 1
    assert snapshot["open_need_summary"]["resolved"] == 1
    assert snapshot["current_phase"] == "Gate"
    assert snapshot["cursor"]["last_message_id"] == 2
    assert snapshot["cursor"]["last_artifact_updated_at"] is not None
    assert snapshot["cursor"]["last_gate_created_at"] is not None
    assert snapshot["cursor"]["last_need_updated_at"] is not None


def test_dashboard_reader_handles_missing_database_without_writes(tmp_path):
    from idea_spark.dashboard import DashboardReader

    missing = tmp_path / "missing.sqlite3"
    reader = DashboardReader(missing)

    assert reader.list_rooms() == []
    snapshot = reader.room_snapshot("unknown")
    assert snapshot["success"] is False
    assert snapshot["error"] == "database not found"
    assert not missing.exists()


def test_dashboard_http_serves_health_html_json_sse_and_rejects_mutations(temp_idea_spark_db):
    from idea_spark import dashboard

    room_id, _ = seed_room()
    server, base_url = start_server(dashboard, temp_idea_spark_db)
    try:
        health = read_json(f"{base_url}/health")
        assert health["status"] == "ok"
        assert health["read_only"] is False
        assert health["room_delete_enabled"] is True
        rooms = read_json(f"{base_url}/api/rooms")
        assert rooms["rooms"][0]["room_id"] == room_id

        html = read_text(f"{base_url}/room/{room_id}")
        assert "Idea-Spark Live Room" in html
        assert room_id in html
        assert "EventSource" in html

        snapshot = read_json(f"{base_url}/api/rooms/{room_id}/snapshot")
        assert snapshot["room"]["title"] == "Dashboard Room"
        assert snapshot["messages"][0]["agent_id"] == "prior"

        sse = read_text(f"{base_url}/api/rooms/{room_id}/events?once=1")
        assert sse.startswith("event: snapshot")
        assert "data:" in sse
        assert "I found a close prior-art match" in sse

        request = urllib.request.Request(f"{base_url}/api/rooms", method="POST")
        try:
            urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            assert exc.code == 405
        else:
            raise AssertionError("POST should be rejected")
    finally:
        server.shutdown()
        server.server_close()


def test_dashboard_http_delete_room_requires_confirmation_and_removes_only_that_room(temp_idea_spark_db):
    from idea_spark import dashboard

    room_id, _ = seed_room()
    keep_room = call(
        idea_spark_room_create,
        {
            "room_id": "dashboard-keep-room",
            "title": "Keep Room",
            "topic": "This room must survive delete smoke",
            "created_by": "parent",
        },
    )["room_id"]
    server, base_url = start_server(dashboard, temp_idea_spark_db)
    try:
        code, payload = read_http_error_json(f"{base_url}/api/rooms/{room_id}", method="DELETE")
        assert code == 400
        assert payload["success"] is False
        assert "confirm" in payload["error"]

        code, payload = read_http_error_json(f"{base_url}/api/rooms/{room_id}?confirm=wrong", method="DELETE")
        assert code == 400
        assert payload["success"] is False

        status, payload = request_json(f"{base_url}/api/rooms/{room_id}?confirm={room_id}", method="DELETE")
        assert status == 200
        assert payload["success"] is True
        assert payload["room_id"] == room_id
        assert payload["deleted"]["rooms"] == 1
        assert payload["deleted"]["messages"] == 2
        assert payload["deleted"]["participants"] == 2
        assert payload["deleted"]["artifacts"] == 3
        assert payload["deleted"]["gates"] == 1
        assert payload["deleted"]["open_needs"] == 1

        rooms = read_json(f"{base_url}/api/rooms")["rooms"]
        assert [room["room_id"] for room in rooms] == [keep_room]
        missing_snapshot = read_json(f"{base_url}/api/rooms/{room_id}/snapshot")
        assert missing_snapshot["success"] is False
        assert missing_snapshot["error"] == "unknown room_id"

        with sqlite3.connect(temp_idea_spark_db) as conn:
            conn.row_factory = sqlite3.Row
            for table in ("participants", "messages", "artifacts", "artifact_links", "gates", "open_needs"):
                assert conn.execute(f"select count(*) from {table} where room_id = ?", (room_id,)).fetchone()[0] == 0
            assert conn.execute("select count(*) from rooms where room_id = ?", (room_id,)).fetchone()[0] == 0
            assert conn.execute("select count(*) from rooms where room_id = ?", (keep_room,)).fetchone()[0] == 1
    finally:
        server.shutdown()
        server.server_close()


def test_dashboard_html_uses_compact_industrial_radii():
    import re

    from idea_spark import dashboard

    html = dashboard._room_html("radius-room")
    radii = [int(value) for value in re.findall(r"border-radius:\s*(\d+)px", html)]

    assert radii
    assert max(radii) <= 10
    assert "border-radius: 999px" not in html
    for large_literal in [
        "border-radius: 12px",
        "border-radius: 14px",
        "border-radius: 16px",
        "border-radius: 17px",
        "border-radius: 18px",
        "border-radius: 22px",
    ]:
        assert large_literal not in html


def test_dashboard_html_uses_wide_flat_hermes_inspired_layout():
    from idea_spark import dashboard

    html = dashboard._room_html("layout-room")

    assert "max-width: 1440px" not in html
    assert "max-width: min(1880px, calc(100vw - 24px));" in html
    assert "--bg: #041c1c;" in html
    assert "--line-soft:" in html
    assert ".grid > section.panel { background: transparent; border: 0; box-shadow: none; overflow: visible; }" in html
    assert ".grid > section.panel .panel-body { padding: 0; }" in html
    assert ".stats { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0; margin: 0 0 18px; border-top: 1px solid var(--line-soft); border-bottom: 1px solid var(--line-soft); }" in html
    assert ".stat { padding: 10px 14px; background: transparent; border: 0; border-right: 1px solid var(--line-soft); border-radius: 0; }" in html
    assert ".controls { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin: 0 0 16px; padding: 0 0 14px; border: 0; border-bottom: 1px solid var(--line-soft); border-radius: 0; background: transparent; }" in html
    assert ".timeline { display: flex; flex-direction: column; gap: 0; border-top: 1px solid var(--line-soft); }" in html
    assert ".event { position: relative; border: 0; border-bottom: 1px solid var(--line-soft); border-radius: 0; background: transparent; padding: 16px 4px 16px 18px; }" in html
    assert ".event::before { content: ''; position: absolute; left: 0; top: 10px; bottom: 10px; width: 3px; border-radius: 2px; background: var(--event-bar, var(--line)); }" in html
    assert ".event.message { --event-bar: var(--accent-2); }" in html
    assert ".event.artifact { --event-bar: var(--accent); }" in html


def test_dashboard_html_marks_active_room_and_breaks_event_rails():
    from idea_spark import dashboard

    html = dashboard._room_html("active-room")

    assert ".rooms a.active { color: var(--accent); background: rgba(255,230,203,.07); box-shadow: inset 3px 0 0 var(--accent); padding-left: 12px; padding-right: 10px; }" in html
    assert ".current-room-badge" in html
    assert "currentRoom: 'current'" in html
    assert "currentRoom: '当前'" in html
    assert "const active = room.room_id === ROOM_ID;" in html
    assert "a.className = active ? 'room-link active' : 'room-link';" in html
    assert "a.setAttribute('aria-current', 'page');" in html
    assert "node('span', 'current-room-badge', t('currentRoom'))" in html
    assert ".event::before { content: ''; position: absolute; left: 0; top: 10px; bottom: 10px; width: 3px; border-radius: 2px; background: var(--event-bar, var(--line)); }" in html


def test_dashboard_html_exposes_pagination_filter_grouping_and_markdown_controls():
    from idea_spark import dashboard

    html = dashboard._room_html("controls-room")

    for marker in [
        'id="timeline-controls"',
        'id="kind-filter"',
        'id="agent-filter"',
        'id="tag-filter"',
        'id="group-by-agent"',
        'id="page-size"',
        'id="page-prev"',
        'id="page-next"',
        'id="page-info"',
        "function renderMarkdown",
        "function markdownToSafeHtml",
        "function contentText",
        "function filteredTimeline",
        "function renderTimelinePage",
        "function buildFilterControls",
        "function groupEventsByAgent",
    ]:
        assert marker in html

    assert "JSON.stringify(event.content" not in html
    assert 'class="event-markdown"' in html
    assert "groupByAgentLabel" in html
    assert "paginationShowing" in html


def test_dashboard_markdown_renderer_supports_pipe_tables():
    from idea_spark import dashboard

    html = dashboard._room_html("table-room")

    for marker in [
        "function splitMarkdownTableRow",
        "function parseMarkdownTableAlign",
        "function markdownTableAt",
        "function renderMarkdownTable",
        'class=\"table-wrap\"',
        "<table>",
        "<thead><tr>",
        "<tbody>",
        ".event-markdown table",
        ".event-markdown th",
        ".event-markdown td",
    ]:
        assert marker in html


def test_dashboard_html_exposes_room_context_menu_management():
    from idea_spark import dashboard

    html = dashboard._room_html("rooms-ui-room")

    for marker in [
        'id="room-group-mode"',
        'id="room-area-menu"',
        'id="room-context-menu"',
        'id="room-folder-menu"',
        'role="menu"',
        "ROOM_PIN_KEY",
        "ROOM_GROUP_KEY",
        "ROOM_FOLDER_KEY",
        "function loadRoomPrefs",
        "function saveRoomPrefs",
        "function createRoomFolder",
        "function renameRoomFolder",
        "function deleteRoomFolder",
        "function addRoomToFolder",
        "function openRoomAreaMenu",
        "function openRoomContextMenu",
        "function openRoomFolderMenu",
        "function closeRoomMenus",
        "function toggleRoomPin",
        "function deleteRoom",
        "function roomGroupKey",
        "function renderRoomGroups",
        "function renderRoomEntry",
        "addEventListener('contextmenu'",
        "className = 'room-entry'",
        "fetch('/api/rooms/' + encodeURIComponent(room.room_id) + '?confirm=' + encodeURIComponent(room.room_id), {method: 'DELETE'})",
        "confirm(t('deleteRoomConfirm')",
        "ideaSparkDashboardPinnedRooms",
        "ideaSparkDashboardRoomGroupMode",
        "ideaSparkDashboardRoomFolders",
        "createFolder: 'New folder'",
        "createFolder: '新建分组文件夹'",
        "addToFolder: 'Add to group'",
        "addToFolder: '添加到分组'",
        "renameFolder: 'Rename folder'",
        "renameFolder: '修改名称'",
        "deleteFolder: 'Delete folder'",
        "deleteFolder: '删除分组文件夹'",
        "pinnedRooms: 'Pinned rooms'",
        "pinnedRooms: '置顶房间'",
        "deleteRoom: 'Delete room'",
        "deleteRoom: '删除房间'",
        "groupRoomsLabel: 'Group rooms'",
        "groupRoomsLabel: '房间分组'",
    ]:
        assert marker in html

    forbidden = [
        "className = 'room-actions'",
        "className = pinned ? 'room-action pin active' : 'room-action pin'",
        "className = 'room-action danger'",
        ".room-actions",
        ".room-action",
    ]
    for marker in forbidden:
        assert marker not in html


def test_dashboard_html_exposes_discussion_state_controls_without_room_action_regression():
    from idea_spark import dashboard

    html = dashboard._room_html("discussion-state-room")

    for marker in [
        'id="discussion-state"',
        'id="latest-gate"',
        'id="open-need-summary"',
        "hasTerminalGate",
        "latestGate",
        "currentPhase",
        "openNeedSummary",
        "当前阶段",
        "最终 Gate",
        "未解决需求",
        "Current phase",
        "Final gate",
        "Unresolved needs",
    ]:
        assert marker in html

    for marker in ["className = 'room-actions'", ".room-actions", ".room-action"]:
        assert marker not in html


def test_dashboard_html_exposes_bilingual_language_switch():
    from idea_spark import dashboard

    html = dashboard._room_html("lang-room")

    assert 'id="language-switch"' in html
    assert 'data-lang-option="en"' in html
    assert 'data-lang-option="zh"' in html
    assert "ideaSparkDashboardLanguage" in html
    assert "const TRANSLATIONS" in html
    assert "function setLanguage" in html
    assert "function applyStaticTranslations" in html
    assert "localStorage" in html
    for required_text in [
        "Idea-Spark 实时房间",
        "房间",
        "实时监控",
        "本地管理 · localhost",
        "消息",
        "产物",
        "未加入",
        "全部预期代理已加入",
    ]:
        assert required_text in html


def test_dashboard_module_cli_help_explains_local_readonly_server():
    result = subprocess.run(
        [sys.executable, "-m", "idea_spark.dashboard", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "local management dashboard" in result.stdout
    assert "--host" in result.stdout
    assert "--port" in result.stdout
    assert "delete" in result.stdout.lower()
