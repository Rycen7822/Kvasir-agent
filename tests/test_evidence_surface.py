"""Public protocol, packaging and manual-only entrypoint regression checks."""
import io
import json
import os
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from kvasir_agent.mcp.server import run_stdio
from kvasir_agent.mcp.tool_registry import call_tool, tools_list_payload
from kvasir_agent.services.evidence_contracts import CONTRACTS

ROOT = Path(__file__).resolve().parents[1]


def test_active_skills_and_manual_is_outside_discovery():
    manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    active = sorted((ROOT / manifest["skills"]).rglob("SKILL.md"))
    assert {path.parent.name for path in active} == {"kvasir-agent", "delphi-idea-spark", "delphi-ponder-forge"}
    manual = ROOT / "manual/init/SKILL.md"
    assert manual.is_file() and not manual.is_relative_to(ROOT / manifest["skills"])
    surface = json.dumps(manifest) + "".join(path.read_text() for path in active) + json.dumps(tools_list_payload())
    for forbidden in ["ka_project_init", "manual/init", "ka_admin", "kvasir-agent-manual-init", "allow_implicit_invocation"]:
        assert forbidden not in surface
    assert '"manual" = "manual"' in (ROOT / "pyproject.toml").read_text()
    assert all(len(path.read_text()) < 4500 for path in active)


def test_versioned_file_schemas_and_examples_match():
    for kind, schema in CONTRACTS.items():
        published = json.loads((ROOT / f"docs/specs/{kind}.schema.json").read_text())
        published.pop("$schema")
        assert published == schema
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(json.loads((ROOT / f"docs/specs/{kind}.example.json").read_text()))
    for kind in ["run", "check"]:
        Draft202012Validator(CONTRACTS[kind]).validate(json.loads((ROOT / f"docs/specs/{kind}-v2.example.json").read_text()))
    for branch in CONTRACTS["research"]["oneOf"]:
        kind = branch["properties"]["kind"]["const"]
        published = json.loads((ROOT / f"docs/specs/research-{kind}.schema.json").read_text())
        published.pop("$schema")
        assert published == branch


def test_manual_init_from_arbitrary_cwd_writes_no_prompt_files(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    for cmd in [[sys.executable, str(ROOT / "scripts/ka_admin.py"), "init", "--project", str(project)],
                ["bash", str(ROOT / "scripts/init_project.sh"), str(project)]]:
        proc = subprocess.run(cmd, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert json.loads(proc.stdout)["ok"]
    assert not (project / ".codex").exists()
    assert not (project / "AGENTS.md").exists()
    assert sorted(p.name for p in project.iterdir()) == ["Kvasir-agent"]


def test_retired_generic_cli_cannot_dispatch_or_write(tmp_path):
    for script in ["ka_native_cli.py", "kactl.py"]:
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / script), "--project", str(tmp_path),
                               "call", "ka_submit_requirements", "--json", "{}"],
                              capture_output=True, text=True, timeout=10)
        assert proc.returncode == 2
        assert json.loads(proc.stdout)["error_type"] == "interface_retired"
    assert list(tmp_path.iterdir()) == []


def test_absolute_project_extra_arguments_and_traversal_fail_closed(tmp_path):
    for args in [{"project": "."}, {"project": str(tmp_path), "profile": "executor_local"},
                 {"project": str(tmp_path), "run_id": "../../outside"},
                 {"project_root": str(tmp_path)}]:
        assert not call_tool("ka_research_status", args)["ok"]
    assert list(tmp_path.iterdir()) == []


def test_stdio_errors_remain_bounded_and_connection_survives(tmp_path):
    output = io.StringIO()
    messages = ["not json", json.dumps({"jsonrpc": "2.0", "id": 1, "method": "password=keep-secret"}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "ka_research_status", "arguments": {"project": str(tmp_path), "secret": "x" * 100000}}}),
                json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})]
    assert run_stdio(io.StringIO("\n".join(messages)), output) == 0
    replies = [json.loads(line) for line in output.getvalue().splitlines()]
    assert len(replies) == 4 and len(replies[-1]["result"]["tools"]) == 4
    assert "keep-secret" not in output.getvalue()
    assert len(json.dumps(replies[2])) < 1000


