#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || "$1" != /* || ! -d "$1" ]]; then
  echo 'Usage: bash scripts/install_pi.sh /absolute/existing/project' >&2
  exit 2
fi
plugin_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="$(command -v python3)"
"$python_bin" -c 'import jsonschema, yaml'
cd -- "$1"
pi mcp add -l kvasir-agent --exposure codemode \
  --description 'Managed research runs and project-local evidence checks.' \
  --cwd "$plugin_dir" --env PYTHONDONTWRITEBYTECODE=1 \
  -- "$python_bin" "$plugin_dir/scripts/ka_mcp.py"
