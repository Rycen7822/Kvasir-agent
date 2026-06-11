import json
import sqlite3

from idea_spark.tools import (
    idea_spark_artifact_create,
    idea_spark_artifact_link,
    idea_spark_artifact_read,
    idea_spark_artifact_status_update,
    idea_spark_gate_record,
    idea_spark_need_create,
    idea_spark_need_update,
    idea_spark_room_create,
    idea_spark_room_status,
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


def read_need(db_path, need_id):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("select * from open_needs where need_id = ?", (need_id,)).fetchone()
    assert row is not None
    need = dict(row)
    need["metadata"] = json.loads(need.pop("metadata_json"))
    return need


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


def test_artifact_read_supports_created_updated_delta_limit_and_next_cursor(temp_idea_spark_db):
    room_id = make_room()
    first = create_artifact(room_id, "AtomicClaim", {"claim": "first"})
    second = create_artifact(room_id, "AtomicClaim", {"claim": "second"})
    call(
        idea_spark_artifact_status_update,
        {"room_id": room_id, "artifact_id": first["artifact_id"], "status": "accepted", "updated_by": "agent-a"},
    )

    created_delta = call(
        idea_spark_artifact_read,
        {"room_id": room_id, "created_after": "1970-01-01T00:00:00Z", "limit": 1, "order": "asc"},
    )
    assert created_delta["success"] is True
    assert len(created_delta["artifacts"]) == 1
    assert created_delta["next_cursor"]["last_artifact_updated_at"] == created_delta["artifacts"][0]["updated_at"]

    updated_delta = call(
        idea_spark_artifact_read,
        {"room_id": room_id, "updated_after": "1970-01-01T00:00:00Z", "order": "desc"},
    )
    assert updated_delta["success"] is True
    assert {artifact["artifact_id"] for artifact in updated_delta["artifacts"]} == {first["artifact_id"], second["artifact_id"]}
    assert any(artifact["artifact_id"] == first["artifact_id"] and artifact["status"] == "accepted" for artifact in updated_delta["artifacts"])
    assert updated_delta["next_cursor"]["last_artifact_updated_at"] >= created_delta["next_cursor"]["last_artifact_updated_at"]

    invalid = call(idea_spark_artifact_read, {"room_id": room_id, "order": "sideways"})
    assert invalid["success"] is False


def test_schema_friendly_artifact_aliases_match_handler_contract(temp_idea_spark_db):
    room_id = make_room()
    created = call(
        idea_spark_artifact_create,
        {
            "room_id": room_id,
            "type": "ResearchGoal",
            "title": "schema alias artifact",
            "content": "plain text content from the public schema",
            "created_by": "schema-agent",
            "status": "accepted",
        },
    )

    assert created["success"] is True
    assert created["status"] == "accepted"
    read_by_alias = call(idea_spark_artifact_read, {"room_id": room_id, "artifact_id": created["artifact_id"], "type": "ResearchGoal"})
    artifact = read_by_alias["artifacts"][0]
    assert artifact["producer_agent"] == "schema-agent"
    assert artifact["content"] == {"text": "plain text content from the public schema"}


def test_gate_and_need_schema_aliases_match_handler_contract(temp_idea_spark_db):
    room_id = make_room()
    artifact = create_artifact(room_id)

    gate = call(
        idea_spark_gate_record,
        {
            "room_id": room_id,
            "gate_type": "schema-compat",
            "input_artifact_ids": [artifact["artifact_id"]],
            "decision": "accepted",
            "rationale": "Schema alias decided_by should populate created_by.",
            "decided_by": "schema-gatekeeper",
        },
    )
    assert gate["success"] is True

    need = call(
        idea_spark_need_create,
        {
            "room_id": room_id,
            "target_artifact_type": "PriorArtEvidence",
            "query": "missing evidence",
            "rationale": "pressure score defaults when omitted",
        },
    )
    assert need["success"] is True
    assert need["pressure_score"] == 0.5


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


def test_gate_record_can_close_room_and_status_reports_terminal_gate(temp_idea_spark_db):
    room_id = make_room()
    artifact = create_artifact(room_id)
    need = call(
        idea_spark_need_create,
        {
            "room_id": room_id,
            "target_artifact_type": "PriorArtEvidence",
            "query": "collect stronger evidence",
            "rationale": "gate policy needs it",
        },
    )
    assert need["success"] is True

    gate = call(
        idea_spark_gate_record,
        {
            "room_id": room_id,
            "gate_type": "novelty",
            "input_artifact_ids": [artifact["artifact_id"]],
            "decision": "needs_more_evidence",
            "rationale": "Evidence debt remains.",
            "decided_by": "gatekeeper",
            "close_room": True,
            "metadata": {"round_id": "r4", "phase": "gate", "max_rounds": 4, "unresolved_open_need_ids": [need["need_id"]]},
        },
    )

    assert gate["success"] is True
    assert gate["room_status"] == "gated"

    status = call(idea_spark_room_status, {"room_id": room_id})
    assert status["status"] == "gated"
    assert status["has_terminal_gate"] is True
    assert status["latest_gate"]["gate_id"] == gate["gate_id"]

    gates = call(idea_spark_artifact_read, {"room_id": room_id, "artifact_type": "GateDecision"})
    gate_content = gates["artifacts"][0]["content"]
    assert gate_content["metadata"]["round_id"] == "r4"
    assert gate_content["metadata"]["phase"] == "gate"
    assert gate_content["metadata"]["max_rounds"] == 4
    assert gate_content["metadata"]["unresolved_open_need_ids"] == [need["need_id"]]


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


def test_need_update_claim_resolve_reopen_and_reject_invalid_state(temp_idea_spark_db):
    room_id = make_room()
    resolution = create_artifact(room_id, "PriorArtEvidence", {"paper": "relevant prior work"})
    other_room_id = make_room()
    other_artifact = create_artifact(other_room_id, "PriorArtEvidence", {"paper": "wrong room"})
    need = call(
        idea_spark_need_create,
        {
            "room_id": room_id,
            "target_artifact_type": "PriorArtEvidence",
            "query": "find nearest prior work",
            "rationale": "novelty pressure",
            "metadata": {"seed": True},
        },
    )
    assert need["success"] is True

    claim = call(
        idea_spark_need_update,
        {
            "room_id": room_id,
            "need_id": need["need_id"],
            "status": "claimed",
            "claimed_by_agent": "agent-b",
            "updated_by": "agent-b",
        },
    )
    assert claim["success"] is True
    claimed = read_need(temp_idea_spark_db, need["need_id"])
    assert claimed["status"] == "claimed"
    assert claimed["claimed_by_agent"] == "agent-b"

    wrong_room_resolution = call(
        idea_spark_need_update,
        {
            "room_id": room_id,
            "need_id": need["need_id"],
            "status": "resolved",
            "resolution_artifact_ids": [other_artifact["artifact_id"]],
            "updated_by": "agent-b",
        },
    )
    assert wrong_room_resolution["success"] is False

    resolved = call(
        idea_spark_need_update,
        {
            "room_id": room_id,
            "need_id": need["need_id"],
            "status": "resolved",
            "resolution_artifact_ids": [resolution["artifact_id"]],
            "resolution_rationale": "Evidence artifact answers the need.",
            "updated_by": "agent-b",
            "metadata": {"note": "resolved in review"},
        },
    )
    assert resolved["success"] is True
    resolved_row = read_need(temp_idea_spark_db, need["need_id"])
    assert resolved_row["status"] == "resolved"
    assert resolved_row["metadata"]["seed"] is True
    assert resolved_row["metadata"]["resolution_artifact_ids"] == [resolution["artifact_id"]]
    assert resolved_row["metadata"]["resolution_rationale"] == "Evidence artifact answers the need."
    assert resolved_row["metadata"]["updated_by"] == "agent-b"
    assert resolved_row["metadata"]["note"] == "resolved in review"

    reopened = call(
        idea_spark_need_update,
        {"room_id": room_id, "need_id": need["need_id"], "status": "open", "updated_by": "agent-c"},
    )
    assert reopened["success"] is True
    reopened_row = read_need(temp_idea_spark_db, need["need_id"])
    assert reopened_row["status"] == "open"
    assert reopened_row["updated_at"] >= resolved_row["updated_at"]

    invalid = call(
        idea_spark_need_update,
        {"room_id": room_id, "need_id": need["need_id"], "status": "invented", "updated_by": "agent-c"},
    )
    assert invalid["success"] is False


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