def test_public_catalog_is_small_and_explicit():
    expected = tools_list_payload()
    for definition in expected["tools"]:
        assert definition["inputSchema"]["required"]
        assert definition["inputSchema"]["additionalProperties"] is False
    assert len(json.dumps(expected, separators=(",", ":"))) < 5500


def test_doctor_uses_current_evidence_server_without_initializing(tmp_path):
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/doctor.py")], cwd=tmp_path,
                          capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert len(payload["tools"]) == 4 and not payload["problems"]
    assert "runtime_doctor" not in payload
    assert list(tmp_path.iterdir()) == []


def test_delphi_invalid_calls_do_not_create_project_state(tmp_path):
    for fields in [
        {"workflow": "idea_spark", "action": "init"},
        {"workflow": "idea_spark", "action": "open", "goal": "Question", "request_id": "bad", "mode": "unsupported"},
        {"workflow": "idea_spark", "action": "status", "room_id": "room_absent"},
        {"workflow": "ponder_forge", "action": "update", "run_id": "run_absent"},
        {"workflow": "ponder_forge", "action": "status", "run_id": "run_absent", "command": "arbitrary"},
    ]:
        assert not call_tool("ka_delphi", {"project": str(tmp_path), **fields})["ok"]
    assert list(tmp_path.iterdir()) == []


def test_delphi_allocation_retry_and_independent_complete_files(tmp_path):
    for workflow in ("idea_spark", "ponder_forge"):
        project = tmp_path / workflow
        project.mkdir()
        base = {"project": str(project), "workflow": workflow}
        opened = call_tool("ka_delphi", {**base, "action": "open", "goal": "Research question", "request_id": "open"})
        assert opened["ok"], opened
        identity = {key: opened[key] for key in ("room_id", "run_id") if key in opened}
        deliveries = []
        full_body = "# Complete report\n" + "Independent research detail.\n" * 100
        for index in range(2):
            brief = project / f"brief-{index}.json"
            payload = ({"task": "Independent review", "title": "Full report", "artifact_type": "MetaReview"}
                       if workflow == "idea_spark" else {"tasks": [{"agent": f"reviewer-{index}", "prompt": "Independent review"}]})
            brief.write_text(json.dumps(payload))
            arguments = {**base, **identity, "action": "prepare", "input_path": str(brief), "request_id": f"review-{index}"}
            if workflow == "idea_spark":
                arguments["agent_id"] = f"reviewer-{index}"
            prepared = call_tool("ka_delphi", arguments)
            replay = call_tool("ka_delphi", arguments)
            assert prepared["ok"] and replay["ok"] and replay["idempotent"]
            delivery = prepared if workflow == "idea_spark" else prepared["assignments"][0]
            repeated = replay if workflow == "idea_spark" else replay["assignments"][0]
            assert repeated["file_path"] == delivery["file_path"]
            Path(delivery["file_path"]).write_text(full_body)
            deliveries.append(delivery)
            if workflow == "idea_spark":
                payload["task"] = "A different research task"
            else:
                payload["tasks"][0]["prompt"] = "A different research task"
            brief.write_text(json.dumps(payload))
            assert not call_tool("ka_delphi", arguments)["ok"]
        assert deliveries[0]["file_path"] != deliveries[1]["file_path"]
        result = call_tool("ka_delphi", {**base, **identity, "action": "collect",
                                         "receipt_paths": [item["receipt_path"] for item in deliveries]})
        assert result["ok"], result
        assert len(result["deliveries"]) == 2
        for item in result["deliveries"]:
            assert Path(item["file_path"]).read_text() == full_body
        status = call_tool("ka_delphi", {**base, **identity, "action": "status", "limit": 1})
        assert status["ok"] and status["has_more"]
        assert len(status["artifacts"] if workflow == "idea_spark" else status["reports"]) == 1
        assert full_body not in json.dumps(status)
        if workflow == "ponder_forge":
            draft = project / "draft.md"
            draft.write_text("Complete original answer.\n")
            verification = project / "verification.json"
            verification.write_text(json.dumps({"mode": "final", "draft_path": str(draft)}))
            arguments = {**base, **identity, "action": "verify", "input_path": str(verification), "request_id": "verification"}
            original = call_tool("ka_delphi", arguments)
            assert original["ok"] and "Complete original answer." in original["assignments"][0]["instructions"]
            draft.write_text("Different answer needing fresh verification.\n")
            assert not call_tool("ka_delphi", arguments)["ok"]
