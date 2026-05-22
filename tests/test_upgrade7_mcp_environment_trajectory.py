from __future__ import annotations

import hashlib
import json
from pathlib import Path

from codex_scientist.mcp.server import handle_jsonrpc_message
from codex_scientist.mcp.tool_registry import call_tool, tools_list_payload

QUEST_ID = "QMCP7"
ENV_ID = "env_mcp"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _toy_manifest(project: Path, *, quest_id: str = QUEST_ID, env_id: str = ENV_ID) -> dict:
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "data").mkdir(parents=True, exist_ok=True)
    protected = project / "src" / "eval.py"
    dataset = project / "data" / "toy.jsonl"
    protected.write_text("print('eval')\n", encoding="utf-8")
    dataset.write_text('{"x": 1}\n', encoding="utf-8")
    return {
        "schema_version": 1,
        "env_id": env_id,
        "quest_id": quest_id,
        "title": "MCP toy environment",
        "problem": "verify phase1 mcp tool exposure",
        "baseline": {"repo_path": ".", "baseline_metric": {"name": "score", "value": 0.5, "direction": "maximize"}},
        "mutable_allowlist": ["src/model.py"],
        "protected_files": [{"path": "src/eval.py", "sha256": _sha(protected)}],
        "datasets": [{"path": "data/toy.jsonl", "sha256": _sha(dataset)}],
        "commands": {
            "setup": [["python", "-V"]],
            "smoke": [["python", "-V"]],
            "run": [["python", "-V"]],
            "evaluate": [["python", "-V"]],
        },
        "primary_metric": {"name": "score", "direction": "maximize", "parser": "json_path", "path": "metrics.score"},
        "sample_metrics": {"metrics": {"score": 0.51}},
        "resources": {"gpu": 0, "cpu": 1},
        "budget": {"gpu_hours": 0.0, "usd_estimate": 0.0},
        "security": {"network": "off"},
    }


def test_mcp_call_round_trip_for_environment_trajectory_and_feedback(tmp_path: Path):
    manifest = _toy_manifest(tmp_path)
    project_root = str(tmp_path)

    registered = call_tool(
        "cs_environment_register",
        {"project_root": project_root, "quest_id": QUEST_ID, "manifest": manifest},
    )
    assert registered.get("ok") is True, registered
    assert registered.get("env_id") == ENV_ID

    validated = call_tool("cs_environment_validate", {"project_root": project_root, "quest_id": QUEST_ID, "env_id": ENV_ID})
    assert validated.get("ok") is True, validated
    assert validated.get("primary_metric", {}).get("value") == 0.51

    created = call_tool(
        "cs_trajectory_record",
        {
            "project_root": project_root,
            "quest_id": QUEST_ID,
            "env_id": ENV_ID,
            "idea": {"idea_id": "idea_mcp", "title": "Small improvement", "mechanism_family": "toy"},
            "strategy": "manual",
        },
    )
    assert created.get("ok") is True, created
    trajectory_id = created["trajectory_id"]

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({"metrics": {"score": 0.62}}), encoding="utf-8")
    log_path = tmp_path / "run.log"
    log_path.write_text("epoch=1 token=secret-value\nscore=0.62\n", encoding="utf-8")
    feedback = call_tool(
        "cs_feedback_ingest",
        {
            "project_root": project_root,
            "quest_id": QUEST_ID,
            "env_id": ENV_ID,
            "trajectory_id": trajectory_id,
            "run_id": "run_mcp",
            "source_kind": "local_metrics",
            "metrics_path": str(metrics_path),
            "log_paths": [str(log_path)],
            "trusted_primary_metric": True,
        },
    )
    assert feedback.get("ok") is True, feedback
    assert feedback.get("feedback", {}).get("primary_metric", {}).get("value") == 0.62
    assert "secret-value" not in json.dumps(feedback, ensure_ascii=False)

    shown = call_tool("cs_trajectory_show", {"project_root": project_root, "quest_id": QUEST_ID, "trajectory_id": trajectory_id})
    assert shown.get("ok") is True, shown
    assert shown["trajectory"]["result"]["status"] == "evaluated"

    searched = call_tool("cs_trajectory_search", {"project_root": project_root, "quest_id": QUEST_ID, "positive_only": True})
    assert searched.get("ok") is True, searched
    assert [item["trajectory_id"] for item in searched["trajectories"]] == [trajectory_id]


def test_phase1_mcp_schema_and_missing_argument_contracts_are_bounded():
    names = {tool["name"] for tool in tools_list_payload({"profile": "execution_planning"})["tools"]}
    assert "cs_environment_register" in names
    assert "cs_feedback_ingest" in names

    schema_response = handle_jsonrpc_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "cs_tool_schema", "arguments": {"name": "cs_feedback_ingest"}},
        }
    )
    assert schema_response is not None
    payload = schema_response["result"]["structuredContent"]
    assert payload.get("ok") is True, payload
    schema = payload["schema"]["input_schema"]
    assert {"quest_id", "env_id", "trajectory_id", "run_id", "source_kind"} <= set(schema.get("required", []))

    missing = call_tool("cs_feedback_ingest", {"quest_id": QUEST_ID})
    assert missing.get("ok") is False, missing
    assert missing.get("error_type") == "missing_argument"
    assert missing.get("recoverable") is True
    assert "env_id" in missing.get("missing_context_keys", [])
