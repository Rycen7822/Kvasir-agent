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
