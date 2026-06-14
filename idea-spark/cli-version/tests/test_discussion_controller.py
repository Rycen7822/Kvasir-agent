import json

from idea_spark.tools import (
    idea_spark_artifact_create,
    idea_spark_gate_record,
    idea_spark_message_post,
    idea_spark_room_create,
    idea_spark_room_export,
    idea_spark_room_join,
    idea_spark_room_status,
)


def call(handler, payload):
    return json.loads(handler(payload))


def seed_discussion_room():
    room = call(
        idea_spark_room_create,
        {
            "title": "controller contract room",
            "topic": "Evaluate whether the idea should continue.",
            "created_by": "parent",
            "metadata": {"expected_agents": ["prior", "feasibility", "author", "gatekeeper"]},
        },
    )
    assert room["success"] is True
    room_id = room["room_id"]
    seeds = [
        ("ResearchGoal", "goal", {"goal": "test controller stop semantics"}),
        ("IdeaCard", "idea", {"idea": "shared ledger debate until a gate exists"}),
        ("EvaluationRubric", "rubric", {"criteria": ["novelty", "feasibility", "risk"]}),
    ]
    artifacts = []
    for artifact_type, title, content in seeds:
        artifact = call(
            idea_spark_artifact_create,
            {
                "room_id": room_id,
                "artifact_type": artifact_type,
                "producer_agent": "parent",
                "title": title,
                "content": content,
                "metadata": {"round_id": "r0", "phase": "Seed / Framing"},
            },
        )
        assert artifact["success"] is True
        artifacts.append(artifact)
    return room_id, artifacts


def fake_role_write(room_id, agent_id, role, round_id, phase, artifact_specs):
    joined = call(idea_spark_room_join, {"room_id": room_id, "agent_id": agent_id, "role": role})
    assert joined["success"] is True
    artifact_ids = []
    for artifact_type, title, content in artifact_specs:
        artifact = call(
            idea_spark_artifact_create,
            {
                "room_id": room_id,
                "artifact_type": artifact_type,
                "producer_agent": agent_id,
                "title": title,
                "content": content,
                "metadata": {"round_id": round_id, "phase": phase},
            },
        )
        assert artifact["success"] is True
        artifact_ids.append(artifact["artifact_id"])
    posted = call(
        idea_spark_message_post,
        {
            "room_id": room_id,
            "round_id": round_id,
            "phase": phase,
            "agent_id": agent_id,
            "role": role,
            "content": f"{role} completed {phase}.",
            "artifact_ids": artifact_ids,
        },
    )
    assert posted["success"] is True
    return artifact_ids


def controller_should_stop(room_id):
    status = call(idea_spark_room_status, {"room_id": room_id})
    assert status["success"] is True
    return status["has_terminal_gate"], status


def test_controller_does_not_stop_without_gate_even_after_review_and_rebuttal(temp_idea_spark_db):
    room_id, _ = seed_discussion_room()
    fake_role_write(
        room_id,
        "prior",
        "PriorArtBreaker",
        "r1",
        "Novelty Attack",
        [("NoveltyObjection", "prior art risk", {"risk": "closest prior work overlaps"})],
    )
    fake_role_write(
        room_id,
        "author",
        "AuthorAdvocate",
        "r2",
        "Author Rebuttal / Improvement Draft",
        [("Rebuttal", "novelty response", {"response": "distinguish by control signal"})],
    )

    should_stop, status = controller_should_stop(room_id)

    assert should_stop is False
    assert status["latest_gate"] is None
    assert status["counts"]["messages"] == 2
    assert status["counts"]["artifacts"] == 5


def test_controller_does_not_stop_when_gatekeeper_posts_message_without_gate_record(temp_idea_spark_db):
    room_id, _ = seed_discussion_room()
    fake_role_write(room_id, "gatekeeper", "Gatekeeper", "r3", "Gate", [])

    should_stop, status = controller_should_stop(room_id)

    assert should_stop is False
    assert status["latest_gate"] is None
    assert status["counts"]["messages"] == 1


def test_controller_does_not_stop_when_gate_record_does_not_close_room(temp_idea_spark_db):
    room_id, seeds = seed_discussion_room()
    gate = call(
        idea_spark_gate_record,
        {
            "room_id": room_id,
            "gate_type": "intermediate",
            "decision": "needs_more_evidence",
            "input_artifact_ids": [seeds[0]["artifact_id"]],
            "rationale": "Intermediate gate should remain visible but non-terminal.",
            "decided_by": "gatekeeper",
            "metadata": {"round_id": "r2", "phase": "Re-review / Cross-examination"},
        },
    )
    assert gate["success"] is True

    should_stop, status = controller_should_stop(room_id)

    assert should_stop is False
    assert status["status"] == "open"
    assert status["latest_gate"]["decision"] == "needs_more_evidence"


def test_controller_stops_after_gate_record_and_exports_report(temp_idea_spark_db):
    room_id, seeds = seed_discussion_room()
    fake_role_write(
        room_id,
        "feasibility",
        "FeasibilityBreaker",
        "r1",
        "Weakness / Feasibility Attack",
        [("FeasibilityObjection", "compute risk", {"risk": "training budget unclear"})],
    )
    gate = call(
        idea_spark_gate_record,
        {
            "room_id": room_id,
            "gate_type": "overall",
            "decision": "accepted",
            "input_artifact_ids": [seeds[1]["artifact_id"]],
            "rationale": "Gate-backed acceptance for controller semantics.",
            "decided_by": "gatekeeper",
            "metadata": {"round_id": "r3", "phase": "Gate", "max_rounds": 4},
            "close_room": True,
        },
    )
    assert gate["success"] is True

    should_stop, status = controller_should_stop(room_id)
    exported = call(idea_spark_room_export, {"room_id": room_id, "format": "markdown"})

    assert should_stop is True
    assert status["status"] == "gated"
    assert status["latest_gate"]["decision"] == "accepted"
    assert exported["success"] is True
    assert "Gate-backed acceptance for controller semantics." in exported["markdown"]


def test_controller_records_needs_more_evidence_gate_when_max_rounds_exhausted(temp_idea_spark_db):
    room_id, seeds = seed_discussion_room()
    fake_role_write(
        room_id,
        "prior",
        "PriorArtBreaker",
        "r4",
        "Re-review / Cross-examination",
        [("OpenNeed", "missing prior art", {"need": "independent prior-art sweep still missing"})],
    )
    gate = call(
        idea_spark_gate_record,
        {
            "room_id": room_id,
            "gate_type": "max_rounds",
            "decision": "needs_more_evidence",
            "input_artifact_ids": [seeds[0]["artifact_id"]],
            "rationale": "max_rounds=4 exhausted without enough evidence.",
            "decided_by": "gatekeeper",
            "metadata": {"round_id": "r4", "phase": "Gate", "max_rounds": 4},
            "close_room": True,
        },
    )
    assert gate["success"] is True

    should_stop, status = controller_should_stop(room_id)

    assert should_stop is True
    assert status["latest_gate"]["decision"] == "needs_more_evidence"
    assert status["status"] == "gated"
