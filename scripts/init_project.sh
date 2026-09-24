#!/usr/bin/env bash
# Explicit terminal compatibility wrapper; creates no model instructions.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -ne 1 || "$1" != /* ]]; then
  printf 'Usage: %s /absolute/existing/project\n' "$0" >&2
  exit 2
fi
PYTHONDONTWRITEBYTECODE=1 exec python3 "$ROOT/scripts/ka_admin.py" init --project "$1"
