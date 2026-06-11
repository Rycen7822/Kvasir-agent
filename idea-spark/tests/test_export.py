import json

from idea_spark.tools import (
    idea_spark_artifact_create,
    idea_spark_artifact_link,
    idea_spark_artifact_status_update,
    idea_spark_gate_record,
    idea_spark_message_post,
    idea_spark_need_create,
    idea_spark_need_update,
    idea_spark_room_create,
    idea_spark_room_export,
)


REQUIRED_HEADINGS = [
    "# Idea-Spark Room Report",
    "## Executive verdict",
    "## Idea card",
    "## Claim-level novelty table",
    "## Accepted / rejected / gate / claim summary",
    "## Feasibility and experiment plan",
    "## Reviewer risks",
    "## Artifact lifecycle",
    "## Schema transitions",
    "## Open needs",
    "## Full transcript appendix",
]


def call(handler, payload):
    return json.loads(handler(payload))


def make_room(title="export room"):
    room = call(
        idea_spark_room_create,
        {"title": title, "topic": "baseline", "created_by": "parent"},
    )
    assert room["success"] is True
    return room["room_id"]


def create_artifact(room_id, artifact_type, content, title="artifact"):
    artifact = call(
        idea_spark_artifact_create,
        {
            "room_id": room_id,
            "artifact_type": artifact_type,
            "producer_agent": "agent-a",
            "title": title,
            "content": content,
        },
    )
    assert artifact["success"] is True
    return artifact


def export_markdown(room_id):
    exported = call(idea_spark_room_export, {"room_id": room_id, "format": "markdown"})
    assert exported["success"] is True
    return exported


def test_export_contains_required_markdown_sections_before_artifacts_exist(temp_idea_spark_db):
    room_id = make_room("empty export")

    exported = export_markdown(room_id)

    assert exported["format"] == "markdown"
    assert exported["artifact_count"] == 0
    assert exported["gate_count"] == 0
    assert exported["open_need_count"] == 0
    for heading in REQUIRED_HEADINGS:
        assert heading in exported["markdown"]


def test_export_orders_all_required_sections(temp_idea_spark_db):
    room_id = make_room()

    markdown = export_markdown(room_id)["markdown"]

    positions = [markdown.index(heading) for heading in REQUIRED_HEADINGS]
    assert positions == sorted(positions)


def test_export_uses_gate_backed_statuses_for_verdict_inputs(temp_idea_spark_db):
    room_id = make_room()
    claim = create_artifact(room_id, "AtomicClaim", {"claim": "new optimizer improves stability"}, "stability claim")
    gate = call(
        idea_spark_gate_record,
        {
            "room_id": room_id,
            "gate_type": "novelty",
            "input_artifact_ids": [claim["artifact_id"]],
            "decision": "accepted",
            "score": {"novelty": 0.8},
            "rationale": "Gate-backed novelty rationale.",
            "created_by": "gatekeeper",
            "status_updates": [{"artifact_id": claim["artifact_id"], "status": "accepted"}],
        },
    )
    assert gate["success"] is True

    exported = export_markdown(room_id)

    assert exported["gate_count"] == 1
    assert "novelty" in exported["markdown"]
    assert "accepted" in exported["markdown"]
    assert "Gate-backed novelty rationale." in exported["markdown"]
    assert "stability claim" in exported["markdown"]


def test_export_includes_rejected_superseded_and_retracted_artifacts(temp_idea_spark_db):
    room_id = make_room()
    statuses = ["rejected", "superseded", "retracted"]
    for status in statuses:
        artifact = create_artifact(room_id, "AtomicClaim", {"claim": status}, f"{status} claim")
        updated = call(
            idea_spark_artifact_status_update,
            {"room_id": room_id, "artifact_id": artifact["artifact_id"], "status": status},
        )
        assert updated["success"] is True

    markdown = export_markdown(room_id)["markdown"]

    for status in statuses:
        assert f"{status} claim" in markdown
        assert status in markdown


