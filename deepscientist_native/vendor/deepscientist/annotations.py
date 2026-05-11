from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .quest import QuestService
from .shared import ensure_dir, generate_id, read_json, utc_now, write_json

_QUEST_FILE_PREFIX = "quest-file::"
_SCHEMA_VERSION = 1
_DEFAULT_AUTHOR_COLOR = "#F1E9D0"
_ALLOWED_KINDS = {"note", "question", "task"}


def _json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value))


class AnnotationService:
    def __init__(self, home: Path) -> None:
        self.home = home.resolve()
        self._lock = threading.Lock()

    @staticmethod
    def _parse_quest_file_id(file_id: str) -> tuple[str, str, str]:
        raw = str(file_id or "").strip()
        if not raw.startswith(_QUEST_FILE_PREFIX):
            raise ValueError("Only quest file ids are supported for annotations.")
        payload = raw[len(_QUEST_FILE_PREFIX) :]
        project_id, encoded_document_id, encoded_path = (payload.split("::", 2) + ["", ""])[:3]
        project_id = str(project_id or "").strip()
        if not project_id or not encoded_document_id:
            raise ValueError("Invalid quest file id.")
        document_id = unquote(encoded_document_id)
        relative_path = unquote(encoded_path or encoded_document_id)
        if not document_id:
            raise ValueError("Invalid quest file id.")
        return project_id, document_id, relative_path

    def _quest_root(self, project_id: str) -> Path:
        quest_root = self.home / "quests" / project_id
        if not quest_root.exists():
            raise FileNotFoundError(f"Unknown quest `{project_id}`.")
        return quest_root

    @staticmethod
    def _manifest_path(quest_root: Path) -> Path:
        return quest_root / ".ds" / "annotations" / "index.json"

    def _load_manifest(self, quest_root: Path) -> dict[str, Any]:
        payload = read_json(self._manifest_path(quest_root), default=None)
        if not isinstance(payload, dict):
            payload = {}
        items = payload.get("items")
        if not isinstance(items, list):
            items = []
        return {
            "schema_version": _SCHEMA_VERSION,
            "updated_at": str(payload.get("updated_at") or utc_now()),
            "items": [dict(item) for item in items if isinstance(item, dict)],
        }

    def _save_manifest(self, quest_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = {
            "schema_version": _SCHEMA_VERSION,
            "updated_at": utc_now(),
            "items": [dict(item) for item in (payload.get("items") or []) if isinstance(item, dict)],
        }
        ensure_dir(self._manifest_path(quest_root).parent)
        write_json(self._manifest_path(quest_root), normalized)
        return normalized

    @staticmethod
    def _normalize_kind(value: object) -> str:
        kind = str(value or "note").strip().lower()
        return kind if kind in _ALLOWED_KINDS else "note"

    @staticmethod
    def _normalize_tags(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        seen: set[str] = set()
        for raw in value:
            tag = str(raw or "").strip()
            if not tag or tag in seen:
                continue
            seen.add(tag)
            result.append(tag)
        return result

    @classmethod
    def _normalize_position(cls, value: object) -> dict[str, Any]:
        payload = _json_clone(value if isinstance(value, dict) else {})
        if not isinstance(payload, dict):
            raise ValueError("`position` must be an object.")
        page_number = payload.get("pageNumber")
        if not isinstance(page_number, int) or page_number <= 0:
            raise ValueError("`position.pageNumber` must be a positive integer.")
        if not isinstance(payload.get("boundingRect"), dict):
            raise ValueError("`position.boundingRect` is required.")
        rects = payload.get("rects")
        if not isinstance(rects, list) or not rects:
            raise ValueError("`position.rects` must be a non-empty list.")
        return payload

    @classmethod
    def _normalize_content(cls, value: object) -> dict[str, Any]:
        payload = _json_clone(value if isinstance(value, dict) else {})
        if not isinstance(payload, dict):
            return {}
        text = payload.get("text")
        image = payload.get("image")
        result: dict[str, Any] = {}
        if isinstance(text, str):
            result["text"] = text
        if isinstance(image, str):
            result["image"] = image
        return result

    @staticmethod
    def _normalize_author(color: object) -> dict[str, str]:
        author_color = str(color or _DEFAULT_AUTHOR_COLOR).strip() or _DEFAULT_AUTHOR_COLOR
        return {
            "id": "local-user",
            "handle": "user",
            "color": author_color,
        }

    @classmethod
    def _normalize_item(cls, item: dict[str, Any]) -> dict[str, Any]:
        author = item.get("author") if isinstance(item.get("author"), dict) else {}
        color = str(item.get("color") or author.get("color") or _DEFAULT_AUTHOR_COLOR).strip() or _DEFAULT_AUTHOR_COLOR
        normalized = {
            "id": str(item.get("id") or "").strip(),
            "file_id": str(item.get("file_id") or "").strip(),
            "project_id": str(item.get("project_id") or "").strip(),
            "position": cls._normalize_position(item.get("position") or {}),
            "content": cls._normalize_content(item.get("content") or {}),
            "comment": str(item.get("comment") or "").strip(),
            "kind": cls._normalize_kind(item.get("kind")),
            "color": color,
            "tags": cls._normalize_tags(item.get("tags")),
            "created_by": str(item.get("created_by") or "local-user").strip() or "local-user",
            "author": {
                "id": str(author.get("id") or "local-user").strip() or "local-user",
                "handle": str(author.get("handle") or "user").strip() or "user",
                "color": str(author.get("color") or color).strip() or color,
            },
            "created_at": str(item.get("created_at") or utc_now()).strip() or utc_now(),
            "updated_at": str(item.get("updated_at") or utc_now()).strip() or utc_now(),
        }
        if not normalized["id"]:
            raise ValueError("Annotation id is required.")
        if not normalized["file_id"]:
            raise ValueError("Annotation file id is required.")
        if not normalized["project_id"]:
            raise ValueError("Annotation project id is required.")
        return normalized

    @staticmethod
    def _response_item(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item["id"],
            "file_id": item["file_id"],
            "project_id": item["project_id"],
            "position": _json_clone(item["position"]),
            "content": _json_clone(item["content"]),
            "comment": item["comment"],
            "kind": item["kind"],
            "color": item["color"],
            "tags": list(item["tags"]),
            "created_by": item["created_by"],
            "author": dict(item["author"]),
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
        }

    def _ensure_document_exists(self, project_id: str, document_id: str) -> None:
        quest_service = QuestService(self.home)
        quest_service.open_document(project_id, document_id)

    def list_annotations(self, file_id: str) -> dict[str, Any]:
        project_id, document_id, _relative_path = self._parse_quest_file_id(file_id)
        self._ensure_document_exists(project_id, document_id)
        manifest = self._load_manifest(self._quest_root(project_id))
        items = [
            self._response_item(self._normalize_item(item))
            for item in manifest["items"]
            if str(item.get("file_id") or "").strip() == file_id
        ]
        items.sort(key=lambda item: (item.get("created_at") or "", item.get("id") or ""), reverse=True)
        return {"items": items, "total": len(items)}

    def create_annotation(
        self,
        *,
        file_id: str,
        position: object,
        content: object,
        comment: object = "",
        kind: object = "note",
        color: object = None,
        tags: object = None,
    ) -> dict[str, Any]:
        project_id, document_id, _relative_path = self._parse_quest_file_id(file_id)
        self._ensure_document_exists(project_id, document_id)
        quest_root = self._quest_root(project_id)
        author = self._normalize_author(color)
        now = utc_now()
        item = self._normalize_item(
            {
                "id": generate_id("ann"),
                "file_id": file_id,
                "project_id": project_id,
                "position": position,
                "content": content,
                "comment": str(comment or "").strip(),
                "kind": kind,
                "color": author["color"],
                "tags": tags,
                "created_by": author["id"],
                "author": author,
                "created_at": now,
                "updated_at": now,
            }
        )
        with self._lock:
            manifest = self._load_manifest(quest_root)
            manifest["items"] = [*manifest["items"], item]
            self._save_manifest(quest_root, manifest)
        return self._response_item(item)

    def _find_annotation(self, annotation_id: str) -> tuple[Path, dict[str, Any], list[dict[str, Any]], int]:
        normalized_id = str(annotation_id or "").strip()
        if not normalized_id:
            raise FileNotFoundError("Unknown annotation.")
        quests_root = self.home / "quests"
        for quest_root in sorted(quests_root.iterdir()) if quests_root.exists() else []:
            if not quest_root.is_dir():
                continue
            manifest = self._load_manifest(quest_root)
            items = manifest["items"]
            for index, raw_item in enumerate(items):
                if str(raw_item.get("id") or "").strip() != normalized_id:
                    continue
                return quest_root, manifest, items, index
        raise FileNotFoundError(f"Unknown annotation `{normalized_id}`.")

    def get_annotation(self, annotation_id: str) -> dict[str, Any]:
        _quest_root, _manifest, items, index = self._find_annotation(annotation_id)
        return self._response_item(self._normalize_item(items[index]))

    def update_annotation(
        self,
        annotation_id: str,
        *,
        comment: object | None = None,
        kind: object | None = None,
        position: object | None = None,
        content: object | None = None,
        color: object | None = None,
        tags: object | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            quest_root, manifest, items, index = self._find_annotation(annotation_id)
            current = self._normalize_item(items[index])
            next_item = dict(current)
            if comment is not None:
                next_item["comment"] = str(comment or "").strip()
            if kind is not None:
                next_item["kind"] = self._normalize_kind(kind)
            if position is not None:
                next_item["position"] = self._normalize_position(position)
            if content is not None:
                next_item["content"] = self._normalize_content(content)
            if color is not None:
                resolved_color = str(color or current["color"]).strip() or current["color"]
                next_item["color"] = resolved_color
                next_item["author"] = {
                    **dict(current["author"]),
                    "color": resolved_color,
                }
            if tags is not None:
                next_item["tags"] = self._normalize_tags(tags)
            next_item["updated_at"] = utc_now()
            normalized = self._normalize_item(next_item)
            items[index] = normalized
            manifest["items"] = items
            self._save_manifest(quest_root, manifest)
        return self._response_item(normalized)

    def delete_annotation(self, annotation_id: str) -> dict[str, Any]:
        with self._lock:
            quest_root, manifest, items, index = self._find_annotation(annotation_id)
            removed = self._normalize_item(items[index])
            items.pop(index)
            manifest["items"] = items
            self._save_manifest(quest_root, manifest)
        return {"ok": True, "id": removed["id"], "file_id": removed["file_id"], "project_id": removed["project_id"]}

    def search_annotations(
        self,
        project_id: str,
        *,
        query: str | None = None,
        color: str | None = None,
        tag: str | None = None,
        page: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        quest_root = self._quest_root(project_id)
        manifest = self._load_manifest(quest_root)
        normalized_query = str(query or "").strip().lower()
        normalized_color = str(color or "").strip().lower()
        normalized_tag = str(tag or "").strip().lower()
        items: list[dict[str, Any]] = []
        for raw_item in manifest["items"]:
            item = self._normalize_item(raw_item)
            if normalized_color and str(item.get("color") or "").strip().lower() != normalized_color:
                continue
            if normalized_tag and normalized_tag not in {tag_item.lower() for tag_item in item.get("tags") or []}:
                continue
            if page is not None:
                item_page = item.get("position", {}).get("pageNumber")
                if item_page != page:
                    continue
            if normalized_query:
                haystack = " ".join(
                    [
                        str(item.get("comment") or ""),
                        str(item.get("content", {}).get("text") or ""),
                        " ".join(item.get("tags") or []),
                    ]
                ).lower()
                if normalized_query not in haystack:
                    continue
            items.append(self._response_item(item))
        items.sort(key=lambda item: (item.get("created_at") or "", item.get("id") or ""), reverse=True)
        return {"items": items[: max(1, limit)], "total": len(items)}
