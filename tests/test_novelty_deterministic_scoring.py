from __future__ import annotations

from codex_scientist.services.method_improvement import MethodImprovementService
from codex_scientist.services.project_state import ProjectLayout


def test_novelty_scoring_is_deterministic_and_bounded(tmp_path):
    service = MethodImprovementService(ProjectLayout.from_project_root(tmp_path))
    contract = {
        "mechanism": "adaptive evidence routing",
        "related_work_refs": ["paper-a", "paper-b"],
        "expected_difference": "scores claim evidence before writing",
        "risk_notes": ["toy validation only"],
    }

    first = service.score_novelty_contract(contract)
    second = service.score_novelty_contract(dict(contract))

    assert first == second
    assert set(first) == {"novelty", "feasibility", "evidence", "risk", "diversity"}
    assert all(0.0 <= value <= 1.0 for value in first.values())
