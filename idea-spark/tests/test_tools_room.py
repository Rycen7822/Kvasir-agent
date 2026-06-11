import json

from idea_spark.tools import (
    idea_spark_artifact_create,
    idea_spark_gate_record,
    idea_spark_message_post,
    idea_spark_message_read,
    idea_spark_need_create,
    idea_spark_room_create,
    idea_spark_room_join,
    idea_spark_room_status,
    idea_spark_round_wait,
)


def call(handler, payload):
    return json.loads(handler(payload))


def make_room(expected_agents=None):
    payload = {
        "title": "test room",
        "topic": "evaluate an ML idea",
        "created_by": "parent",
        "metadata": {},
    }
    if expected_agents is not None:
        payload["metadata"]["expected_agents"] = expected_agents
    result = call(idea_spark_room_create, payload)
    assert result["success"] is True
    return result["room_id"]


def test_room_create_join_post_read_round_trip(temp_idea_spark_db):
    room_id = make_room(["agent-a"])

    joined = call(
        idea_spark_room_join,
        {"room_id": room_id, "agent_id": "agent-a", "role": "PriorArtBreaker", "display_name": "A"},
    )
    assert joined["success"] is True
    assert joined["status"] == "joined"

    posted = call(
        idea_spark_message_post,
        {
            "room_id": room_id,
            "round_id": "r1",
            "phase": "ideation",
            "agent_id": "agent-a",
            "role": "PriorArtBreaker",
            "content": "Claim needs prior-art check.",
            "artifact_ids": ["artifact-1"],
        },
    )
    assert posted["success"] is True
    assert isinstance(posted["message_id"], int)

    read = call(idea_spark_message_read, {"room_id": room_id})
    assert read["success"] is True
    assert read["messages"][0]["content"] == "Claim needs prior-art check."
    assert read["messages"][0]["artifact_ids"] == ["artifact-1"]


def test_round_wait_completes_when_expected_agents_arrive(temp_idea_spark_db):
    room_id = make_room(["agent-a", "agent-b"])
    for agent in ["agent-a", "agent-b"]:
        call(
            idea_spark_message_post,
            {
                "room_id": room_id,
                "round_id": "r1",
                "phase": "critique",
                "agent_id": agent,
                "content": f"{agent} arrived",
            },
        )

    waited = call(
        idea_spark_round_wait,
        {"room_id": room_id, "round_id": "r1", "phase": "critique", "timeout_s": 0.01},
    )

    assert waited["success"] is True
    assert waited["status"] == "complete"
    assert waited["arrived_agents"] == ["agent-a", "agent-b"]
    assert waited["missing_agents"] == []


def test_round_wait_times_out_without_deadlock_and_returns_partial_state(temp_idea_spark_db):
    room_id = make_room(["agent-a", "agent-b"])
    call(
        idea_spark_message_post,
        {
            "room_id": room_id,
            "round_id": "r1",
            "phase": "critique",
            "agent_id": "agent-a",
            "content": "only one agent arrived",
        },
    )

    waited = call(
        idea_spark_round_wait,
        {"room_id": room_id, "round_id": "r1", "phase": "critique", "timeout_s": 0.01},
    )

    assert waited["success"] is True
    assert waited["status"] == "timeout"
    assert waited["arrived_agents"] == ["agent-a"]
    assert waited["missing_agents"] == ["agent-b"]
    assert "continue with partial state" in waited["instruction"]


def test_round_wait_uses_per_call_expected_agents_without_mutating_room_metadata(temp_idea_spark_db):
    room_id = make_room(["prior", "feasibility", "author", "gatekeeper"])
    call(
        idea_spark_message_post,
        {
            "room_id": room_id,
            "round_id": "r2",
            "phase": "rebuttal",
            "agent_id": "author",
            "content": "author rebuttal arrived",
        },
    )

    waited = call(
        idea_spark_round_wait,
        {
            "room_id": room_id,
            "round_id": "r2",
            "phase": "rebuttal",
            "expected_agents": ["author"],
            "timeout_s": 0.01,
        },
    )

    assert waited["success"] is True
    assert waited["status"] == "complete"
    assert waited["arrived_agents"] == ["author"]
    assert waited["missing_agents"] == []

    status = call(idea_spark_room_status, {"room_id": room_id})
    assert status["expected_agents"] == ["prior", "feasibility", "author", "gatekeeper"]
    assert status["missing_expected_agents"] == ["prior", "feasibility", "author", "gatekeeper"]


def test_message_read_filters_and_limit_cap(temp_idea_spark_db):
    room_id = make_room()
    for i in range(205):
        call(
            idea_spark_message_post,
            {
                "room_id": room_id,
                "round_id": "r1" if i % 2 == 0 else "r2",
                "phase": "phase-a" if i % 2 == 0 else "phase-b",
                "agent_id": "agent-a" if i % 2 == 0 else "agent-b",
                "content": f"message {i}",
            },
        )

    capped = call(idea_spark_message_read, {"room_id": room_id, "limit": 999})
    assert capped["success"] is True
    assert len(capped["messages"]) == 200

    filtered = call(
        idea_spark_message_read,
        {"room_id": room_id, "round_id": "r1", "phase": "phase-a", "agent_id": "agent-a"},
    )
    assert filtered["success"] is True
    assert filtered["messages"]
    assert all(msg["round_id"] == "r1" for msg in filtered["messages"])
    assert all(msg["phase"] == "phase-a" for msg in filtered["messages"])
    assert all(msg["agent_id"] == "agent-a" for msg in filtered["messages"])


