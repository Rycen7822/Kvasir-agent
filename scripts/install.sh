#!/usr/bin/env bash
set -euo pipefail

PLUGIN_NAME="deepscientist-codex"
# Default install path: ~/.codex/plugins/deepscientist-codex
SOURCE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
INSTALL_DIR="${CODEX_HOME}/plugins/${PLUGIN_NAME}"
AGENTS_HOME="${AGENTS_HOME:-${HOME}/.agents}"
MARKETPLACE_FILE="${AGENTS_HOME}/plugins/marketplace.json"
CONFIG_FILE="${CODEX_HOME}/config.toml"

log() { printf '[DeepScientist-codex] %s\n' "$*"; }
fail() { printf '[DeepScientist-codex] ERROR: %s\n' "$*" >&2; exit 1; }

[ -f "${SOURCE_ROOT}/.codex-plugin/plugin.json" ] || fail "Run install.sh from a complete DeepScientist-codex source tree."
if grep -R "mcp""Servers" -n "${SOURCE_ROOT}/.codex-plugin" >/dev/null 2>&1; then
  fail "MCP server registration is forbidden for this native adapter."
fi

mkdir -p "$(dirname -- "${INSTALL_DIR}")"
if [ "${SOURCE_ROOT}" != "${INSTALL_DIR}" ]; then
  if [ -e "${INSTALL_DIR}" ]; then
    BACKUP="${INSTALL_DIR}.backup-$(date +%Y%m%d%H%M%S)"
    log "Backing up existing plugin to ${BACKUP}"
    mv "${INSTALL_DIR}" "${BACKUP}"
  fi
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude '.git/' \
      --exclude '__pycache__/' \
      --exclude '.pytest_cache/' \
      --exclude '*.pyc' \
      "${SOURCE_ROOT}/" "${INSTALL_DIR}/"
  else
    cp -a "${SOURCE_ROOT}" "${INSTALL_DIR}"
  fi
else
  log "Source is already installed at ${INSTALL_DIR}"
fi

[ -f "${INSTALL_DIR}/.codex-plugin/plugin.json" ] || fail "Installed plugin is missing .codex-plugin/plugin.json"
[ ! -f "${INSTALL_DIR}/.mcp.json" ] || fail "Installed plugin unexpectedly contains .mcp.json"

mkdir -p "$(dirname -- "${MARKETPLACE_FILE}")"
python3 - "${MARKETPLACE_FILE}" <<'PY'
from pathlib import Path
import json, sys
path = Path(sys.argv[1])
entry = {
    "name": "deepscientist-codex",
    "source": {"source": "local", "path": "./.codex/plugins/deepscientist-codex"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Productivity",
}
if path.exists():
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {}
else:
    data = {}
data.setdefault("name", "local-personal")
data.setdefault("interface", {"displayName": "Local Personal Plugins"})
plugins = [p for p in data.get("plugins", []) if p.get("name") != entry["name"]]
plugins.append(entry)
data["plugins"] = plugins
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

mkdir -p "$(dirname -- "${CONFIG_FILE}")"
python3 - "${CONFIG_FILE}" <<'PY'
from pathlib import Path
import re, sys
path = Path(sys.argv[1])
section = '[plugins."deepscientist-codex@local-personal"]'
enabled = 'enabled = true\n'
if not path.exists():
    path.write_text(section + '\n' + enabled, encoding='utf-8')
    raise SystemExit(0)
lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
out = []
found = False
in_section = False
wrote = False
for line in lines:
    stripped = line.strip()
    if stripped == section:
        found = True
        in_section = True
        wrote = False
        out.append(line)
        continue
    if in_section and stripped.startswith('[') and stripped.endswith(']'):
        if not wrote:
            out.append(enabled)
            wrote = True
        in_section = False
    if in_section and re.match(r'^enabled\s*=', stripped):
        out.append(enabled)
        wrote = True
        continue
    out.append(line)
if in_section and not wrote:
    out.append(enabled)
if not found:
    if out and out[-1].strip():
        out.append('\n')
    out.extend([section + '\n', enabled])
path.write_text(''.join(out), encoding='utf-8')
PY

python3 "${INSTALL_DIR}/scripts/doctor.py" >/dev/null
log "Installed ${PLUGIN_NAME} to ${INSTALL_DIR}"
log "Registered marketplace: ${MARKETPLACE_FILE}"
log "Enabled [plugins.\"deepscientist-codex@local-personal\"] in ${CONFIG_FILE}"
log "Use from a research project root: python ${INSTALL_DIR}/scripts/dsctl.py doctor --format json"
