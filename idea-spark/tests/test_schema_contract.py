EXPECTED_TOOL_NAMES = [
    "idea_spark_room_create",
    "idea_spark_room_join",
    "idea_spark_room_status",
    "idea_spark_message_post",
    "idea_spark_message_read",
    "idea_spark_round_wait",
    "idea_spark_artifact_create",
    "idea_spark_artifact_read",
    "idea_spark_artifact_link",
    "idea_spark_artifact_status_update",
    "idea_spark_gate_record",
    "idea_spark_need_create",
    "idea_spark_room_export",
]


def test_canonical_names_and_no_aliases():
    from idea_spark import schemas

    assert schemas.PLUGIN_NAME == "idea-spark"
    assert schemas.TOOLSET == "idea_spark"
    assert schemas.PROTOCOL == "idea_spark_ml_review_v1"
    assert schemas.TOOL_NAMES == EXPECTED_TOOL_NAMES
    assert len(schemas.TOOL_NAMES) == len(set(schemas.TOOL_NAMES))
    assert all(name.startswith("idea_spark_") for name in schemas.TOOL_NAMES)
    assert not any("alias" in name or "legacy" in name for name in schemas.TOOL_NAMES)

    assert "needs_more_evidence" in schemas.GATE_DECISIONS
    assert "needs_more_evidence" not in schemas.ARTIFACT_STATUSES
    assert "decomposes" in schemas.RELATIONS
    assert "GateDecision" in schemas.ARTIFACT_TYPES
