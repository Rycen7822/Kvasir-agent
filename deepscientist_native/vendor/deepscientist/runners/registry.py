from __future__ import annotations

import re
from typing import Callable


RunnerFactory = Callable[..., object]
_RUNNER_FACTORIES: dict[str, RunnerFactory] = {}
_RUNNER_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _normalize_runner_name(name: str) -> str:
    normalized = str(name or "").strip().lower()
    if not normalized or not _RUNNER_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Runner name must match `^[a-z0-9][a-z0-9_-]*$`."
        )
    return normalized


def register_runner(name: str, factory: RunnerFactory) -> None:
    _RUNNER_FACTORIES[_normalize_runner_name(name)] = factory


def get_runner_factory(name: str) -> RunnerFactory:
    normalized = _normalize_runner_name(name)
    try:
        return _RUNNER_FACTORIES[normalized]
    except KeyError as exc:
        available = ", ".join(sorted(_RUNNER_FACTORIES)) or "none"
        raise KeyError(f"Unknown runner `{normalized}`. Available runners: {available}.") from exc


def list_runner_names() -> list[str]:
    return sorted(_RUNNER_FACTORIES)
