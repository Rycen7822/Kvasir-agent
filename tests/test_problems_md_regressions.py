from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from codex_scientist.mcp.tool_registry import call_tool, list_tool_specs, tools_list_payload


REPO_ROOT = Path(__file__).resolve().parents[1]


def _ok(payload: dict) -> dict:
    assert payload.get("ok") is True, payload
    return payload


def _new_quest(tmp_path: Path, goal: str = "problems regression quest") -> str:
    payload = _ok(call_tool("cs_new_quest", {"project": str(tmp_path), "goal": goal, "title": goal}))
    return str(payload["quest"]["quest_id"])


def _open_baseline(tmp_path: Path, quest_id: str) -> None:
    baseline = _ok(
        call_tool(
            "cs_create_local_baseline",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "baseline_id": "baseline-regression",
                "title": "Regression baseline",
                "content": "Baseline stub for regression tests.",
                "metric_contract": {"primary_metric": "exact_match", "direction": "maximize"},
            },
        )
    )
    _ok(call_tool("cs_confirm_baseline", {"project": str(tmp_path), **baseline["confirm_args"]}))


def test_usage_doc_matches_upgrade6_profile_contract() -> None:
    usage = (REPO_ROOT / "docs" / "USAGE.md").read_text(encoding="utf-8")

    stale_phrases = [
        "14-tool core profile",
        "47-tool goal profile",
        "filtered by active stage subset",
        "progress watchdog state",
        "allowed_tools_for_stage",
        "Use `cs_skill_search`",
        "Use `cs_skill_load`",
    ]
    for phrase in stale_phrases:
        assert phrase not in usage

    assert "core profile exposes 11" in usage
    assert "goal profile is deprecated" in usage
    assert "stage is a label" in usage
    assert "manual watchdog diagnostic" in usage
    assert "MCP registry-only" in usage


def test_project_root_alias_is_honored_and_does_not_write_to_cwd(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "target-project"
    cwd = tmp_path / "cwd-project"
    target.mkdir()
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    status = _ok(call_tool("cs_status", {"project_root": str(target)}))
    assert status["project"] == str(target.resolve())
    assert status["state_root"] == str((target / "CodexScientist").resolve())

    checkpoint = _ok(
        call_tool(
            "cs_checkpoint",
            {
                "project_root": str(target),
                "phase": "project-root-alias-regression",
                "completed": ["project_root alias honored"],
            },
        )
    )
    assert str(target.resolve()) in str(checkpoint)
    assert (target / "CodexScientist").exists()
    assert not (cwd / "CodexScientist").exists()


def test_tool_schema_returns_minimal_schema_for_every_registered_tool() -> None:
    missing: list[str] = []
    for spec in list_tool_specs("admin"):
        payload = call_tool("cs_tool_schema", {"name": spec.name})
        if payload.get("ok") is not True:
            missing.append(f"{spec.name}:{payload.get('error_type')}:{payload.get('error')}")
            continue
        schema = payload.get("schema")
        assert isinstance(schema, dict), (spec.name, payload)
        assert schema.get("name") == spec.name
        assert "input_schema" in schema
        required = (schema.get("input_schema") or {}).get("required", [])
        for key in spec.required_context_keys:
            assert key in required, (spec.name, key, payload)
    assert missing == []


def _jsonrpc_tool_call(name: str, arguments: dict) -> dict:
    message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
    result = subprocess.run(
        [sys.executable, "scripts/cs_mcp.py"],
        cwd=str(REPO_ROOT),
        input=json.dumps(message) + "\n",
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    response = json.loads(result.stdout)
    return response["result"]["structuredContent"]


def test_jsonrpc_tools_call_enforces_public_mcp_profile_boundary(tmp_path: Path) -> None:
    quest_id = _new_quest(tmp_path)

    public_payload = _jsonrpc_tool_call("cs_status", {"project": str(tmp_path)})
    assert public_payload["ok"] is True, public_payload

    for hidden_name, args in [
        ("cs_cost_status", {"project": str(tmp_path)}),
        ("cs_select_next_idea", {"project": str(tmp_path), "quest_id": quest_id}),
        ("cs_goal_watchdog", {"project": str(tmp_path), "quest_id": quest_id}),
    ]:
        payload = _jsonrpc_tool_call(hidden_name, args)
        assert payload["ok"] is False, (hidden_name, payload)
        assert payload["error_type"] == "tool_not_registered_for_mcp", (hidden_name, payload)
        assert payload["recoverable"] is True
        assert "tools/list" in json.dumps(payload)

        schema_payload = _jsonrpc_tool_call("cs_tool_schema", {"name": hidden_name})
        assert schema_payload["ok"] is False, (hidden_name, schema_payload)
        assert schema_payload["error_type"] == "tool_not_registered_for_mcp", (hidden_name, schema_payload)
        assert "schema" not in schema_payload


def test_resume_brief_uses_mcp_first_quest_goal_without_missing_goal_blocker(tmp_path: Path) -> None:
    goal = "Small audit simulation goal for resume recovery"
    quest_id = _new_quest(tmp_path, goal=goal)
    _ok(
        call_tool(
            "cs_checkpoint",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "phase": "resume-regression",
                "completed": ["quest-created"],
                "next_action": "continue toy workflow",
            },
        )
    )

    brief = _ok(call_tool("cs_resume_brief", {"project": str(tmp_path), "quest_id": quest_id}))
    assert brief["goal"]["title"] == goal
    assert brief.get("blocker") is None
    assert "blocked_missing_goal" not in brief.get("warnings", [])


def test_artifact_index_can_scope_to_quest_artifacts_seen_by_compact_state(tmp_path: Path) -> None:
    quest_id = _new_quest(tmp_path)
    _ok(
        call_tool(
            "cs_artifact_record",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "kind": "report",
                "summary": "quest artifact index regression",
                "payload": {"kind": "report", "summary": "quest artifact index regression", "status": "completed"},
            },
        )
    )

    state = _ok(call_tool("cs_get_quest_state", {"project": str(tmp_path), "quest_id": quest_id}))
    index = _ok(call_tool("cs_artifact_index", {"project": str(tmp_path), "quest_id": quest_id, "max_items": 20}))
    assert index["scope"] == "quest"
    assert index["quest_id"] == quest_id
    assert index["count"] >= 1
    assert index["quest_artifact_count"] == state["snapshot"]["counts"]["artifacts"]
    assert any("reports" in item["relative_path"] for item in index["artifacts"])


