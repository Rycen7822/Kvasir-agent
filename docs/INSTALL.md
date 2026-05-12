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
5. Runs `scripts/doctor.py`.

For normal Codex use, leave `CODEX_HOME` and `AGENTS_HOME` unset so the standard `~/.codex` / `~/.agents` locations are used.

## MCP registration snippet

Register the curated local MCP by pointing the client at:

```bash
python /path/to/CodexScientist-codex/scripts/cs_mcp.py
```

A typical config entry should use stdio transport and should not contain secrets. The server reads only local project files and exposes curated `cs_*` tools.

Smoke test the entrypoint:

```bash
python scripts/cs_mcp.py --stdio-smoke initialize
python scripts/cs_mcp.py --stdio-smoke tools/list
python scripts/cs_mcp.py --stdio-smoke call cs_doctor '{}'
```

## hidden admin/debug CLI

Use hidden admin/debug CLI for CI, debugging, migration, recovery, and MCP-unavailable environments:

```bash
See `docs/ADMIN_CLI.md` for human/admin/debug/CI/recovery commands.
```

Runtime state will live in:

```text
/path/to/project/CodexScientist/
```

## Uninstall

Remove the plugin directory and the config entries if desired:

```bash
rm -rf ~/.codex/plugins/codexscientist-codex
```

Then remove `[plugins."codexscientist-codex@local-personal"]` from `~/.codex/config.toml` and the `codexscientist-codex` entry from `~/.agents/plugins/marketplace.json`.
