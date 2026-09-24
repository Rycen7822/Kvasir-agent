"""Research services remain usable after removing generic memory machinery."""
from pathlib import Path

from kvasir_agent.runtime.config import NativeConfig
from kvasir_agent.runtime.runtime import get_services


def test_runtime_boot_preserves_documents_without_creating_generic_memory(tmp_path, monkeypatch):
    home = tmp_path / "runtime"
    old_note = home / "memory/papers/preserved.md"
    old_note.parent.mkdir(parents=True)
    old_note.write_text("Existing research source\n")
    before = (old_note.read_bytes(), old_note.stat().st_mtime_ns)
    config = NativeConfig(
        config_root=home, config_path=home / "config/native.yaml",
        runtime_home=home, session_map_path=home / "sessions.json",
    )
    services = get_services(config)
    assert services.artifact is not None and services.bash is not None
    assert (old_note.read_bytes(), old_note.stat().st_mtime_ns) == before
    for kind in ("decisions", "episodes", "knowledge", "templates"):
        assert not (home / "memory" / kind).exists()

    from kvasiragent.markdown import dump_markdown_document, load_markdown_document

    project = tmp_path / "project"
    idea = project / "memory/ideas/I1/idea.md"
    idea.parent.mkdir(parents=True)
    metadata = {"title": "Research idea", "idea_id": "I1"}
    idea.write_text(dump_markdown_document(metadata, "Hypothesis and source evidence\n"))
    assert load_markdown_document(idea) == (metadata, "Hypothesis and source evidence\n")
    monkeypatch.setattr(services.quest, "_require_initialized_quest_root", lambda _: project)
    monkeypatch.setattr(services.quest, "active_workspace_root", lambda _: project)
    documents = services.quest.list_documents("Q1")
    item = next(d for d in documents if d["document_id"] == "memory::ideas/I1/idea.md")
    assert Path(item["path"]) == idea


def test_prompt_builder_boot_has_no_general_memory_dependency(tmp_path):
    config = NativeConfig(
        config_root=tmp_path, config_path=tmp_path / "config.yaml",
        runtime_home=tmp_path, session_map_path=tmp_path / "sessions.json",
    )
    services = get_services(config)
    from kvasiragent.prompts import PromptBuilder

    builder = PromptBuilder(services.resource_repo_root, tmp_path)
    assert builder.quest_service is not None
    assert not (tmp_path / "memory").exists()
