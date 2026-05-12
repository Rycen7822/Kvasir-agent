#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="${1:-$(pwd)}"
mkdir -p "${PROJECT}/.codex"
cat > "${PROJECT}/.codex/CODEXSCIENTIST_CODEX.md" <<EOF
# CodexScientist Codex Native

Use this project with the CodexScientist Codex native adapter.

- Runtime home: ${PROJECT}/CodexScientist
- Native control script: ${ROOT}/scripts/csctl.py
- No MCP transport is used.
- Do not call the external npm cs command for normal work.
- Bundled support skills include codexscientist-experiment-execution, codexscientist-quest-handoffs, codexscientist-writing-plans, codexscientist-paper-reliability-verification, and codexscientist-review.

Smoke check:

\`\`\`bash
cd "${PROJECT}"
python "${ROOT}/scripts/csctl.py" doctor --format json
\`\`\`
EOF
python "${ROOT}/scripts/csctl.py" --project-root "${PROJECT}" doctor --format json >/dev/null
printf 'Initialized CodexScientist Codex note in %s/.codex/CODEXSCIENTIST_CODEX.md\n' "${PROJECT}"
