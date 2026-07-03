from __future__ import annotations

from pathlib import Path

from profiles import PROFILE_IDS, get_profile
from verifier import reviewer_role_for_profile

ROOT = Path(__file__).resolve().parents[1]
PROMPT_FILES = {
    "research": "research_fact_checker.md",
    "coding": "coding_causality_reviewer.md",
    "design": "design_decision_reviewer.md",
    "analysis": "analysis_repro_reviewer.md",
    "math": "math_proof_reviewer.md",
}


def test_each_profile_has_reviewer_role_and_prompt_contract():
    for profile_id in PROFILE_IDS:
        profile = get_profile(profile_id)
        role = reviewer_role_for_profile(profile_id)
        assert role in profile.roles or role.endswith("reviewer") or role.endswith("checker")
        path = ROOT / "prompts" / "reviewers" / PROMPT_FILES[profile_id]
        text = path.read_text(encoding="utf-8")
        assert "independent" in text.lower()
        assert "structured JSON reviewer report" in text
        assert "Ponder-Forge CLI" in text
        assert "ponder_forge_" not in text
        assert profile_id in text


def test_reviewer_prompts_do_not_claim_final_authority():
    for filename in PROMPT_FILES.values():
        text = (ROOT / "prompts" / "reviewers" / filename).read_text(encoding="utf-8").lower()
        assert "ponder_forge_" not in text
        assert "final answer" not in text
