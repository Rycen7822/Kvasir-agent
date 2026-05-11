from __future__ import annotations


def test_frontier_selection_is_deterministic_and_single_seed_promotes_only_to_promising(tmp_path):
    from codex_scientist.services.frontier import FrontierService
    from codex_scientist.services.project_state import ProjectLayout

    frontier = FrontierService(ProjectLayout.from_project_root(tmp_path))
    frontier.add_candidate("I2", score=0.5, source="human")
    frontier.add_candidate("I1", score=0.5, source="human")
    frontier.add_candidate("I3", score=0.9, source="human")

    selected = frontier.select(limit=3)
    assert [item["idea_id"] for item in selected] == ["I3", "I1", "I2"]

    promoted = frontier.promote("I3", evidence_level="single_seed")
    assert promoted["candidate"]["status"] == "promising"
    assert promoted["candidate"]["claim_status"] == "not_claimable"


def test_default_copilot_frontier_generation_requires_user_decision(tmp_path):
    from codex_scientist.services.frontier import FrontierService
    from codex_scientist.services.manifest import ManifestService
    from codex_scientist.services.project_state import ProjectLayout

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest_service = ManifestService(layout)
    manifest_service.write(manifest_service.default_manifest(name="Demo", goal="Improve"))

    frontier = FrontierService(layout)
    result = frontier.propose_generated_candidate(source="frontier_gap", title="Try a new routing idea")

    assert result["ok"] is True
    assert result["status"] == "needs_user_decision"
    assert result["created_running_trial"] is False
