from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
QUEST_ID = "QCLI7"
ENV_ID = "env_cli"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _toy_manifest(project: Path) -> dict:
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "data").mkdir(parents=True, exist_ok=True)
    protected = project / "src" / "eval.py"
    dataset = project / "data" / "toy.jsonl"
    protected.write_text("print('eval')\n", encoding="utf-8")
    dataset.write_text('{"x": 1}\n', encoding="utf-8")
    return {
        "schema_version": 1,
        "env_id": ENV_ID,
        "quest_id": QUEST_ID,
        "title": "CLI toy environment",
        "problem": "verify phase1 native cli exposure",
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


def _cli(project: Path, tool: str, payload: dict) -> dict:
    result = subprocess.run(
        [
            PYTHON,
            str(REPO_ROOT / "scripts" / "cs_native_cli.py"),
            "--project-root",
            str(project),
            "call",
            tool,
            "--json",
            json.dumps(payload),
            "--format",
            "json",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def test_native_cli_lists_phase1_tools_and_round_trips_environment_and_trajectory(tmp_path: Path):
    listed = subprocess.run(
        [PYTHON, str(REPO_ROOT / "scripts" / "cs_native_cli.py"), "--project-root", str(tmp_path), "list-tools", "--format", "json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    tool_names = {tool["name"] for tool in json.loads(listed.stdout)["tools"]}
    assert {"cs_environment_validate", "cs_trajectory_show", "cs_feedback_ingest", "cs_evolutionary_plan_round"} <= tool_names

    manifest = _toy_manifest(tmp_path)
    registered = _cli(tmp_path, "cs_environment_register", {"quest_id": QUEST_ID, "manifest": manifest})
    assert registered.get("ok") is True, registered

    validated = _cli(tmp_path, "cs_environment_validate", {"quest_id": QUEST_ID, "env_id": ENV_ID})
    assert validated.get("ok") is True, validated
    assert validated.get("primary_metric", {}).get("value") == 0.51

    created = _cli(
        tmp_path,
        "cs_trajectory_record",
        {"quest_id": QUEST_ID, "env_id": ENV_ID, "idea": {"idea_id": "idea_cli", "title": "CLI improvement"}},
    )
    assert created.get("ok") is True, created

    shown = _cli(tmp_path, "cs_trajectory_show", {"quest_id": QUEST_ID, "trajectory_id": created["trajectory_id"]})
    assert shown.get("ok") is True, shown
    assert shown["trajectory"]["idea"]["idea_id"] == "idea_cli"
