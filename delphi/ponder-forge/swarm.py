"""Dispatch size only; team composition belongs to the coordinator."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class SwarmBudget:
    delegate_batch_size: int = 20

    def as_dict(self) -> dict:
        return {"delegate_batch_size": self.delegate_batch_size}


def normalize_swarm_budget(raw: dict | None = None) -> SwarmBudget:
    raw = {} if raw is None else raw
    if not isinstance(raw, dict):
        raise ValueError("budget must be an object")
    unknown = set(raw) - {"delegate_batch_size"}
    if unknown:
        raise ValueError(f"unknown or retired budget key: {sorted(unknown)[0]}")
    value = raw.get("delegate_batch_size", 20)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 20:
        raise ValueError("delegate_batch_size must be an integer between 1 and 20")
    return SwarmBudget(value)