def test_public_tool_metadata_and_schemas_are_codex_discoverable() -> None:
    for profile in ["core", "evidence", "formal_run", "literature", "paper_write"]:
        payload = tools_list_payload({"profile": profile})
        assert payload["ok"] is True, payload
        for tool in payload["tools"]:
            assert "Hermes" not in tool.get("description", ""), (profile, tool)

    bash_schema = _ok(call_tool("cs_tool_schema", {"name": "cs_bash_exec"}))["schema"]["input_schema"]
    assert "allOf" in bash_schema or "oneOf" in bash_schema or "if" in bash_schema
    encoded_bash_schema = json.dumps(bash_schema)
    for key in ["command_class", "provenance_reason", "experiment_or_artifact_id", "cwd_policy"]:
        assert key in encoded_bash_schema

    resume_props = _ok(call_tool("cs_tool_schema", {"name": "cs_resume_brief"}))["schema"]["input_schema"]["properties"]
    assert {"quest_id", "max_chars", "include_recent_events", "include_risks"} <= set(resume_props)

    delta_props = _ok(call_tool("cs_tool_schema", {"name": "cs_pack_delta"}))["schema"]["input_schema"]["properties"]
    assert {"since_event_seq", "since_checkpoint_id", "max_chars"} <= set(delta_props)

    checkpoint_props = _ok(call_tool("cs_tool_schema", {"name": "cs_checkpoint"}))["schema"]["input_schema"]["properties"]
    assert {
        "phase",
        "completed",
        "decisions",
        "validation",
        "next_action",
        "artifact_refs",
        "risk_flags",
        "idempotency_key",
    } <= set(checkpoint_props)

    context_props = _ok(call_tool("cs_tool_schema", {"name": "cs_context_pack"}))["schema"]["input_schema"]["properties"]
    assert {"quest_id", "max_chars"} <= set(context_props)

    analysis_schema = _ok(call_tool("cs_tool_schema", {"name": "cs_create_analysis_campaign"}))["schema"]["input_schema"]
    analysis_props = analysis_schema["properties"]
    assert {"selected_outline_ref", "research_questions", "experimental_designs", "todo_items"} <= set(analysis_props)
    assert "writing-facing" in json.dumps(analysis_schema).lower()

    artifact_schema = _ok(call_tool("cs_tool_schema", {"name": "cs_artifact_record"}))["schema"]["input_schema"]
    kind_schema = artifact_schema["properties"]["kind"]
    assert {"report", "run", "decision", "baseline"} <= set(kind_schema.get("enum", []))


