"""Codex-native Kvasir-agent adapter package.

This package embeds the retained headless Kvasir-agent runtime and exposes it
through scripts/kactl.py for Codex CLI. It does not use MCP and does not invoke
the upstream CLI for normal operation.
"""

__all__ = ["schemas", "tools", "runtime", "config", "state"]
