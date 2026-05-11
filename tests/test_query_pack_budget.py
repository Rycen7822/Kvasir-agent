from __future__ import annotations


def test_query_pack_respects_character_budget_and_uses_compact_lines(tmp_path):
    from codex_scientist.services.project_state import ProjectLayout
    from codex_scientist.services.research_wiki import ResearchWikiService

    wiki = ResearchWikiService(ProjectLayout.from_project_root(tmp_path))
    wiki.add_paper("P1", title="A very useful paper", summary="x" * 200)
    wiki.add_idea("I1", title="A compact idea", mechanism="y" * 200)
    wiki.add_edge("P1", "I1", "grounds")

    pack = wiki.query_pack(max_chars=140)
    assert pack["ok"] is True
    assert len(pack["content"]) <= 140
    assert "P1" in pack["content"]
    assert "I1" in pack["content"]
    assert pack["truncated"] is True
