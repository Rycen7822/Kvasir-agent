from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..shared import append_jsonl, ensure_dir, generate_id, slugify, utc_now
from .frontmatter import dump_markdown_document, load_markdown_document, load_markdown_document_from_text

MEMORY_KINDS = ("papers", "ideas", "decisions", "episodes", "knowledge", "templates")


class MemoryService:
    def __init__(self, home: Path) -> None:
        self.home = home

    @staticmethod
    def _normalize_tags(tags: list[str] | str | None) -> list[str]:
        if tags is None:
            return []
        raw_values: list[object]
        if isinstance(tags, str):
            stripped = tags.strip()
            if not stripped:
                return []
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    raw_values = list(parsed)
                else:
                    raw_values = [part.strip() for part in stripped.split(",")]
            else:
                raw_values = [part.strip() for part in stripped.split(",")]
        else:
            raw_values = list(tags)

        normalized: list[str] = []
        seen: set[str] = set()
        for item in raw_values:
            value = str(item or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized

    def _root_for(self, scope: str, quest_root: Path | None = None) -> Path:
        if scope == "global":
            return self.home / "memory"
        if scope == "quest":
            if quest_root is None:
                raise ValueError("quest_root is required for quest-scoped memory")
            return quest_root / "memory"
        raise ValueError(f"Unknown memory scope: {scope}")

    def _resolve_existing_card(
        self,
        *,
        card_id: str | None = None,
        path: str | None = None,
        scope: str,
        quest_root: Path | None = None,
    ) -> Path:
        if path:
            candidate = Path(path)
            if candidate.exists():
                return candidate
        root = self._root_for(scope, quest_root)
        if card_id:
            for candidate in root.glob("**/*.md"):
                metadata, _body = load_markdown_document(candidate)
                if metadata.get("id") == card_id:
                    return candidate
        raise FileNotFoundError("Memory card not found")

    def _normalize_metadata(
        self,
        *,
        kind: str,
        title: str,
        scope: str,
        quest_id: str | None,
        tags: list[str] | str | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        seed = dict(metadata or {})
        seed.setdefault("id", generate_id(kind[:-1] if kind.endswith("s") else kind))
        seed["type"] = kind
        seed.setdefault("kind", kind[:-1] if kind.endswith("s") else kind)
        seed.setdefault("title", title)
        seed.setdefault("quest_id", quest_id)
        seed.setdefault("tags", self._normalize_tags(tags))
        seed.setdefault("created_at", now)
        seed["updated_at"] = now
        seed["scope"] = scope
        return seed

    def write_card(
        self,
        *,
        scope: str,
        kind: str,
        title: str,
        body: str = "",
        markdown: str | None = None,
        quest_root: Path | None = None,
        quest_id: str | None = None,
        tags: list[str] | str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        if kind not in MEMORY_KINDS:
            raise ValueError(f"Unknown memory kind: {kind}. Allowed memory kinds: {', '.join(MEMORY_KINDS)}")
        root = self._root_for(scope, quest_root)
        folder = ensure_dir(root / kind)
        if markdown and markdown.lstrip().startswith("---"):
            parsed_metadata, parsed_body = load_markdown_document_from_text(markdown)
            title = str(parsed_metadata.get("title") or title or "Untitled")
            body = parsed_body
            metadata = {**parsed_metadata, **(metadata or {})}
        normalized = self._normalize_metadata(
            kind=kind,
            title=title,
            scope=scope,
            quest_id=quest_id,
            tags=tags,
            metadata=metadata,
        )
        filename = f"{slugify(title, kind)}.md"
        path = folder / filename
        path.write_text(dump_markdown_document(normalized, body), encoding="utf-8")
        self._append_index(folder / "_index.jsonl", path, normalized, body)
        return self.read_card(path=str(path), scope=scope, quest_root=quest_root)

    def read_card(
        self,
        *,
        card_id: str | None = None,
        path: str | None = None,
        scope: str = "global",
        quest_root: Path | None = None,
    ) -> dict:
        resolved = self._resolve_existing_card(card_id=card_id, path=path, scope=scope, quest_root=quest_root)
        metadata, body = load_markdown_document(resolved)
        return {
            "id": metadata.get("id"),
            "title": metadata.get("title", resolved.stem),
            "type": metadata.get("type"),
            "scope": metadata.get("scope", scope),
            "path": str(resolved),
            "metadata": metadata,
            "body": body,
            "updated_at": metadata.get("updated_at"),
            "excerpt": body.strip().splitlines()[0] if body.strip() else "",
        }

    def list_cards(
        self,
        *,
        scope: str = "global",
        quest_root: Path | None = None,
        limit: int = 30,
        kind: str | None = None,
    ) -> list[dict]:
        root = self._root_for(scope, quest_root)
        cards: list[dict] = []
        pattern = f"{kind}/*.md" if kind else "*/*.md"
        for path in sorted(root.glob(pattern)):
            metadata, body = load_markdown_document(path)
            cards.append(
                {
                    "id": metadata.get("id"),
                    "title": metadata.get("title", path.stem),
                    "type": metadata.get("type"),
                    "path": str(path),
                    "document_id": f"memory::{path.relative_to(root).as_posix()}",
                    "excerpt": body.strip().splitlines()[0] if body.strip() else "",
                    "updated_at": metadata.get("updated_at"),
                    "writable": True,
                }
            )
        return cards[-limit:]

    def list_recent(
        self,
        *,
        scope: str = "global",
        quest_root: Path | None = None,
        limit: int = 20,
        kind: str | None = None,
    ) -> list[dict]:
        cards = self.list_cards(scope=scope, quest_root=quest_root, limit=5000, kind=kind)
        cards.sort(key=self._card_sort_key, reverse=True)
        return cards[:limit]

    def search(
        self,
        query: str,
        *,
        scope: str = "global",
        quest_root: Path | None = None,
        limit: int = 20,
        kind: str | None = None,
    ) -> list[dict]:
        query_lower = query.lower()
        matches: list[dict] = []
        scopes = [scope]
        if scope == "both":
            scopes = ["quest", "global"]
        for resolved_scope in scopes:
            if resolved_scope == "quest" and quest_root is None:
                continue
            for card in self.list_cards(scope=resolved_scope, quest_root=quest_root, limit=500, kind=kind):
                content = Path(card["path"]).read_text(encoding="utf-8").lower()
                if query_lower in content:
                    match = dict(card)
                    match["scope"] = resolved_scope
                    matches.append(match)
        matches.sort(key=self._card_sort_key, reverse=True)
        return matches[:limit]

    def promote_to_global(
        self,
        *,
        card_id: str | None = None,
        path: str | None = None,
        quest_root: Path,
    ) -> dict:
        current = self.read_card(card_id=card_id, path=path, scope="quest", quest_root=quest_root)
        metadata = dict(current["metadata"])
        metadata["scope"] = "global"
        metadata["promoted_from"] = {
            "quest_root": str(quest_root),
            "path": current["path"],
        }
        return self.write_card(
            scope="global",
            kind=str(metadata.get("type") or "knowledge"),
            title=str(metadata.get("title") or "Promoted memory"),
            body=current["body"],
            metadata=metadata,
        )

    @staticmethod
    def _append_index(path: Path, card_path: Path, metadata: dict[str, Any], body: str) -> None:
        append_jsonl(
            path,
            {
                "id": metadata.get("id"),
                "title": metadata.get("title"),
                "type": metadata.get("type"),
                "path": str(card_path),
                "quest_id": metadata.get("quest_id"),
                "scope": metadata.get("scope"),
                "tags": metadata.get("tags", []),
                "updated_at": metadata.get("updated_at"),
                "excerpt": body.strip().splitlines()[0] if body.strip() else "",
            },
        )

    @staticmethod
    def _card_sort_key(card: dict[str, Any]) -> tuple[float, str]:
        updated_at = str(card.get("updated_at") or "").strip()
        try:
            parsed = datetime.fromisoformat(updated_at).timestamp() if updated_at else float("-inf")
        except ValueError:
            parsed = float("-inf")
        return parsed, str(card.get("path") or "")
