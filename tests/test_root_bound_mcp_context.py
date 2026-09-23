from __future__ import annotations

import os

from kvasir_agent.mcp.context import KvasirAgentMcpContext
from kvasir_agent.mcp.research_tools import mcp_environment
from kvasir_agent.services.manifest import ManifestService
from kvasir_agent.services.project_state import ProjectLayout


def test_mcp_context_resolves_research_root_without_quest_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    context = KvasirAgentMcpContext.from_env({"project": str(tmp_path)})

    assert context.require_project_root() == tmp_path.resolve()
    assert context.require_research_root() == tmp_path / "Kvasir-agent"
    assert context.require_quest_root() == tmp_path / "Kvasir-agent"
    assert context.resolve_project_layout().state_root == tmp_path / "Kvasir-agent"


def test_mcp_environment_exports_root_bound_paths_without_creating_state(tmp_path, monkeypatch):
    monkeypatch.delenv("KA_QUEST_ID", raising=False)
    monkeypatch.delenv("KA_HOME", raising=False)
    monkeypatch.delenv("KA_QUEST_ROOT", raising=False)

    with mcp_environment({"project": str(tmp_path)}) as context:
        assert context.require_quest_root() == tmp_path / "Kvasir-agent"
        assert os.environ["KVASIR_AGENT_PROJECT_ROOT"] == str(tmp_path)
        assert os.environ["KA_HOME"] == str(tmp_path / "Kvasir-agent")
        assert os.environ["KA_QUEST_ROOT"] == str(tmp_path / "Kvasir-agent")
        assert "KA_QUEST_ID" not in os.environ
        assert not (tmp_path / "Kvasir-agent").exists()

    assert "KA_HOME" not in os.environ
    assert "KA_QUEST_ROOT" not in os.environ


def test_mcp_environment_exports_manifest_quest_id_when_manifest_exists(tmp_path, monkeypatch):
    manifest = ManifestService(ProjectLayout.from_project_root(tmp_path)).ensure_initialized(
        create=True,
        inferred_goal="single research root",
    )
    quest_id = manifest["manifest"]["quest"]["id"]
    monkeypatch.delenv("KA_QUEST_ID", raising=False)

    with mcp_environment({"project": str(tmp_path)}):
        assert os.environ["KA_HOME"] == str(tmp_path / "Kvasir-agent")
        assert os.environ["KA_QUEST_ROOT"] == str(tmp_path / "Kvasir-agent")
        assert os.environ["KA_QUEST_ID"] == quest_id
