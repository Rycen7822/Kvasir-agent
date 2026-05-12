from __future__ import annotations

from pathlib import Path


def test_review_service_is_readonly_and_redacts_secret_like_content(tmp_path: Path):
    from codex_scientist.services.project_state import ProjectLayout
    from codex_scientist.services.review import ReviewService

    review = ReviewService(ProjectLayout.from_project_root(tmp_path))
    result = review.create_review(
        claim_text="Model improves accuracy; token=abc123",
        trial_ids=["T0001"],
        artifact_paths=["CodexScientist/trials/T0001/metrics.json"],
        verdict="needs_fix",
        notes="Do not trust password=hunter2",
    )

    assert result["ok"] is True
    assert result["review"]["read_only"] is True
    assert result["review"]["allowed_actions"] == ["read_manifest", "read_trial_summary", "read_metric", "read_artifact_paths", "write_review_artifact"]
    assert "shell" not in result["review"]["allowed_actions"]
    assert "source_write" not in result["review"]["allowed_actions"]
    assert "abc123" not in Path(result["json_path"]).read_text(encoding="utf-8")
    assert "hunter2" not in Path(result["markdown_path"]).read_text(encoding="utf-8")