def test_analysis_campaign_writing_fields_return_actionable_retry_template(tmp_path: Path) -> None:
    quest_id = _new_quest(tmp_path)
    _open_baseline(tmp_path, quest_id)
    payload = call_tool(
        "cs_create_analysis_campaign",
        {
            "project": str(tmp_path),
            "quest_id": quest_id,
            "campaign_title": "writing-facing campaign",
            "campaign_goal": "summarize paper evidence",
            "slices": [{"slice_id": "S1", "question": "what changed?"}],
            "research_questions": ["what changed?"],
        },
    )
    assert payload["ok"] is False
    encoded = json.dumps(payload)
    assert "selected_outline_ref" in encoded
    assert "retry_template" in payload
    assert payload["retry_template"]["name"] == "cs_create_analysis_campaign"


def test_analysis_campaign_preflight_reports_all_missing_writing_contract_fields(tmp_path: Path) -> None:
    quest_id = _new_quest(tmp_path)
    _open_baseline(tmp_path, quest_id)
    payload = call_tool(
        "cs_create_analysis_campaign",
        {
            "project": str(tmp_path),
            "quest_id": quest_id,
            "campaign_title": "writing-facing campaign",
            "campaign_goal": "summarize paper evidence",
            "selected_outline_ref": "outline-001",
            "research_questions": ["what changed?"],
            "slices": [{"slice_id": "S1", "question": "what changed?"}],
        },
    )
    assert payload["ok"] is False
    assert payload["error_type"] == "missing_argument"
    assert {"experimental_designs", "todo_items"} <= set(payload["missing_context_keys"])
    assert payload["retry_template"]["name"] == "cs_create_analysis_campaign"
    encoded = json.dumps(payload["retry_template"], ensure_ascii=False)
    assert "section_id" in encoded and "claim_links" in encoded


def test_artifact_record_rejects_unknown_kind_with_allowed_kinds_and_retry_template(tmp_path: Path) -> None:
    quest_id = _new_quest(tmp_path)
    payload = call_tool(
        "cs_artifact_record",
        {
            "project": str(tmp_path),
            "quest_id": quest_id,
            "kind": "dataset_inspection",
            "summary": "synthetic dataset inspection",
        },
    )
    assert payload["ok"] is False
    assert payload["error_type"] == "invalid_argument"
    assert "report" in payload["allowed_kinds"]
    assert payload["retry_template"] == {
        "name": "cs_artifact_record",
        "kind": "report",
        "payload": {"kind": "report", "report_type": "dataset_inspection", "summary": "synthetic dataset inspection"},
    }


def test_bash_exec_outside_workdir_reports_allowed_roots_and_retry_template(tmp_path: Path) -> None:
    quest_id = _new_quest(tmp_path)
    outside = tmp_path.parent
    payload = call_tool(
        "cs_bash_exec",
        {
            "project": str(tmp_path),
            "quest_id": quest_id,
            "operation": "run",
            "command": "python -V",
            "command_class": "formal_experiment",
            "provenance_reason": "regression test for formal-run safety envelope",
            "experiment_or_artifact_id": "run-outside-workdir",
            "cwd_policy": "quest",
            "expected_outputs": ["version output"],
            "workdir": str(outside),
        },
    )
    assert payload["ok"] is False
    assert payload["error_type"] == "workdir_outside_quest"
    assert payload.get("allowed_roots")
    assert payload.get("retry_template", {}).get("name") == "cs_bash_exec"


