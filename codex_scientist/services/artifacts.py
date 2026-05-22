from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from codex_scientist.runtime.redaction import redact_payload

from .project_state import ProjectLayout


_ARTIFACT_DIR_NAMES = ("artifacts", "results")
_IGNORED_SUFFIXES = {".tmp", ".lock"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_type(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "file"


class ArtifactIndexService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout

    def _roots(self) -> list[Path]:
        return [self.layout.state_root / name for name in _ARTIFACT_DIR_NAMES]

    def _quest_roots(self, quest_id: str) -> list[Path]:
        quest_root = self.layout.quest_root_for(quest_id)
        return [quest_root / "artifacts", quest_root / "results"]

    def index(self, *, max_items: int = 50, quest_id: str | None = None) -> dict[str, Any]:
        max_items = max(1, min(int(max_items), 500))
        artifacts: list[dict[str, Any]] = []
        total_count = 0
        artifact_record_count = 0
        saw_more = False
        roots = self._quest_roots(quest_id) if quest_id else self._roots()
        relative_base = self.layout.quest_root_for(quest_id) if quest_id else self.layout.state_root
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.suffix.lower() in _IGNORED_SUFFIXES:
                    continue
                total_count += 1
                if path.suffix.lower() == ".json":
                    artifact_record_count += 1
                if len(artifacts) >= max_items:
                    saw_more = True
                    continue
                stat = path.stat()
                try:
                    relative_path = str(path.relative_to(relative_base))
                except ValueError:
                    relative_path = str(path)
                artifacts.append(
                    {
                        "path": str(path),
                        "relative_path": relative_path,
                        "type": _artifact_type(path),
                        "bytes": stat.st_size,
                        "sha256": _sha256_file(path),
                        "updated_at": int(stat.st_mtime),
                    }
                )
        payload = {
            "ok": True,
            "project": str(self.layout.project_root),
            "state_root": str(self.layout.state_root),
            "scope": "quest" if quest_id else "project",
            "quest_id": quest_id,
            "count": len(artifacts),
            "total_count": total_count,
            "quest_artifact_count": artifact_record_count if quest_id else None,
            "artifact_file_count": total_count,
            "artifacts": artifacts,
            "truncated": saw_more,
        }
        return redact_payload(payload)
