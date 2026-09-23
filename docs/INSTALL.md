# Install Kvasir-agent

Kvasir-agent installs as a Codex CLI plugin with a stable curated MCP entrypoint and a hidden admin/debug CLI.

## Local install

From `Kvasir-agent`:

```bash
bash scripts/install.sh
```

The installer:

1. Copies this plugin to `~/.codex/plugins/kvasir-agent`.
2. If that directory already exists, moves it aside as `~/.codex/plugins/kvasir-agent.backup-<timestamp>` before copying the new version.
3. Registers a local marketplace entry in `~/.agents/plugins/marketplace.json`.
4. Enables `[plugins."kvasir-agent@local-personal"]` in `~/.codex/config.toml`.
5. Registers `[mcp_servers.kvasir-agent]` in `~/.codex/config.toml` so Codex can launch `scripts/ka_mcp.py` by stdio.
6. Runs `scripts/doctor.py` without leaving `__pycache__` or `*.pyc` files in a copied install tree.

For normal Codex use, leave `CODEX_HOME` and `AGENTS_HOME` unset so the standard `~/.codex` / `~/.agents` locations are used.

## Codex MCP registration

The installer writes the MCP server entry automatically. To register the same entry manually, point Codex at the stdio launcher:

```bash
codex mcp add kvasir-agent -- python -B /path/to/Kvasir-agent/scripts/ka_mcp.py
```

A typical config entry should use stdio transport and should not contain secrets. The server reads only local project files and exposes curated `ka_*` tools.

Smoke test the entrypoint:

```bash
python scripts/ka_mcp.py --stdio-smoke initialize
python scripts/ka_mcp.py --stdio-smoke tools/list
python scripts/ka_mcp.py --stdio-smoke tools/list '{"profile":"evidence"}'
python scripts/ka_mcp.py --stdio-smoke call ka_doctor '{}'
```

## Advanced admin/debug CLI

Advanced admin/debug CLI commands are documented separately for CI, debugging, migration, recovery, and MCP-unavailable environments. Normal Codex users should stay on the public MCP path above; see `docs/ADMIN_CLI.md` only for human/admin/debug/CI/recovery commands.

Runtime state will live in:

```text
/path/to/project/Kvasir-agent/
```

If an existing research project stores state in `/path/to/project/CodexScientist/`, back it up and rename that directory to `Kvasir-agent/` before using this version. Rename any nested `.cs/` runtime directories to `.ka/` as well. The installer does not move project data. The previous `codexscientist-codex` plugin installation and config entries also remain until you remove them.

## Uninstall

Remove the plugin directory and the config entries if desired:

```bash
rm -rf ~/.codex/plugins/kvasir-agent
```

Then remove `[plugins."kvasir-agent@local-personal"]` and `[mcp_servers.kvasir-agent]` from `~/.codex/config.toml`, and remove the `kvasir-agent` entry from `~/.agents/plugins/marketplace.json`.
