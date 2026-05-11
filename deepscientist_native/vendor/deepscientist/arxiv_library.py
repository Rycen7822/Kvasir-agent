from __future__ import annotations

import threading
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from .artifact.arxiv import USER_AGENT, normalize_arxiv_id
from .shared import ensure_dir, read_json, utc_now, write_json


class ArxivLibraryService:
    _SCHEMA_VERSION = 2

    def __init__(self) -> None:
        self._manifest_lock = threading.Lock()
        self._download_lock = threading.Lock()
        self._inflight_downloads: set[tuple[str, str]] = set()

    @staticmethod
    def _root(quest_root: Path) -> Path:
        return quest_root / "literature" / "arxiv"

    @classmethod
    def _index_path(cls, quest_root: Path) -> Path:
        return cls._root(quest_root) / "index.json"

    @classmethod
    def _pdf_dir(cls, quest_root: Path) -> Path:
        return cls._root(quest_root) / "pdfs"

    @staticmethod
    def _pdf_file_name(arxiv_id: str) -> str:
        return f"{arxiv_id}.pdf"

    @classmethod
    def pdf_relative_path(cls, arxiv_id: str) -> str:
        return f"literature/arxiv/pdfs/{cls._pdf_file_name(arxiv_id)}"

    @classmethod
    def pdf_path(cls, quest_root: Path, arxiv_id: str) -> Path:
        return cls._pdf_dir(quest_root) / cls._pdf_file_name(arxiv_id)

    @classmethod
    def _empty_payload(cls) -> dict[str, Any]:
        return {
            "schema_version": cls._SCHEMA_VERSION,
            "updated_at": utc_now(),
            "items": [],
        }

    def load_manifest(self, quest_root: Path) -> dict[str, Any]:
        path = self._index_path(quest_root)
        payload = read_json(path, default=None)
        if not isinstance(payload, dict):
            payload = self._empty_payload()
        items = payload.get("items")
        if not isinstance(items, list):
            payload["items"] = []
        payload["schema_version"] = self._SCHEMA_VERSION
        payload["updated_at"] = str(payload.get("updated_at") or utc_now())
        return payload

    def save_manifest(self, quest_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload or {})
        normalized["schema_version"] = self._SCHEMA_VERSION
        normalized["updated_at"] = utc_now()
        if not isinstance(normalized.get("items"), list):
            normalized["items"] = []
        ensure_dir(self._root(quest_root))
        write_json(self._index_path(quest_root), normalized)
        return normalized

    @staticmethod
    def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(item or {})
        normalized["arxiv_id"] = str(normalized.get("arxiv_id") or "").strip()
        normalized["status"] = str(normalized.get("status") or "processing").strip() or "processing"
        metadata_status = str(normalized.get("metadata_status") or "").strip()
        if not metadata_status:
            metadata_status = "ready" if str(normalized.get("metadata_source") or "").strip() else ""
        normalized["metadata_status"] = metadata_status or None
        normalized["title"] = str(normalized.get("title") or normalized.get("display_name") or normalized["arxiv_id"]).strip()
        normalized["display_name"] = str(
            normalized.get("display_name") or normalized.get("title") or normalized["arxiv_id"]
        ).strip()
        normalized["abstract"] = str(normalized.get("abstract") or "").strip()
        normalized["overview"] = str(normalized.get("overview") or "").strip()
        normalized["overview_markdown"] = str(normalized.get("overview_markdown") or "").strip()
        normalized["summary_source"] = str(normalized.get("summary_source") or "").strip() or None
        normalized["overview_source"] = str(normalized.get("overview_source") or "").strip() or None
        normalized["metadata_source"] = str(normalized.get("metadata_source") or "").strip() or None
        normalized["published_at"] = str(normalized.get("published_at") or "").strip()
        normalized["primary_class"] = str(normalized.get("primary_class") or "").strip()
        bibtex = str(normalized.get("bibtex") or "").strip()
        normalized["bibtex"] = bibtex or None
        normalized["abs_url"] = str(normalized.get("abs_url") or "").strip() or None
        normalized["pdf_url"] = str(normalized.get("pdf_url") or "").strip() or None
        normalized["created_at"] = str(normalized.get("created_at") or utc_now()).strip()
        normalized["updated_at"] = str(normalized.get("updated_at") or utc_now()).strip()
        normalized["authors"] = [str(item).strip() for item in (normalized.get("authors") or []) if str(item).strip()]
        normalized["categories"] = [str(item).strip() for item in (normalized.get("categories") or []) if str(item).strip()]
        normalized["tags"] = [str(item).strip() for item in (normalized.get("tags") or []) if str(item).strip()]
        version = normalized.get("version")
        normalized["version"] = int(version) if isinstance(version, int) or str(version).isdigit() else None
        normalized["pdf_rel_path"] = str(normalized.get("pdf_rel_path") or "").strip() or None
        normalized["error"] = str(normalized.get("error") or "").strip() or None
        return normalized

    def get_item(self, quest_root: Path, arxiv_id: str) -> dict[str, Any] | None:
        normalized_id = normalize_arxiv_id(arxiv_id)
        if not normalized_id:
            return None
        payload = self.load_manifest(quest_root)
        for raw_item in payload.get("items") or []:
            if str(raw_item.get("arxiv_id") or "").strip() == normalized_id:
                return self._materialize_item(quest_root, self._normalize_item(dict(raw_item)))
        return None

    def list_items(self, quest_root: Path) -> list[dict[str, Any]]:
        payload = self.load_manifest(quest_root)
        items = [
            self._materialize_item(quest_root, self._normalize_item(dict(item)))
            for item in payload.get("items") or []
            if str(item.get("arxiv_id") or "").strip()
        ]
        return sorted(items, key=lambda item: str(item.get("updated_at") or ""), reverse=True)

    def upsert_item(self, quest_root: Path, item: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_item(item)
        if not normalized["arxiv_id"]:
            raise ValueError("`arxiv_id` is required.")
        with self._manifest_lock:
            payload = self.load_manifest(quest_root)
            items = [dict(existing) for existing in (payload.get("items") or []) if isinstance(existing, dict)]
            updated = False
            for index, existing in enumerate(items):
                if str(existing.get("arxiv_id") or "").strip() != normalized["arxiv_id"]:
                    continue
                merged = {**existing, **normalized, "updated_at": utc_now()}
                if not existing.get("created_at"):
                    merged["created_at"] = normalized["created_at"]
                items[index] = merged
                updated = True
                break
            if not updated:
                items.append({**normalized, "created_at": utc_now(), "updated_at": utc_now()})
            payload["items"] = items
            self.save_manifest(quest_root, payload)
        return self.get_item(quest_root, normalized["arxiv_id"]) or normalized

    def mark_processing(self, quest_root: Path, arxiv_id: str, *, display_name: str | None = None) -> dict[str, Any]:
        normalized_id = normalize_arxiv_id(arxiv_id)
        if not normalized_id:
            raise ValueError("Invalid arXiv id.")
        current = self.get_item(quest_root, normalized_id) or {}
        return self.upsert_item(
            quest_root,
            {
                **current,
                "arxiv_id": normalized_id,
                "display_name": display_name or current.get("display_name") or normalized_id,
                "status": "processing",
                "pdf_rel_path": self.pdf_relative_path(normalized_id),
                "error": None,
            },
        )

    def mark_failed(self, quest_root: Path, arxiv_id: str, *, error: str) -> dict[str, Any]:
        normalized_id = normalize_arxiv_id(arxiv_id)
        if not normalized_id:
            raise ValueError("Invalid arXiv id.")
        current = self.get_item(quest_root, normalized_id) or {}
        return self.upsert_item(
            quest_root,
            {
                **current,
                "arxiv_id": normalized_id,
                "status": "failed",
                "error": error,
                "pdf_rel_path": current.get("pdf_rel_path") or self.pdf_relative_path(normalized_id),
            },
        )

    def mark_ready(self, quest_root: Path, arxiv_id: str) -> dict[str, Any]:
        normalized_id = normalize_arxiv_id(arxiv_id)
        if not normalized_id:
            raise ValueError("Invalid arXiv id.")
        current = self.get_item(quest_root, normalized_id) or {}
        return self.upsert_item(
            quest_root,
            {
                **current,
                "arxiv_id": normalized_id,
                "status": "ready",
                "error": None,
                "pdf_rel_path": current.get("pdf_rel_path") or self.pdf_relative_path(normalized_id),
            },
        )

    def _materialize_item(self, quest_root: Path, item: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_item(item)
        arxiv_id = normalized["arxiv_id"]
        pdf_rel_path = normalized.get("pdf_rel_path") or self.pdf_relative_path(arxiv_id)
        normalized["pdf_rel_path"] = pdf_rel_path
        pdf_path = quest_root / pdf_rel_path
        if pdf_path.exists() and pdf_path.is_file():
            relative = pdf_path.relative_to(quest_root).as_posix()
            normalized["path"] = relative
            normalized["document_id"] = f"questpath::{relative}"
        else:
            normalized["path"] = None
            normalized["document_id"] = None
        return normalized

    def queue_pdf_download(self, quest_root: Path, arxiv_id: str, *, pdf_url: str | None = None) -> bool:
        normalized_id = normalize_arxiv_id(arxiv_id)
        if not normalized_id:
            return False
        target_path = self.pdf_path(quest_root, normalized_id)
        if target_path.exists() and target_path.is_file():
            self.mark_ready(quest_root, normalized_id)
            return False
        target_url = str(pdf_url or "").strip() or f"https://arxiv.org/pdf/{normalized_id}.pdf"
        inflight_key = (str(quest_root.resolve()), normalized_id)
        with self._download_lock:
            if inflight_key in self._inflight_downloads:
                return False
            self._inflight_downloads.add(inflight_key)

        thread = threading.Thread(
            target=self._download_pdf_worker,
            kwargs={
                "quest_root": quest_root,
                "arxiv_id": normalized_id,
                "pdf_url": target_url,
                "inflight_key": inflight_key,
            },
            name=f"deepscientist-arxiv-{normalized_id}",
        )
        thread.start()
        return True

    def _download_pdf_worker(
        self,
        *,
        quest_root: Path,
        arxiv_id: str,
        pdf_url: str,
        inflight_key: tuple[str, str],
    ) -> None:
        try:
            ensure_dir(self._pdf_dir(quest_root))
            target_path = self.pdf_path(quest_root, arxiv_id)
            request = Request(
                pdf_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/pdf,*/*;q=0.8",
                },
            )
            with urlopen(request, timeout=20) as response:  # noqa: S310
                payload = response.read()
            if not payload.startswith(b"%PDF"):
                raise ValueError("Downloaded payload is not a PDF.")
            temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
            temp_path.write_bytes(payload)
            temp_path.replace(target_path)
            self.mark_ready(quest_root, arxiv_id)
        except Exception as exc:  # noqa: BLE001
            self.mark_failed(quest_root, arxiv_id, error=str(exc).strip() or "download_failed")
        finally:
            with self._download_lock:
                self._inflight_downloads.discard(inflight_key)
