#!/usr/bin/env bash
set -euo pipefail

PLUGIN_NAME="codexscientist-codex"
# Default install path: ~/.codex/plugins/codexscientist-codex
SOURCE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
INSTALL_DIR="${CODEX_HOME}/plugins/${PLUGIN_NAME}"
AGENTS_HOME="${AGENTS_HOME:-${HOME}/.agents}"
MARKETPLACE_FILE="${AGENTS_HOME}/plugins/marketplace.json"
CONFIG_FILE="${CODEX_HOME}/config.toml"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python || true)}"

log() { printf '[CodexScientist-codex] %s\n' "$*"; }
fail() { printf '[CodexScientist-codex] ERROR: %s\n' "$*" >&2; exit 1; }
[ -n "${PYTHON_BIN}" ] || fail "python3 or python is required for CodexScientist MCP registration."

[ -f "${SOURCE_ROOT}/.codex-plugin/plugin.json" ] || fail "Run install.sh from a complete CodexScientist-codex source tree."
if grep -R "mcp""Servers" -n "${SOURCE_ROOT}/.codex-plugin" >/dev/null 2>&1; then
  fail "plugin.json should not inline MCP server registrations; use scripts/cs_mcp.py as the stable stdio entrypoint."
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
"${PYTHON_BIN}" - "${MARKETPLACE_FILE}" "${INSTALL_DIR}" "${CODEX_HOME}" "${HOME}" <<'PY'
from pathlib import Path
import json, sys
path = Path(sys.argv[1])
install_dir = Path(sys.argv[2]).resolve()
codex_home = Path(sys.argv[3]).expanduser().resolve()
home = Path(sys.argv[4]).expanduser().resolve()
def source_path() -> str:
    default_codex_home = home / ".codex"
    if codex_home == default_codex_home:
        return "./.codex/plugins/codexscientist-codex"
    return str(install_dir)
entry = {
    "name": "codexscientist-codex",
    "source": {"source": "local", "path": source_path()},
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
"${PYTHON_BIN}" - "${CONFIG_FILE}" <<'PY'
from pathlib import Path
import re, sys
path = Path(sys.argv[1])
section = '[plugins."codexscientist-codex@local-personal"]'
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

"${PYTHON_BIN}" - "${CONFIG_FILE}" "${INSTALL_DIR}/scripts/cs_mcp.py" "${PYTHON_BIN}" <<'PY'
from pathlib import Path
import json
import sys

path = Path(sys.argv[1])
mcp_entry = Path(sys.argv[2])
python_bin = sys.argv[3]
section = '[mcp_servers.codexscientist-codex]'
body = [
    f'command = {json.dumps(python_bin)}\n',
    f'args = ["-B", {json.dumps(str(mcp_entry))}]\n',
]
text = path.read_text(encoding='utf-8') if path.exists() else ''
lines = text.splitlines(keepends=True)
out: list[str] = []
i = 0
found = False
while i < len(lines):
    if lines[i].strip() == section:
        found = True
        out.append(section + '\n')
        out.extend(body)
        i += 1
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                break
            i += 1
        continue
    out.append(lines[i])
    i += 1
if not found:
    if out and out[-1].strip():
        out.append('\n')
    out.append(section + '\n')
    out.extend(body)
path.write_text(''.join(out), encoding='utf-8')
PY

PYTHONDONTWRITEBYTECODE=1 "${PYTHON_BIN}" "${INSTALL_DIR}/scripts/doctor.py" >/dev/null
if [ "${SOURCE_ROOT}" != "${INSTALL_DIR}" ]; then
  find "${INSTALL_DIR}" -type d \( -name '.git' -o -name '.pytest_cache' -o -name '__pycache__' \) -prune -exec rm -rf {} +
  find "${INSTALL_DIR}" -type f -name '*.pyc' -delete
fi
log "Installed ${PLUGIN_NAME} to ${INSTALL_DIR}"
log "Registered marketplace: ${MARKETPLACE_FILE}"
log "Enabled [plugins.\"codexscientist-codex@local-personal\"] in ${CONFIG_FILE}"
log "Registered MCP server [mcp_servers.codexscientist-codex] in ${CONFIG_FILE}"
log "Verify with: codex mcp list && codex mcp get codexscientist-codex"
log "Smoke test: ${PYTHON_BIN} -B ${INSTALL_DIR}/scripts/cs_mcp.py --stdio-smoke call cs_doctor '{}'"
