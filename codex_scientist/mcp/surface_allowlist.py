"""P4 agent-facing surface and hidden CLI allowlist checks."""
from __future__ import annotations

import re
from pathlib import Path


def _literal(*parts: str) -> str:
    return "".join(parts)


_FORBIDDEN_AGENT_FACING_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (_literal("scripts/", "cs", "ctl.py"), re.compile(re.escape(_literal("scripts/", "cs", "ctl.py")), re.IGNORECASE)),
    (_literal("CLI ", "fallback"), re.compile(re.escape(_literal("CLI ", "fallback")), re.IGNORECASE)),
    (_literal("cs", "ctl services"), re.compile(re.escape(_literal("cs", "ctl services")), re.IGNORECASE)),
    (_literal("current ", "cs", "ctl surface"), re.compile(re.escape(_literal("current ", "cs", "ctl surface")), re.IGNORECASE)),
    (_literal("cs", "ctl"), re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(_literal("cs", "ctl")) + r"(?![A-Za-z0-9_-])", re.IGNORECASE)),
)
FORBIDDEN_AGENT_FACING_TERMS = tuple(label for label, _pattern in _FORBIDDEN_AGENT_FACING_PATTERNS)

_AGENT_FACING_FILES = (
    ".codex-plugin/plugin.json",
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


def _agent_facing_skill_paths(root: Path) -> list[Path]:
    skills_root = root / "skills"
    if not skills_root.exists():
        return []
    return sorted(skills_root.glob("**/SKILL.md"))


def agent_facing_paths(root: Path) -> list[Path]:
    """Return default P4 agent-facing files that must not advertise hidden CLI commands."""
    paths = [root / rel for rel in _AGENT_FACING_FILES if (root / rel).exists()]
    paths.extend(_agent_facing_skill_paths(root))
    return sorted(dict.fromkeys(paths))


def allowed_cli_reference_paths() -> tuple[Path, ...]:
    """Return repo-relative paths where hidden admin/debug CLI references may remain."""
    return tuple(Path(rel) for rel in _ALLOWED_CLI_REFERENCE_PATHS)


def find_agent_facing_cli_terms(text: str) -> list[str]:
    """Return forbidden hidden-CLI terms present in agent-facing text."""
    hits: list[str] = []
    for label, pattern in _FORBIDDEN_AGENT_FACING_PATTERNS:
        if pattern.search(text) and label not in hits:
            hits.append(label)
    return hits


def find_agent_facing_cli_violations(root: Path) -> list[dict[str, object]]:
    """Find forbidden hidden-CLI command guidance in default agent-facing files."""
    violations: list[dict[str, object]] = []
    for path in agent_facing_paths(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(root)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for term in find_agent_facing_cli_terms(line):
                violations.append({"path": str(rel), "line": line_no, "term": term, "content": line.strip()})
    return violations
