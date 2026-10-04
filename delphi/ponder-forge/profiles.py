from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileSpec:
    profile_id: str
    roles: tuple[str, ...]


PROFILES: dict[str, ProfileSpec] = {
    "research": ProfileSpec(
        profile_id="research",
        roles=("researcher", "domain_specialist", "fact_checker", "conflict_reviewer", "draft_reviewer", "global_verifier"),
    ),
    "coding": ProfileSpec(
        profile_id="coding",
        roles=("bug_reproducer", "developer", "test_runner", "code_reviewer", "causality_reviewer", "regression_reviewer"),
    ),
    "design": ProfileSpec(
        profile_id="design",
        roles=("requirements_analyst", "architecture_designer", "risk_reviewer", "simplicity_reviewer", "implementation_planner"),
    ),
    "analysis": ProfileSpec(
        profile_id="analysis",
        roles=("data_inspector", "metric_analyst", "reproduction_runner", "sanity_reviewer", "narrative_reviewer"),
    ),
    "math": ProfileSpec(
        profile_id="math",
        roles=("solver", "proof_checker", "counterexample_searcher", "revision_solver", "final_proof_reviewer"),
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
