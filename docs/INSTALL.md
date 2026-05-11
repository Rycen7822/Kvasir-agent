# Install DeepScientist Codex Native

This adapter is installed as a native Codex CLI plugin. It is not MCP. After install, `scripts/dsctl.py list-tools --format json` should report the Codex-native manifest with `transport="codex-native-cli"`, `mcp=false`, and the current 48-tool public canonical `ds_*` business surface, including the original Hermes MCP event/convenience/introspection equivalents such as `ds_events`. Legacy `deepscientist_*` aliases are hidden from the public manifest and kept only for compatibility calls.

## Local install

From `DeepScientist-codex`:

```bash
bash scripts/install.sh
```

The installer:

1. Copies this plugin to `~/.codex/plugins/deepscientist-codex`.
2. If that directory already exists, moves it aside as `~/.codex/plugins/deepscientist-codex.backup-<timestamp>` before copying the new version.
3. Registers a local marketplace entry in `~/.agents/plugins/marketplace.json`.
4. Enables `[plugins."deepscientist-codex@local-personal"]` in `~/.codex/config.toml`.
5. Runs `scripts/doctor.py`.

For normal Codex use, leave `CODEX_HOME` and `AGENTS_HOME` unset so the standard `~/.codex` / `~/.agents` locations are used. The installer honors those variables for isolated smoke tests or deliberate non-default installs, but the default local-personal marketplace layout is the supported user path.

It does not create `.mcp.json`, does not add a server-transport registry field, and does not call external ds for normal work.

The installed Codex plugin also includes DeepScientist-specific support skills: `deepscientist-experiment-execution`, `deepscientist-quest-handoffs`, `deepscientist-writing-plans`, `deepscientist-paper-reliability-verification`, and `deepscientist-review`. These are native Codex skill resources; durable state still goes through `scripts/dsctl.py call ds_* ... --format json`.

The installer also does not copy or start the original FastMCP server. Original DeepScientist Hermes MCP capabilities are reached through Codex-native wrappers such as `ds_events`, `ds_memory_list_recent`, `ds_resolve_runtime_refs`, `ds_get_global_status`, `ds_get_method_scoreboard`, `ds_get_optimization_frontier`, `ds_get_conversation_context`, `ds_get_paper_contract_health`, `ds_list_paper_outlines`, `ds_refresh_summary`, `ds_arxiv`, and `ds_bash_exec`.

## Project initialization note

After install, from a research project root:

```bash
bash ~/.codex/plugins/deepscientist-codex/scripts/init_project.sh /path/to/project
python ~/.codex/plugins/deepscientist-codex/scripts/dsctl.py --project-root /path/to/project doctor --format json
```

Runtime state will live in:

```text
/path/to/project/DeepScientist/
```

## Uninstall

Remove the plugin directory and the config entries if desired:

```bash
rm -rf ~/.codex/plugins/deepscientist-codex
```

Then remove `[plugins."deepscientist-codex@local-personal"]` from `~/.codex/config.toml` and the `deepscientist-codex` entry from `~/.agents/plugins/marketplace.json`.
