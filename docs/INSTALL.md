# Install Kvasir-agent

Requires Python 3.10+, PyYAML and jsonschema (`python3 -m pip install -e .` from this source tree) and Codex CLI plugin support. The plugin bundles its stdio MCP configuration in `.mcp.json`.

## Register a source

Use an existing local marketplace when available. For a first personal installation, ask Codex's `plugin-creator` to register this source in `~/.agents/plugins/marketplace.json`. Preserve other entries and the existing marketplace name. The source must point to this plugin directory, containing `.codex-plugin/plugin.json`.

Alternatively, use a separate local marketplace directory with this layout:

```text
marketplace/
  .agents/plugins/marketplace.json
  plugins/kvasir-agent/    # this plugin source
```

Its catalog can contain:

```json
{
  "name": "kvasir-local",
  "plugins": [{
    "name": "kvasir-agent",
    "source": {"source": "local", "path": "./plugins/kvasir-agent"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Productivity"
  }]
}
```

Register that non-default marketplace with `codex plugin marketplace add /path/to/marketplace`. The personal marketplace is discovered automatically and needs no such command.

## Install and verify

Use the actual marketplace name:

```bash
bash scripts/install.sh kvasir-agent@local-personal
codex plugin list
```

The installer calls `codex plugin add`. Codex manages the cache, enablement and bundled MCP server; the script does not edit `config.toml` or register a global server. Open a **new thread** after installation or upgrade. Check that `ka_research_read` and the seven skills are available.

A source-level check is useful but does not prove host discovery:

```bash
python3 scripts/doctor.py
python3 scripts/ka_mcp.py --stdio-smoke initialize
python3 scripts/ka_mcp.py --stdio-smoke tools/list
```

The bundled server launches from its cache directory using `cwd: "."`; pass the absolute research root as `project` on every MCP research call. Missing roots are rejected before writing state. `scripts/init_project.sh /path/to/project` writes an optional project note.

## Updates and migration

Update the plugin source and version/cachebuster, then rerun `codex plugin add kvasir-agent@<marketplace-name>` and open a new thread. Use the plugin-creator update workflow for local cache refreshes.

Older installations registered a standalone `[mcp_servers.kvasir-agent]` in addition to the plugin. After confirming the bundled server works, remove that old global registration with `codex mcp remove kvasir-agent` to avoid duplicate tools. The installer leaves existing registrations and research data untouched.

Existing `<project>/Kvasir-agent/` records remain readable. Old goal-state files are ignored; use `ka_research_read` with `operation="resume"` and Codex's own goals. Context-pack export is retained only for admin/legacy consumers. Retired skill and goal MCP tools should be removed from external callers.

## Uninstall

Use `codex plugin remove kvasir-agent@<marketplace-name>`. Project research records remain in `<project>/Kvasir-agent/`. Hidden admin/debug CLI compatibility is documented in [ADMIN_CLI.md](ADMIN_CLI.md).

The public API now exposes 24 tools. See [tool migration](TOOL_MIGRATION.md) for grouped operations and the canonical project parameter.
