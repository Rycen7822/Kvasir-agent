"""Codex-native CodexScientist adapter package.

This package embeds the retained headless CodexScientist runtime and exposes it
through scripts/csctl.py for Codex CLI. It does not use MCP and does not invoke
the external npm cs command for normal operation.
"""

__all__ = ["schemas", "tools", "runtime", "config", "state"]
