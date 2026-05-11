from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .service import ArtifactService

__all__ = ["ArtifactService"]


def __getattr__(name: str):
    if name == "ArtifactService":
        from .service import ArtifactService

        return ArtifactService
    raise AttributeError(name)
