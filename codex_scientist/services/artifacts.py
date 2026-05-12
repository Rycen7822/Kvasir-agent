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

    def index(self, *, max_items: int = 50) -> dict[str, Any]:
        max_items = max(1, min(int(max_items), 500))
        artifacts: list[dict[str, Any]] = []
        saw_more = False
        for root in self._roots():
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.suffix.lower() in _IGNORED_SUFFIXES:
                    continue
                if len(artifacts) >= max_items:
                    saw_more = True
                    break
                stat = path.stat()
                artifacts.append(
                    {
                        "path": str(path),
                        "relative_path": str(path.relative_to(self.layout.state_root)),
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
            "count": len(artifacts),
            "artifacts": artifacts,
            "truncated": saw_more,
        }
        return redact_payload(payload)
