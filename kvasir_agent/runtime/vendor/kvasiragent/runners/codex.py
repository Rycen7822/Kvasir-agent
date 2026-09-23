from __future__ import annotations

"""Disabled upstream Codex bridge for Kvasir-agent.

The Codex-native adapter uses scripts/kactl.py and direct vendored runtime calls.
The historical bridge/config-injection runner is intentionally unavailable.
"""


class CodexBridgeUnavailable(RuntimeError):
    pass


def __getattr__(name: str):
    raise CodexBridgeUnavailable(
        "The upstream Codex bridge is disabled in Kvasir-agent; use scripts/kactl.py instead."
    )
