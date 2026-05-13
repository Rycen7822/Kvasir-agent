# Install CodexScientist

CodexScientist installs as a Codex CLI plugin with a stable curated MCP entrypoint and a hidden admin/debug CLI.

## Local install

From `CodexScientist-codex`:

```bash
bash scripts/install.sh
```

The installer:

1. Copies this plugin to `~/.codex/plugins/codexscientist-codex`.
2. If that directory already exists, moves it aside as `~/.codex/plugins/codexscientist-codex.backup-<timestamp>` before copying the new version.
3. Registers a local marketplace entry in `~/.agents/plugins/marketplace.json`.
4. Enables `[plugins."codexscientist-codex@local-personal"]` in `~/.codex/config.toml`.
5. Registers `[mcp_servers.codexscientist-codex]` in `~/.codex/config.toml` so Codex can launch `scripts/cs_mcp.py` by stdio.
6. Runs `scripts/doctor.py` without leaving `__pycache__` or `*.pyc` files in a copied install tree.

For normal Codex use, leave `CODEX_HOME` and `AGENTS_HOME` unset so the standard `~/.codex` / `~/.agents` locations are used.

## Codex MCP registration

The installer writes the MCP server entry automatically. To register the same entry manually, point Codex at the stdio launcher:

```bash
codex mcp add codexscientist-codex -- python /path/to/CodexScientist-codex/scripts/cs_mcp.py
```

A typical config entry should use stdio transport and should not contain secrets. The server reads only local project files and exposes curated `cs_*` tools.

Smoke test the entrypoint:

```bash
python scripts/cs_mcp.py --stdio-smoke initialize
python scripts/cs_mcp.py --stdio-smoke tools/list
python scripts/cs_mcp.py --stdio-smoke tools/list '{"profile":"evidence"}'
python scripts/cs_mcp.py --stdio-smoke call cs_doctor '{}'
```

## Hidden admin/debug CLI

Use hidden admin/debug CLI for CI, debugging, migration, recovery, and MCP-unavailable environments. See `docs/ADMIN_CLI.md` for human/admin/debug/CI/recovery commands.

Runtime state will live in:

```text
/path/to/project/CodexScientist/
```

## Uninstall

Remove the plugin directory and the config entries if desired:

```bash
rm -rf ~/.codex/plugins/codexscientist-codex
```

Then remove `[plugins."codexscientist-codex@local-personal"]` and `[mcp_servers.codexscientist-codex]` from `~/.codex/config.toml`, and remove the `codexscientist-codex` entry from `~/.agents/plugins/marketplace.json`.