def test_message_read_supports_after_message_id_and_order(temp_idea_spark_db):
    room_id = make_room()
    message_ids = []
    for i in range(5):
        posted = call(
            idea_spark_message_post,
            {"room_id": room_id, "round_id": "r1", "phase": "review", "agent_id": "agent-a", "content": f"message {i}"},
        )
        message_ids.append(posted["message_id"])

    ascending = call(
        idea_spark_message_read,
        {"room_id": room_id, "after_message_id": message_ids[1], "order": "asc"},
    )

    assert ascending["success"] is True
    assert [msg["message_id"] for msg in ascending["messages"]] == message_ids[2:]
    assert ascending["next_cursor"]["last_message_id"] == message_ids[-1]

    descending = call(
        idea_spark_message_read,
        {"room_id": room_id, "after_message_id": message_ids[1], "order": "desc"},
    )

    assert descending["success"] is True
    assert [msg["message_id"] for msg in descending["messages"]] == list(reversed(message_ids[2:]))
    assert descending["next_cursor"]["last_message_id"] == message_ids[-1]

    invalid = call(idea_spark_message_read, {"room_id": room_id, "order": "sideways"})
    assert invalid["success"] is False


def test_room_status_reports_missing_expected_agents(temp_idea_spark_db):
    room_id = make_room(["agent-a", "agent-b"])
    call(idea_spark_room_join, {"room_id": room_id, "agent_id": "agent-a", "role": "PriorArtBreaker"})
    call(
        idea_spark_message_post,
        {"room_id": room_id, "round_id": "r1", "phase": "start", "agent_id": "agent-a", "content": "hello"},
    )

    status = call(idea_spark_room_status, {"room_id": room_id})

    assert status["success"] is True
    assert status["counts"]["participants"] == 1
    assert status["counts"]["messages"] == 1
    assert status["counts"]["artifacts"] == 0
    assert status["expected_agents"] == ["agent-a", "agent-b"]
    assert status["joined_agents"] == ["agent-a"]
    assert status["missing_expected_agents"] == ["agent-b"]


def test_room_status_reports_latest_gate_terminal_flag_open_need_summary_and_cursors(temp_idea_spark_db):
    room_id = make_room(["agent-a", "agent-b"])
    call(idea_spark_room_join, {"room_id": room_id, "agent_id": "agent-a", "role": "PriorArtBreaker"})
    first_message = call(
        idea_spark_message_post,
        {"room_id": room_id, "round_id": "r1", "phase": "review", "agent_id": "agent-a", "content": "first"},
    )
    latest_message = call(
        idea_spark_message_post,
        {"room_id": room_id, "round_id": "r1", "phase": "review", "agent_id": "agent-b", "content": "second"},
    )
    assert latest_message["message_id"] > first_message["message_id"]

    need = call(
        idea_spark_need_create,
        {
            "room_id": room_id,
            "target_artifact_type": "PriorArtEvidence",
            "query": "find prior art",
            "rationale": "novelty pressure",
            "pressure_score": 0.8,
        },
    )
    assert need["success"] is True

    artifact = call(
        idea_spark_artifact_create,
        {
            "room_id": room_id,
            "artifact_type": "AtomicClaim",
            "producer_agent": "agent-a",
            "title": "claim",
            "content": {"claim": "A improves B"},
        },
    )
    assert artifact["success"] is True

    gate = call(
        idea_spark_gate_record,
        {
            "room_id": room_id,
            "gate_type": "novelty",
            "decision": "needs_more_evidence",
            "input_artifact_ids": [artifact["artifact_id"]],
            "rationale": "Need stronger prior-art evidence.",
            "created_by": "gatekeeper",
            "close_room": True,
        },
    )
    assert gate["success"] is True

    status = call(idea_spark_room_status, {"room_id": room_id})

    assert status["success"] is True
    assert status["expected_agents"] == ["agent-a", "agent-b"]
    assert status["joined_agents"] == ["agent-a"]
    assert status["missing_expected_agents"] == ["agent-b"]
    assert status["latest_gate"]["gate_id"] == gate["gate_id"]
    assert status["latest_gate"]["decision"] == "needs_more_evidence"
    assert status["latest_gate"]["input_artifact_ids"] == [artifact["artifact_id"]]
    assert status["has_terminal_gate"] is True
    assert status["open_need_summary"]["open"] == 1
    assert status["open_need_summary"]["claimed"] == 0
    assert status["open_need_summary"]["resolved"] == 0
    assert status["cursors"]["last_message_id"] == latest_message["message_id"]
    assert status["cursors"]["last_artifact_updated_at"]
    assert status["cursors"]["last_gate_created_at"]
    assert status["cursors"]["last_need_updated_at"]
