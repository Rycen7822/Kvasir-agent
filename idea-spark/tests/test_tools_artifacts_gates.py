import json

from idea_spark.tools import (
    idea_spark_artifact_create,
    idea_spark_artifact_link,
    idea_spark_artifact_read,
    idea_spark_artifact_status_update,
    idea_spark_gate_record,
    idea_spark_need_create,
    idea_spark_room_create,
)


def call(handler, payload):
    return json.loads(handler(payload))


def make_room():
    room = call(
        idea_spark_room_create,
        {"title": "artifact room", "topic": "ledger", "created_by": "parent"},
    )
    assert room["success"] is True
    return room["room_id"]


def create_artifact(room_id, artifact_type="AtomicClaim", content=None, **extra):
    payload = {
        "room_id": room_id,
        "artifact_type": artifact_type,
        "producer_agent": "agent-a",
        "title": "artifact",
        "content": content or {"claim": "A improves B under C"},
    }
    payload.update(extra)
    result = call(idea_spark_artifact_create, payload)
    assert result["success"] is True
    return result


def test_artifact_create_hashes_and_links_parents(temp_idea_spark_db):
    room_id = make_room()
    idea = create_artifact(room_id, "IdeaCard", {"idea": "base idea"})
    claim = create_artifact(
        room_id,
        "AtomicClaim",
        {"claim": "claim 1"},
        parent_links=[{"source_artifact_id": idea["artifact_id"], "relation": "decomposes"}],
    )

    assert claim["content_hash"].startswith("sha256:")
    read = call(
        idea_spark_artifact_read,
        {"room_id": room_id, "artifact_ids": [claim["artifact_id"]], "relation_depth": 1},
    )

    assert read["success"] is True
    artifact = read["artifacts"][0]
    assert artifact["artifact_id"] == claim["artifact_id"]
    assert artifact["status"] == "proposed"
    assert artifact["inbound_links"] == [
        {"source_artifact_id": idea["artifact_id"], "relation": "decomposes", "target_artifact_id": claim["artifact_id"]}
    ]


def test_artifact_create_deduplicates_same_type_and_content_in_room(temp_idea_spark_db):
    room_id = make_room()
    first = create_artifact(room_id, content={"claim": "same"})
    second = create_artifact(room_id, content={"claim": "same"})

    assert second["artifact_id"] == first["artifact_id"]
    assert second["deduplicated"] is True

    read = call(idea_spark_artifact_read, {"room_id": room_id, "artifact_type": "AtomicClaim"})
    assert len(read["artifacts"]) == 1


def test_invalid_artifact_type_status_relation_and_gate_decision_return_error_json(temp_idea_spark_db):
    room_id = make_room()
    artifact = create_artifact(room_id)

    bad_type = call(
        idea_spark_artifact_create,
        {"room_id": room_id, "artifact_type": "Unknown", "producer_agent": "agent-a", "content": {}},
    )
    assert bad_type["success"] is False

    bad_status = call(
        idea_spark_artifact_status_update,
        {"room_id": room_id, "artifact_id": artifact["artifact_id"], "status": "needs_more_evidence"},
    )
    assert bad_status["success"] is False

    bad_relation = call(
        idea_spark_artifact_link,
        {
            "room_id": room_id,
            "source_artifact_id": artifact["artifact_id"],
            "relation": "invented_relation",
            "target_artifact_id": artifact["artifact_id"],
        },
    )
    assert bad_relation["success"] is False

    bad_gate = call(
        idea_spark_gate_record,
        {"room_id": room_id, "gate_type": "novelty", "decision": "maybe", "rationale": "invalid"},
    )
    assert bad_gate["success"] is False


def test_gate_record_updates_artifact_status_and_retains_gate_rationale(temp_idea_spark_db):
    room_id = make_room()
    artifact = create_artifact(room_id)

    gate = call(
        idea_spark_gate_record,
        {
            "room_id": room_id,
            "gate_type": "novelty",
            "input_artifact_ids": [artifact["artifact_id"]],
            "decision": "accepted",
            "score": {"novelty": 0.8},
            "rationale": "Claim is sufficiently novel.",
            "created_by": "gatekeeper",
            "status_updates": [{"artifact_id": artifact["artifact_id"], "status": "accepted"}],
        },
    )

    assert gate["success"] is True
    assert gate["decision"] == "accepted"
    assert gate["gate_artifact_id"].startswith("artifact_")

    read = call(idea_spark_artifact_read, {"room_id": room_id, "artifact_ids": [artifact["artifact_id"]]})
    assert read["artifacts"][0]["status"] == "accepted"

    gates = call(idea_spark_artifact_read, {"room_id": room_id, "artifact_type": "GateDecision"})
    assert gates["artifacts"][0]["content"]["rationale"] == "Claim is sufficiently novel."


def test_needs_more_evidence_is_gate_decision_not_artifact_status(temp_idea_spark_db):
    room_id = make_room()
    artifact = create_artifact(room_id)

    rejected_status = call(
        idea_spark_artifact_status_update,
        {"room_id": room_id, "artifact_id": artifact["artifact_id"], "status": "needs_more_evidence"},
    )
    assert rejected_status["success"] is False

    gate = call(
        idea_spark_gate_record,
        {
            "room_id": room_id,
            "gate_type": "feasibility",
            "input_artifact_ids": [artifact["artifact_id"]],
            "decision": "needs_more_evidence",
            "rationale": "Need a benchmark requirement before accepting.",
        },
    )
    assert gate["success"] is True


def test_need_create_rejects_out_of_range_pressure_score(temp_idea_spark_db):
    room_id = make_room()

    bad = call(
        idea_spark_need_create,
        {
            "room_id": room_id,
            "target_artifact_type": "PriorArtEvidence",
            "query": "find nearest prior work",
            "rationale": "novelty pressure",
            "pressure_score": 1.5,
        },
    )
    assert bad["success"] is False

    good = call(
        idea_spark_need_create,
        {
            "room_id": room_id,
            "target_artifact_type": "PriorArtEvidence",
            "query": "find nearest prior work",
            "rationale": "novelty pressure",
            "pressure_score": 0.9,
            "created_by": "agent-a",
        },
    )
    assert good["success"] is True
    assert good["status"] == "open"


def test_original_idea_is_superseded_by_link_not_overwritten(temp_idea_spark_db):
    room_id = make_room()
    old = create_artifact(room_id, "IdeaCard", {"idea": "old"})
    new = create_artifact(room_id, "IdeaCard", {"idea": "new"})

    linked = call(
        idea_spark_artifact_link,
        {
            "room_id": room_id,
            "source_artifact_id": new["artifact_id"],
            "relation": "supersedes",
            "target_artifact_id": old["artifact_id"],
            "created_by": "agent-a",
        },
    )
    assert linked["success"] is True

    read_old = call(idea_spark_artifact_read, {"room_id": room_id, "artifact_ids": [old["artifact_id"]]})
    assert read_old["artifacts"][0]["status"] == "proposed"

    read_new = call(
        idea_spark_artifact_read,
        {"room_id": room_id, "artifact_ids": [new["artifact_id"]], "relation_depth": 1},
    )
    assert read_new["artifacts"][0]["outbound_links"] == [
        {"source_artifact_id": new["artifact_id"], "relation": "supersedes", "target_artifact_id": old["artifact_id"]}
    ]