def test_paper_reliability_verify_supports_bounded_dry_run(tmp_path: Path) -> None:
    quest_id = _new_quest(tmp_path)
    command = [
        sys.executable,
        "-c",
        (
            "import json; "
            "from codex_scientist.mcp.tool_registry import call_tool; "
            "payload = call_tool('cs_paper_reliability_verify', "
            + repr(
                {
                    "project": str(tmp_path),
                    "quest_id": quest_id,
                    "title": "Toy Paper",
                    "url": "https://example.com/toy",
                    "dry_run": True,
                    "network": False,
                }
            )
            + "); "
            "print(json.dumps(payload))"
        ),
    ]
    result = subprocess.run(command, cwd=str(REPO_ROOT), text=True, capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["network"] is False
    assert payload["tool"] == "cs_paper_reliability_verify"
    assert "reliability_card_path" not in payload
    assert payload["suggested_next_action"].startswith("Retry cs_paper_reliability_verify")


def test_paper_reliability_verify_external_url_without_bounded_mode_fails_fast(tmp_path: Path) -> None:
    quest_id = _new_quest(tmp_path)
    command = [
        sys.executable,
        "-c",
        (
            "import json; "
            "from codex_scientist.mcp.tool_registry import call_tool; "
            "payload = call_tool('cs_paper_reliability_verify', "
            + repr(
                {
                    "project": str(tmp_path),
                    "quest_id": quest_id,
                    "title": "Toy Paper",
                    "url": "https://example.com/toy",
                }
            )
            + "); "
            "print(json.dumps(payload))"
        ),
    ]
    result = subprocess.run(command, cwd=str(REPO_ROOT), text=True, capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error_type"] == "external_io_requires_bounded_mode"
    assert payload["recoverable"] is True
    assert "dry_run" in json.dumps(payload)


def test_submit_paper_outline_accepts_string_list_as_section_titles(tmp_path: Path) -> None:
    quest_id = _new_quest(tmp_path)

    payload = _ok(
        call_tool(
            "cs_submit_paper_outline",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "title": "Toy Paper",
                "story": "toy story",
                "detailed_outline": ["Introduction", "Method"],
            },
        )
    )
    sections = payload["record"]["sections"]
    assert [section["title"] for section in sections] == ["Introduction", "Method"]


def test_baseline_gate_errors_use_mcp_tool_guidance(tmp_path: Path) -> None:
    quest_id = _new_quest(tmp_path)
    outside_baseline = tmp_path / "baseline.md"
    outside_baseline.write_text("# external baseline\n", encoding="utf-8")

    confirm = call_tool(
        "cs_confirm_baseline",
        {"project": str(tmp_path), "quest_id": quest_id, "baseline_path": str(outside_baseline)},
    )
    assert confirm.get("ok") is False
    assert confirm.get("error_type") == "invalid_argument"
    assert "cs_create_local_baseline" in confirm.get("suggested_next_action", "")
    assert "artifact.confirm_baseline" not in json.dumps(confirm)
    assert "baseline_path must be under quest_root" in json.dumps(confirm)

    experiment = call_tool(
        "cs_record_main_experiment",
        {"project": str(tmp_path), "quest_id": quest_id, "run_id": "run1", "title": "run"},
    )
    assert experiment.get("ok") is False
    encoded = json.dumps(experiment)
    assert "artifact.confirm_baseline" not in encoded
    assert "artifact.waive_baseline" not in encoded
    assert "cs_confirm_baseline" in encoded
    assert "cs_waive_baseline" in encoded


def test_submit_idea_missing_nested_contract_fields_returns_retry_template(tmp_path: Path) -> None:
    quest_id = _new_quest(tmp_path)

    payload = call_tool(
        "cs_submit_idea",
        {
            "project": str(tmp_path),
            "quest_id": quest_id,
            "title": "idea missing mechanism",
            "novelty_contract": {
                "related_work_refs": ["Toy2024"],
                "expected_difference": "different objective",
            },
        },
    )
    assert payload.get("ok") is False
    assert payload.get("error_type") == "missing_mechanism"
    retry_template = payload.get("retry_template") or {}
    assert retry_template.get("name") == "cs_submit_idea"
    minimal = retry_template.get("minimal_novelty_contract") or {}
    assert set(minimal) >= {"mechanism", "related_work_refs", "expected_difference"}
    assert "novelty_contract.mechanism" in payload.get("suggested_next_action", "")


def test_native_cli_accepts_cs_status_as_lightweight_mcp_boundary_hint(tmp_path: Path) -> None:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "cs_native_cli.py"),
        "--format",
        "json",
        "call",
        "cs_status",
        "--json",
        json.dumps({"project": str(tmp_path)}),
    ]
    result = subprocess.run(command, cwd=str(REPO_ROOT), text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload.get("ok") is True
    assert payload.get("tool") == "cs_status"
    assert payload.get("mcp") is False
    assert payload.get("mcp_hint") == "Use scripts/cs_mcp.py for the default MCP registry surface."
