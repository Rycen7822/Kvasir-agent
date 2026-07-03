from __future__ import annotations

import pytest

from profiles import PROFILE_IDS, get_profile, list_profiles, select_profile


def test_profiles_define_five_data_records():
    assert tuple(list_profiles()) == PROFILE_IDS == ("research", "coding", "design", "analysis", "math")

    for profile_id in PROFILE_IDS:
        profile = get_profile(profile_id)
        assert profile.profile_id == profile_id
        assert profile.roles
        assert profile.required_evidence_types
        assert profile.critical_assertion_types
        assert profile.gate_name


def test_profile_auto_routing_is_deterministic():
    assert select_profile("fix failing pytest in store.py") == "coding"
    assert select_profile("analyze csv metrics and plot experiment results") == "analysis"
    assert select_profile("prove this lemma and search for a counterexample") == "math"
    assert select_profile("write an architecture migration plan") == "design"
    assert select_profile("research papers in my knowledge base and write a survey") == "research"


def test_profile_auto_routing_honors_explicit_profile():
    assert select_profile("fix code", requested="research") == "research"
    with pytest.raises(ValueError):
        select_profile("fix code", requested="unknown")
