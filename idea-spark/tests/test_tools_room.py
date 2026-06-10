import json

from idea_spark.tools import (
    idea_spark_message_post,
    idea_spark_message_read,
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
    assert status["missing_expected_agents"] == ["agent-b"]
