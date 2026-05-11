"""Codex-native DeepScientist adapter package.

This package embeds the retained headless DeepScientist runtime and exposes it
through scripts/dsctl.py for Codex CLI. It does not use MCP and does not invoke
the external npm ds command for normal operation.
"""

__all__ = ["schemas", "tools", "runtime", "config", "state"]
