from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileSpec:
    profile_id: str
    roles: tuple[str, ...]
    required_evidence_types: tuple[str, ...]
    critical_assertion_types: tuple[str, ...]
    required_evidence_groups: tuple[tuple[str, ...], ...]
    gate_name: str


PROFILES: dict[str, ProfileSpec] = {
    "research": ProfileSpec(
        profile_id="research",
        roles=("researcher", "domain_specialist", "fact_checker", "conflict_reviewer", "draft_reviewer", "global_verifier"),
        required_evidence_types=("source_quote", "primary_source", "secondary_source", "counterevidence", "definition_boundary"),
        critical_assertion_types=("factual_claim",),
        required_evidence_groups=(("source_quote", "primary_source", "secondary_source"),),
        gate_name="claim-evidence graph reasoning",
    ),
    "coding": ProfileSpec(
        profile_id="coding",
        roles=("bug_reproducer", "developer", "test_runner", "code_reviewer", "causality_reviewer", "regression_reviewer"),
        required_evidence_types=("failing_test", "passing_test", "execution_log", "diff", "code_pointer", "root_cause_trace", "regression_risk"),
        critical_assertion_types=("code_claim",),
        required_evidence_groups=(("root_cause_trace",), ("execution_log", "passing_test", "failing_test")),
        gate_name="causal-evidence comparison",
    ),
    "design": ProfileSpec(
        profile_id="design",
        roles=("requirements_analyst", "architecture_designer", "risk_reviewer", "simplicity_reviewer", "implementation_planner"),
        required_evidence_types=("requirement", "constraint", "existing_owner_seam", "alternative", "decision_reason", "rejection_reason", "acceptance_gate"),
        critical_assertion_types=("design_decision",),
        required_evidence_groups=(("constraint",), ("existing_owner_seam",), ("decision_reason",)),
        gate_name="decision-evidence graph review",
    ),
    "analysis": ProfileSpec(
        profile_id="analysis",
        roles=("data_inspector", "metric_analyst", "reproduction_runner", "sanity_reviewer", "narrative_reviewer"),
        required_evidence_types=("dataset", "transform_script", "metric_output", "sanity_check", "plot_artifact", "reproduction_log"),
        critical_assertion_types=("data_result",),
        required_evidence_groups=(("metric_output",), ("transform_script", "reproduction_log"), ("sanity_check",)),
        gate_name="computation-provenance verification",
    ),
    "math": ProfileSpec(
        profile_id="math",
        roles=("solver", "proof_checker", "counterexample_searcher", "revision_solver", "final_proof_reviewer"),
        required_evidence_types=("proof_attempt", "proof_step", "lemma", "critique", "proof_check", "counterexample", "revision_trace"),
        critical_assertion_types=("proof_step",),
        required_evidence_groups=(("proof_step",), ("critique", "proof_check")),
        gate_name="generate-verify-revise",
    ),
}
PROFILE_IDS = tuple(PROFILES)

_ROUTING_TERMS = {
    "coding": ("patch", "bug", "failing test", "stack trace", ".py", "implementation", "refactor", "lint", "type error", "benchmark regression", "code review", "pytest"),
    "analysis": ("dataset", "csv", "excel", "jsonl", "log", "metrics", "metric", "plot", "statistical", "experiment results", "calculate", "analysis"),
    "math": ("proof", "theorem", "derivation", "formal logic", "counterexample", "equation", "lemma"),
    "design": ("architecture", "planning", "roadmap", "system design", "migration", "product decision", "workflow design", "implementation plan"),
    "research": ("research", "source-backed", "literature", "survey", "knowledge base", "domain research", "papers", "factual synthesis"),
}


def is_valid_profile(profile: str) -> bool:
    return profile in PROFILES


def list_profiles() -> list[str]:
    return list(PROFILE_IDS)


def get_profile(profile: str) -> ProfileSpec:
    try:
        return PROFILES[profile]
    except KeyError as exc:
        raise ValueError(f"unknown Ponder-Forge profile: {profile}") from exc


def select_profile(goal: str, requested: str = "auto") -> str:
    if requested != "auto":
        if not is_valid_profile(requested):
            raise ValueError(f"unknown Ponder-Forge profile: {requested}")
        return requested
    text = goal.lower()
    for profile in ("coding", "analysis", "math", "design", "research"):
        if any(term in text for term in _ROUTING_TERMS[profile]):
            return profile
    return "research"
