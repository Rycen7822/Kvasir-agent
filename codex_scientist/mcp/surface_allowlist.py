"""P4 agent-facing surface and hidden CLI allowlist checks."""
from __future__ import annotations

from pathlib import Path

FORBIDDEN_AGENT_FACING_TERMS = ("scripts/csctl.py", "CLI fallback")

_AGENT_FACING_FILES = (
    ".codex-plugin/plugin.json",
    "skills/codexscientist-codex/SKILL.md",
    "docs/ARCHITECTURE.md",
    "docs/REPOSITORY_LAYOUT.md",
    "docs/USAGE.md",
    "docs/INSTALL.md",
    "docs/MCP.md",
    "docs/LONG_RUN.md",
    "codex_scientist/mcp/tool_registry.py",
    "codex_scientist/mcp/skill_index.py",
)

_ALLOWED_CLI_REFERENCE_PATHS = (
    "scripts/csctl.py",
    "scripts/cs_native_cli.py",
    "codex_scientist/adapters/legacy_csctl.py",
    "tests/test_json_output_flag.py",
    "tests/test_csctl_compat.py",
    "tests/test_mcp_cli_parity.py",
    "tests/test_final_acceptance_commands.py",
    "docs/ADMIN_CLI.md",
    "docs/MIGRATION.md",
    ".github/workflows/ci.yml",
)


def agent_facing_paths(root: Path) -> list[Path]:
    """Return the default P4 agent-facing files that must not advertise CLI fallback."""
    return [root / rel for rel in _AGENT_FACING_FILES if (root / rel).exists()]


def allowed_cli_reference_paths() -> tuple[Path, ...]:
    """Return repo-relative paths where hidden admin/debug CLI references may remain."""
    return tuple(Path(rel) for rel in _ALLOWED_CLI_REFERENCE_PATHS)


def find_agent_facing_cli_violations(root: Path) -> list[dict[str, object]]:
    """Find forbidden CLI fallback terms in default agent-facing files."""
    violations: list[dict[str, object]] = []
    for path in agent_facing_paths(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(root)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for term in FORBIDDEN_AGENT_FACING_TERMS:
                if term in line:
                    violations.append({"path": str(rel), "line": line_no, "term": term, "content": line.strip()})
    return violations
