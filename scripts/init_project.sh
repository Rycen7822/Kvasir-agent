#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="${1:-$(pwd)}"
mkdir -p "${PROJECT}/.codex"
cat > "${PROJECT}/.codex/DEEPSCIENTIST_CODEX.md" <<EOF
# DeepScientist Codex Native

Use this project with the DeepScientist Codex native adapter.

- Runtime home: ${PROJECT}/DeepScientist
- Native control script: ${ROOT}/scripts/dsctl.py
- No MCP transport is used.
- Do not call the external npm ds command for normal work.
- Bundled support skills include deepscientist-experiment-execution, deepscientist-quest-handoffs, deepscientist-writing-plans, deepscientist-paper-reliability-verification, and deepscientist-review.

Smoke check:

\`\`\`bash
cd "${PROJECT}"
python "${ROOT}/scripts/dsctl.py" doctor --format json
\`\`\`
EOF
python "${ROOT}/scripts/dsctl.py" --project-root "${PROJECT}" doctor --format json >/dev/null
printf 'Initialized DeepScientist Codex note in %s/.codex/DEEPSCIENTIST_CODEX.md\n' "${PROJECT}"
