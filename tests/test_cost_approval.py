from __future__ import annotations


def test_cost_approval_allows_readonly_and_blocks_over_budget_gpu(tmp_path):
    from codex_scientist.services.costs import CostApprovalService
    from codex_scientist.services.project_state import ProjectLayout

    service = CostApprovalService(ProjectLayout.from_project_root(tmp_path), daily_cap_usd=1.0)

    readonly = service.evaluate_action(action_class="read-only local", estimated_cost_usd=0.0)
    assert readonly["decision"] == "allowed"

    gpu = service.evaluate_action(action_class="GPU/cloud job", estimated_cost_usd=2.5)
    assert gpu["decision"] == "blocked_budget"
    assert gpu["requires_approval"] is True


def test_cost_approval_blocks_destructive_and_scheduled_by_default(tmp_path):
    from codex_scientist.services.costs import CostApprovalService
    from codex_scientist.services.project_state import ProjectLayout

    service = CostApprovalService(ProjectLayout.from_project_root(tmp_path), daily_cap_usd=10.0)

    destructive = service.evaluate_action(action_class="destructive git/delete/upload", estimated_cost_usd=0.0)
    assert destructive["decision"] == "blocked_destructive"
    assert destructive["requires_approval"] is True

    scheduled = service.evaluate_action(action_class="scheduled/recurring job", estimated_cost_usd=0.1)
    assert scheduled["decision"] == "blocked_approval"
    assert scheduled["requires_approval"] is True
