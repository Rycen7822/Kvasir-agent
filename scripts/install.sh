#!/usr/bin/env bash
# Install from an existing Codex marketplace; Codex owns cache and configuration.
set -euo pipefail
if [[ $# -ne 1 || "$1" != kvasir-agent@* ]]; then
  printf 'Usage: %s kvasir-agent@<marketplace-name>\nRegister the plugin source in a Codex marketplace first; see docs/INSTALL.md.\n' "$0" >&2
  exit 2
fi
command -v codex >/dev/null
codex plugin add "$1"
printf 'Open a new Codex thread to load the bundled MCP server and skills.\n'
