import json
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
    artifact = call(
        idea_spark_artifact_create,
        {
            "room_id": room["room_id"],
            "type": "AtomicClaim",
            "title": "Claim from prior",
            "content": "Nearest prior art challenges the novelty claim.",
            "created_by": "prior",
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
    assert rooms[0]["counts"] == {"participants": 1, "messages": 1, "artifacts": 2, "gates": 1, "open_needs": 1}

    snapshot = reader.room_snapshot(room_id)
    assert snapshot["success"] is True
    assert snapshot["room"]["title"] == "Dashboard Room"
    assert snapshot["participants"][0]["agent_id"] == "prior"
    assert snapshot["missing_expected_agents"] == ["feasibility"]
    assert snapshot["messages"][0]["content"].startswith("I found a close prior-art match")
    assert snapshot["artifacts"][0]["artifact_id"] == artifact_id
    assert any(event["kind"] == "message" for event in snapshot["timeline"])
    assert any(event["kind"] == "artifact" for event in snapshot["timeline"])
    assert any(event["kind"] == "gate" for event in snapshot["timeline"])
    assert any(event["kind"] == "open_need" for event in snapshot["timeline"])
    assert snapshot["cursor"]["messages"] == 1


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
        assert read_json(f"{base_url}/health")["status"] == "ok"
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


def test_dashboard_html_uses_compact_industrial_radii():
    import re

    from idea_spark import dashboard

    html = dashboard._room_html("radius-room")
    radii = [int(value) for value in re.findall(r"border-radius:\s*(\d+)px", html)]

    assert radii
    assert max(radii) <= 10
    assert "border-radius: 999px" not in html
    for large_literal in ["border-radius: 12px", "border-radius: 14px", "border-radius: 16px", "border-radius: 17px", "border-radius: 18px", "border-radius: 22px"]:
        assert large_literal not in html


def test_dashboard_module_cli_help_explains_local_readonly_server():
    result = subprocess.run(
        [sys.executable, "-m", "idea_spark.dashboard", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "Idea-Spark realtime dashboard" in result.stdout
    assert "--host" in result.stdout
    assert "--port" in result.stdout
    assert "read-only" in result.stdout.lower()
