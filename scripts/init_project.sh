#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="${1:-$(pwd)}"
mkdir -p "${PROJECT}/.codex"
cat > "${PROJECT}/.codex/KVASIR_AGENT_CODEX.md" <<EOF
# Kvasir-agent Codex MCP Project Note

Use this project with the Kvasir-agent Codex MCP control plane.

- Runtime home: ${PROJECT}/Kvasir-agent
- MCP server entrypoint: ${ROOT}/scripts/ka_mcp.py
- Routine file, shell, Git, test, build, and process work remains Codex-native.
- Use Kvasir-agent MCP \`ka_*\` tools only for durable research semantics: quest state, requirements, memory, artifacts, baselines, experiments, analysis, paper/reliability, checkpoint, resume, and formal evidence provenance.
- Bundled support skills include kvasir-agent-experiment, kvasir-agent-quest-handoffs, kvasir-agent-write, ka-paper-reliability, kvasir-agent-strict-research, and kvasir-agent-figure-polish.

MCP smoke checks:

\`\`\`bash
cd "${PROJECT}"
python "${ROOT}/scripts/ka_mcp.py" --stdio-smoke initialize
python "${ROOT}/scripts/ka_mcp.py" --stdio-smoke tools/list
python "${ROOT}/scripts/ka_mcp.py" --stdio-smoke call ka_doctor '{"project":"${PROJECT}"}'
\`\`\`

If Codex cannot see the tools, verify the MCP registration:

\`\`\`bash
codex plugin list
\`\`\`
EOF
PYTHONDONTWRITEBYTECODE=1 python "${ROOT}/scripts/ka_mcp.py" --stdio-smoke initialize >/dev/null
printf 'Initialized Kvasir-agent Codex MCP note in %s/.codex/KVASIR_AGENT_CODEX.md\n' "${PROJECT}"
