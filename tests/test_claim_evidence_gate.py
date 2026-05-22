from __future__ import annotations

from pathlib import Path
import json

from codex_scientist.mcp.tool_registry import call_tool


def test_claim_gate_blocks_without_required_evidence(tmp_path: Path):
    blocked = call_tool(
        "cs_claim_gate",
        {
            "project": str(tmp_path),
            "quest_id": "QCLAIM",
            "claim_id": "C1",
            "claim_text": "method improves accuracy",
            "baseline_id": "b1",
            "metric_contract": "primary",
            "evidence_paths": [],
            "analysis_slice_ids": [],
            "seed_count": 1,
        },
    )
    assert blocked["ok"] is False
    assert blocked["error_type"] == "claim_gate_blocked"
    assert {"evidence_path_missing", "analysis_slice_missing", "insufficient_seed_count"} <= set(blocked["blocking_reasons"])


def test_claim_gate_allows_evidence_backed_claim(tmp_path: Path):
    evidence = tmp_path / "CodexScientist" / "artifacts" / "analysis" / "metrics.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("{}\n", encoding="utf-8")
    manifest = tmp_path / "CodexScientist" / ".cs" / "analysis_campaigns" / "analysis-regression.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps({"campaign_id": "analysis-regression", "slices": [{"slice_id": "slice-1", "status": "completed"}]}),
        encoding="utf-8",
    )

    allowed = call_tool(
        "cs_claim_gate",
        {
            "project": str(tmp_path),
            "quest_id": "QCLAIM2",
            "claim_id": "C2",
            "claim_text": "method improves accuracy",
            "baseline_id": "b1",
            "metric_contract": "primary",
            "evidence_paths": [str(evidence)],
            "analysis_slice_ids": ["slice-1"],
            "seed_count": 3,
        },
    )
    assert allowed["ok"] is True, allowed
    assert allowed["claim_gate"]["claimable"] is True
    assert allowed["claim_gate"]["claim_id"] == "C2"


def test_claim_gate_blocks_unknown_analysis_slice_ids(tmp_path: Path):
    evidence = tmp_path / "CodexScientist" / "artifacts" / "analysis" / "metrics.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("{}\n", encoding="utf-8")

    blocked = call_tool(
        "cs_claim_gate",
        {
            "project": str(tmp_path),
            "quest_id": "QCLAIM3",
            "claim_id": "C3",
            "claim_text": "method improves accuracy",
            "baseline_id": "b1",
            "metric_contract": "primary",
            "evidence_paths": [str(evidence)],
            "analysis_slice_ids": ["missing-slice"],
            "seed_count": 3,
        },
    )
    assert blocked["ok"] is False
    assert blocked["error_type"] == "claim_gate_blocked"
    assert "analysis_slice_not_found:missing-slice" in blocked["blocking_reasons"]
    assert blocked["claim_gate"]["claimable"] is False
    assert blocked["retry_template"]["name"] == "cs_claim_gate"
