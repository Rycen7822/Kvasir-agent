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


def test_only_one_active_skill_and_manual_is_outside_discovery():
    manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    active = list((ROOT / manifest["skills"]).rglob("SKILL.md"))
    assert active == [ROOT / "skills/kvasir-agent/SKILL.md"]
    manual = ROOT / "manual/init/SKILL.md"
    assert manual.is_file() and not manual.is_relative_to(ROOT / manifest["skills"])
    surface = json.dumps(manifest) + active[0].read_text() + json.dumps(tools_list_payload())
    for forbidden in ["ka_project_init", "manual/init", "ka_admin", "kvasir-agent-manual-init", "allow_implicit_invocation"]:
        assert forbidden not in surface
    assert '"manual" = "manual"' in (ROOT / "pyproject.toml").read_text()
    assert len(active[0].read_text()) < 4500


def test_versioned_file_schemas_and_examples_match():
    for kind, schema in CONTRACTS.items():
        published = json.loads((ROOT / f"docs/specs/{kind}.schema.json").read_text())
        published.pop("$schema")
        assert published == schema
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(json.loads((ROOT / f"docs/specs/{kind}.example.json").read_text()))


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
    assert len(replies) == 4 and len(replies[-1]["result"]["tools"]) == 5
    assert "keep-secret" not in output.getvalue()
    assert len(json.dumps(replies[2])) < 1000


def test_no_profile_or_environment_can_enable_extra_tools(monkeypatch):
    monkeypatch.setenv("KVASIR_AGENT_ENABLE_EXECUTOR_MCP", "1")
    expected = tools_list_payload()
    for profile in ["all", "admin", "executor_local", "core", "literature"]:
        assert tools_list_payload({"profile": profile}) == expected
    for definition in expected["tools"]:
        assert definition["inputSchema"]["required"]
        assert definition["inputSchema"]["additionalProperties"] is False
    assert len(json.dumps(expected, separators=(",", ":"))) < 5500


def test_all_retired_tool_names_fail_without_writes(tmp_path):
    retired = ['ka_artifact_index',
     'ka_artifact_record',
     'ka_bash_exec',
     'ka_checkpoint',
     'ka_claim_gate',
     'ka_confirm_baseline',
     'ka_context_pack',
     'ka_cost_status',
     'ka_create_analysis_campaign',
     'ka_create_local_baseline',
     'ka_definitely_missing_for_p4',
     'ka_environment_register',
     'ka_environment_validate',
     'ka_evolutionary_plan_round',
     'ka_evolutionary_round_submit',
     'ka_feedback_ingest',
     'ka_get_analysis_campaign',
     'ka_get_method_scoreboard',
     'ka_get_optimization_frontier',
     'ka_get_quest_state',
     'ka_goal_next_action',
     'ka_goal_watchdog',
     'ka_log_digest',
     'ka_manifest_init',
     'ka_manifest_record_baseline',
     'ka_manifest_validate',
     'ka_memory_search',
     'ka_memory_write',
     'ka_missing_for_stress_regression',
     'ka_missing_goal_tool',
     'ka_missing_research_primitive',
     'ka_missing_tool',
     'ka_new_quest',
     'ka_pack_delta',
     'ka_queue_reconcile',
     'ka_queue_start_attempt',
     'ka_queue_status',
     'ka_queue_submit',
     'ka_record_analysis_slice',
     'ka_record_main_experiment',
     'ka_record_negative_result',
     'ka_record_user_requirement',
     'ka_refresh_summary',
     'ka_resume_brief',
     'ka_review_status',
     'ka_runner_start',
     'ka_runner_status',
     'ka_scheduler_submit',
     'ka_soak_accelerated',
     'ka_soak_crash_resume',
     'ka_status',
     'ka_submit_idea',
     'ka_submit_paper_outline',
     'ka_tool_schema',
     'ka_trajectory_record',
     'ka_trajectory_search',
     'ka_trajectory_show',
     'ka_trial_decide',
     'ka_trial_evaluate',
     'ka_trial_plan',
     'ka_trial_propose',
     'ka_trial_ready',
     'ka_trial_show',
     'ka_update_method_scoreboard',
     'ka_wiki_query_pack',
     'ka_worker_claim',
     'ka_worker_collect',
     'ka_worker_heartbeat',
     'ka_worker_upload_artifact']
    for name in retired:
        result = call_tool(name, {"project": str(tmp_path), "profile": "executor_local"})
        assert result["error_type"] == "tool_not_registered", name
    assert list(tmp_path.iterdir()) == []
