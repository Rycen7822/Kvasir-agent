#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="${1:-$(pwd)}"
mkdir -p "${PROJECT}/.codex"
cat > "${PROJECT}/.codex/CODEXSCIENTIST_CODEX.md" <<EOF
# CodexScientist Codex MCP Project Note

Use this project with the CodexScientist Codex MCP control plane.

- Runtime home: ${PROJECT}/CodexScientist
- MCP server entrypoint: ${ROOT}/scripts/cs_mcp.py
- Routine file, shell, Git, test, build, and process work remains Codex-native.
- Use CodexScientist MCP \`cs_*\` tools only for durable research semantics: quest state, requirements, memory, artifacts, baselines, experiments, analysis, paper/reliability, checkpoint, resume, and formal evidence provenance.
- Bundled support skills include codexscientist-experiment-execution, codexscientist-quest-handoffs, codexscientist-writing-plans, cs-paper-reliability, and codexscientist-review.

MCP smoke checks:

\`\`\`bash
cd "${PROJECT}"
python "${ROOT}/scripts/cs_mcp.py" --stdio-smoke initialize
python "${ROOT}/scripts/cs_mcp.py" --stdio-smoke tools/list
python "${ROOT}/scripts/cs_mcp.py" --stdio-smoke call cs_doctor '{"project":"${PROJECT}"}'
\`\`\`

If Codex cannot see the tools, verify the MCP registration:

\`\`\`bash
codex mcp list
codex mcp get codexscientist-codex
\`\`\`
EOF
PYTHONDONTWRITEBYTECODE=1 python "${ROOT}/scripts/cs_mcp.py" --stdio-smoke initialize >/dev/null
printf 'Initialized CodexScientist Codex MCP note in %s/.codex/CODEXSCIENTIST_CODEX.md\n' "${PROJECT}"
