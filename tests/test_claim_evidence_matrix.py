from __future__ import annotations

from pathlib import Path


def test_claim_without_evidence_is_hypothesis_not_result_claim(tmp_path: Path):
    from codex_scientist.services.claims import ClaimEvidenceService
    from codex_scientist.services.project_state import ProjectLayout

    service = ClaimEvidenceService(ProjectLayout.from_project_root(tmp_path))
    claim = service.upsert_claim(claim_id="C1", text="Method improves accuracy")

    assert claim["claim"]["status"] == "hypothesis"
    assert claim["claim"]["included_in_results"] is False


def test_claim_with_evidence_writes_matrix_and_can_enter_results(tmp_path: Path):
    from codex_scientist.services.claims import ClaimEvidenceService
    from codex_scientist.services.project_state import ProjectLayout

    service = ClaimEvidenceService(ProjectLayout.from_project_root(tmp_path))
    result = service.upsert_claim(
        claim_id="C1",
        text="Method improves accuracy",
        supporting_trial_ids=["T0001"],
        metric_values={"accuracy": 0.91},
        artifact_paths=["CodexScientist/trials/T0001/metrics.json"],
        limitations=["toy data"],
        contradictory_trial_ids=["T0002"],
        reviewer_verdict="pass",
    )

    assert result["claim"]["status"] == "result_claim"
    assert result["claim"]["included_in_results"] is True
    matrix = Path(result["matrix_path"]).read_text(encoding="utf-8")
    assert "C1" in matrix
    assert "T0001" in matrix
    assert "toy data" in matrix