def test_export_contains_open_needs_and_transcript_appendix(temp_idea_spark_db):
    room_id = make_room()
    need = call(
        idea_spark_need_create,
        {
            "room_id": room_id,
            "target_artifact_type": "PriorArtEvidence",
            "query": "nearest prior work for optimizer stability",
            "rationale": "Reviewer risk requires evidence.",
            "pressure_score": 0.7,
            "created_by": "agent-a",
        },
    )
    assert need["success"] is True
    posted = call(
        idea_spark_message_post,
        {
            "room_id": room_id,
            "round_id": "r1",
            "phase": "evidence",
            "agent_id": "agent-a",
            "content": "Need stronger prior-art evidence.",
        },
    )
    assert posted["success"] is True

    exported = export_markdown(room_id)

    assert exported["open_need_count"] == 1
    assert "nearest prior work for optimizer stability" in exported["markdown"]
    assert "Reviewer risk requires evidence." in exported["markdown"]
    assert "Need stronger prior-art evidence." in exported["markdown"]


def test_export_includes_discussion_trajectory_unresolved_needs_and_latest_gate(temp_idea_spark_db):
    room_id = make_room("trajectory export")
    idea = create_artifact(room_id, "IdeaCard", {"idea": "adaptive controller"}, "Adaptive controller idea")
    objection = create_artifact(room_id, "NoveltyObjection", {"attack": "closest baseline is similar"}, "Novelty attack")
    rebuttal = create_artifact(room_id, "Rebuttal", {"answer": "uses a different feedback signal"}, "Author rebuttal")
    revision = create_artifact(room_id, "RevisionPlan", {"change": "narrow claim and add ablation"}, "Improvement plan")
    experiment = create_artifact(room_id, "ExperimentPlan", {"plan": "run fixed-candidate ablation"}, "Ablation plan")
    scorecard = create_artifact(room_id, "ScoreCard", {"score": 0.62}, "Gate scorecard")
    for source, target, relation in [
        (objection, idea, "critiques"),
        (rebuttal, objection, "rebuts"),
        (revision, rebuttal, "supports"),
        (experiment, revision, "requires"),
        (scorecard, experiment, "supports"),
    ]:
        linked = call(
            idea_spark_artifact_link,
            {
                "room_id": room_id,
                "source_artifact_id": source["artifact_id"],
                "target_artifact_id": target["artifact_id"],
                "relation": relation,
            },
        )
        assert linked["success"] is True
    unresolved = call(
        idea_spark_need_create,
        {
            "room_id": room_id,
            "target_artifact_type": "PriorArtEvidence",
            "query": "unresolved official baseline evidence",
            "rationale": "Need remains open for final review.",
            "pressure_score": 0.8,
        },
    )
    assert unresolved["success"] is True
    resolved = call(
        idea_spark_need_create,
        {
            "room_id": room_id,
            "target_artifact_type": "BenchmarkRequirement",
            "query": "resolved benchmark protocol",
            "rationale": "Benchmark plan is now documented.",
            "pressure_score": 0.3,
        },
    )
    assert resolved["success"] is True
    updated = call(
        idea_spark_need_update,
        {"room_id": room_id, "need_id": resolved["need_id"], "status": "resolved", "updated_by": "planner"},
    )
    assert updated["success"] is True
    gate = call(
        idea_spark_gate_record,
        {
            "room_id": room_id,
            "gate_type": "overall",
            "decision": "needs_more_evidence",
            "input_artifact_ids": [scorecard["artifact_id"]],
            "rationale": "Latest gate requires stronger baseline evidence.",
            "decided_by": "gatekeeper",
            "metadata": {"round_id": "r4", "phase": "Gate", "max_rounds": 4},
        },
    )
    assert gate["success"] is True

    markdown = export_markdown(room_id)["markdown"]

    assert "Discussion trajectory" in markdown
    assert "Novelty attack" in markdown
    assert "Improvement plan" in markdown
    assert "Latest gate" in markdown
    assert "unresolved official baseline evidence" in markdown
    assert "status=open" in markdown
    assert "resolved benchmark protocol" in markdown
    assert "status=resolved" in markdown
    assert "Latest gate requires stronger baseline evidence." in markdown
