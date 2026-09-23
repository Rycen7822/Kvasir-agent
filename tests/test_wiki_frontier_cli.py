from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_kactl(*args: str, project_root: Path) -> dict:
    proc = subprocess.run(
        [PYTHON, str(PLUGIN_ROOT / "scripts" / "kactl.py"), "--project-root", str(project_root), *args],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(proc.stdout)


def test_wiki_and_query_pack_cli_respects_budget(tmp_path: Path):
    paper = run_kactl("wiki", "add-paper", "--paper-id", "P1", "--title", "Paper", "--summary", "x" * 200, "--format", "json", project_root=tmp_path)
    assert paper["record"]["paper_id"] == "P1"

    idea = run_kactl("wiki", "add-idea", "--idea-id", "I1", "--title", "Idea", "--mechanism", "y" * 200, "--format", "json", project_root=tmp_path)
    assert idea["record"]["idea_id"] == "I1"

    edge = run_kactl("wiki", "add-edge", "--source-id", "P1", "--target-id", "I1", "--relation", "grounds", "--format", "json", project_root=tmp_path)
    assert edge["record"]["relation"] == "grounds"

    pack = run_kactl("wiki", "query-pack", "--max-chars", "120", "--format", "json", project_root=tmp_path)
    assert pack["ok"] is True
    assert len(pack["content"]) <= 120
    assert "P1" in pack["content"]
    assert "I1" in pack["content"]


def test_frontier_and_negative_memory_cli_keep_default_copilot_gate(tmp_path: Path):
    run_kactl("manifest", "init", "--name", "Demo", "--goal", "Improve", "--format", "json", project_root=tmp_path)

    candidate = run_kactl("frontier", "add", "--idea-id", "I1", "--score", "0.5", "--source", "human", "--title", "Idea", "--format", "json", project_root=tmp_path)
    assert candidate["candidate"]["idea_id"] == "I1"

    selected = run_kactl("frontier", "select", "--limit", "1", "--format", "json", project_root=tmp_path)
    assert selected["candidates"][0]["idea_id"] == "I1"

    promoted = run_kactl("frontier", "promote", "I1", "--evidence-level", "single_seed", "--format", "json", project_root=tmp_path)
    assert promoted["candidate"]["status"] == "promising"
    assert promoted["candidate"]["claim_status"] == "not_claimable"

    generated = run_kactl("frontier", "propose-generated", "--source", "frontier_gap", "--title", "New idea", "--format", "json", project_root=tmp_path)
    assert generated["status"] == "needs_user_decision"
    assert generated["created_running_trial"] is False

    negative = run_kactl("journal", "negative", "--trial-id", "T0001", "--idea-id", "I1", "--failure-reason", "metric dropped", "--lesson", "avoid", "--format", "json", project_root=tmp_path)
    assert negative["record"]["failure_reason"] == "metric dropped"
