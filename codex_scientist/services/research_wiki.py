from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .event_store import EventStore
from .project_state import ProjectLayout


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class ResearchWikiService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)
        self.wiki_dir = layout.state_root / "wiki"
        self.papers_path = self.wiki_dir / "papers.jsonl"
        self.ideas_path = self.wiki_dir / "ideas.jsonl"
        self.edges_path = self.wiki_dir / "edges.jsonl"

    def _append(self, path: Path, record: dict[str, Any]) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def _read(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def add_paper(self, paper_id: str, *, title: str, summary: str) -> dict[str, Any]:
        record = {"paper_id": paper_id, "title": title, "summary": summary, "created_at": _utc_now()}
        self._append(self.papers_path, record)
        self.events.append("wiki.paper_added", {"paper_id": paper_id})
        return record

    def add_idea(self, idea_id: str, *, title: str, mechanism: str) -> dict[str, Any]:
        record = {"idea_id": idea_id, "title": title, "mechanism": mechanism, "created_at": _utc_now()}
        self._append(self.ideas_path, record)
        self.events.append("wiki.idea_added", {"idea_id": idea_id})
        return record

    def add_edge(self, source_id: str, target_id: str, relation: str) -> dict[str, Any]:
        record = {"source_id": source_id, "target_id": target_id, "relation": relation, "created_at": _utc_now()}
        self._append(self.edges_path, record)
        self.events.append("wiki.edge_added", {"source_id": source_id, "target_id": target_id, "relation": relation})
        return record

    def query_pack(self, *, max_chars: int) -> dict[str, Any]:
        papers = self._read(self.papers_path)
        ideas = self._read(self.ideas_path)
        edges = self._read(self.edges_path)
        lines: list[str] = ["# Query Pack"]
        if papers:
            lines.append("PAPERS " + ",".join(str(paper["paper_id"]) for paper in papers))
        if ideas:
            lines.append("IDEAS " + ",".join(str(idea["idea_id"]) for idea in ideas))
        for paper in papers:
            summary = str(paper.get("summary", ""))[:48]
            lines.append(f"PAPER {paper['paper_id']}: {paper['title']} :: {summary}")
        for idea in ideas:
            mechanism = str(idea.get("mechanism", ""))[:48]
            lines.append(f"IDEA {idea['idea_id']}: {idea['title']} :: {mechanism}")
        for edge in edges:
            lines.append(f"EDGE {edge['source_id']} -{edge['relation']}-> {edge['target_id']}")
        content = "\n".join(lines)
        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars]
        return {"ok": True, "content": content, "truncated": truncated, "max_chars": max_chars}
