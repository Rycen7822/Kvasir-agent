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
    "idea_spark_need_update",
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


def test_round_wait_schema_exposes_per_call_expected_agents():
    from idea_spark.tools import schema_for

    schema = schema_for("idea_spark_round_wait")
    props = schema["parameters"]["properties"]

    assert "expected_agents" in props
    assert props["expected_agents"]["type"] == "array"
    assert props["expected_agents"]["items"] == {"type": "string"}
    assert "expected_agents" not in schema["parameters"]["required"]
    assert "phase" not in schema["parameters"]["required"]
    assert props["phases"]["type"] == "array"
    assert props["phases"]["items"] == {"type": "string"}


def test_room_create_schema_exposes_dashboard_base_url():
    from idea_spark.tools import schema_for

    schema = schema_for("idea_spark_room_create")
    props = schema["parameters"]["properties"]

    assert props["dashboard_base_url"]["type"] == "string"
    assert props["check_dashboard"] == {"type": "boolean"}
    assert "room_url" in schema["description"]
    assert "dashboard_base_url" not in schema["parameters"]["required"]
    assert "check_dashboard" not in schema["parameters"]["required"]


def test_read_schemas_expose_delta_cursor_fields():
    from idea_spark.tools import schema_for

    message_props = schema_for("idea_spark_message_read")["parameters"]["properties"]
    artifact_props = schema_for("idea_spark_artifact_read")["parameters"]["properties"]

    assert message_props["after_message_id"]["type"] == "integer"
    assert message_props["order"]["enum"] == ["asc", "desc"]
    assert artifact_props["created_after"]["type"] == "string"
    assert artifact_props["updated_after"]["type"] == "string"
    assert artifact_props["order"]["enum"] == ["asc", "desc"]


def test_gate_record_schema_exposes_close_room_flag():
    from idea_spark.tools import schema_for

    schema = schema_for("idea_spark_gate_record")
    props = schema["parameters"]["properties"]

    assert props["close_room"] == {"type": "boolean"}
    assert "close_room" not in schema["parameters"]["required"]


def test_need_update_schema_exposes_lifecycle_fields():
    from idea_spark.tools import schema_for

    schema = schema_for("idea_spark_need_update")
    props = schema["parameters"]["properties"]

    assert props["need_id"]["type"] == "string"
    assert props["resolution_artifact_ids"] == {"type": "array", "items": {"type": "string"}}
    assert props["resolution_rationale"] == {"type": "string"}
    assert schema["parameters"]["required"] == ["room_id", "need_id", "status", "updated_by"]
