# Install

Requires Linux (process identity and file locks), Python 3.10+, PyYAML, jsonschema and a Codex CLI with plugin support. Install Python dependencies into the interpreter used by the bundled `python3` MCP entrypoint.

Register this repository through a Codex plugin marketplace and install its exact marketplace reference:

```sh
bash scripts/install.sh kvasir-agent@your-marketplace
codex plugin list
```

The wrapper delegates to `codex plugin add` and preserves errors. Open a fresh thread after changing the installation. The plugin manifest registers `./skills` and `./.mcp.json`. Expected discovery is five research tools and one `kvasir-agent` skill; project paths must be supplied explicitly.

For updates to a local source, refresh the plugin cache version and reinstall from the registered marketplace. Verify the installed source/cache identity, not only the source checkout. A source-level test does not prove host discovery.

Project creation is a separate, user-triggered action:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 /absolute/plugin/path/scripts/ka_admin.py init --project /absolute/existing/project
```

This creates minimal state and no Codex instructions. The independent `manual/init/SKILL.md` is packaged but not registered or auto-discovered. Its name, description, path and body are absent from ordinary model startup context. Users may execute the terminal command directly, or explicitly supply the manual path in a separate conversation. See [ADMIN_CLI.md](ADMIN_CLI.md) for legacy migration and maintenance.
