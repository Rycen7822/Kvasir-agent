# Install

Requires Linux (process identity and file locks), Python 3.10+, PyYAML and jsonschema. Install Python dependencies into the interpreter used by the MCP entrypoint. Codex and Pi use the same stdio server and file contracts.

## Codex

Register this repository through a Codex plugin marketplace and install its exact marketplace reference:

```sh
bash scripts/install.sh kvasir-agent@your-marketplace
codex plugin list
```

The wrapper delegates to `codex plugin add` and preserves errors. Open a fresh thread after changing the installation. The plugin manifest registers `./skills` and `./.mcp.json`. Expected discovery is five research tools plus `kvasir-agent:kvasir-agent`, `kvasir-agent:idea-spark` and `kvasir-agent:ponder-forge`; project paths must be supplied explicitly. Delphi's two workflows use the [native host contract](../delphi/HOSTS.md) and the terminal CLI, adding no MCP tools.

For updates to a local source, refresh the plugin cache version and reinstall from the registered marketplace. Verify the installed source/cache identity, not only the source checkout. A source-level test does not prove host discovery.

Codex's [MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) and [plugin documentation](https://developers.openai.com/plugins/build/plugins) describe the host integration. The marketplace wrapper is a Codex installation step; it does not initialize research projects.

## Pi

In Pi versions with native MCP support, install a project-local server:

```sh
bash /absolute/plugin/path/scripts/install_pi.sh /absolute/existing/project
```

The wrapper delegates to `pi mcp add -l`, preserves unrelated servers through Pi's native configuration writer, and records absolute interpreter, script and working-directory paths in `.pi/mcp.json`. Its default `codemode` exposure keeps the five tool schemas callable on demand. Trust the project using Pi's own controls, then open a session or `/reload`; `/mcp` shows discovery and connection state. For direct declarations, change the server's exposure to `direct` in Pi. This needs a Pi release supporting `mcp add --exposure` (verified with Pi 1.0.0).

The research skill is optional and explicitly selected in Pi:

```sh
pi --skill /absolute/plugin/path/skills/kvasir-agent/SKILL.md
```

The two Delphi skills can be selected explicitly with the same `--skill` syntax. Their common CLI does not depend on Hermes. Pi's actual native multi-agent execution is verified separately. The separate `manual/` directory stays outside discovery. No Pi extension, session loop or model provider is supplied by Kvasir.

## Manual project creation

Project creation is a separate, user-triggered action:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 /absolute/plugin/path/scripts/ka_admin.py init --project /absolute/existing/project
```

This creates minimal state and no Codex instructions. The independent `manual/init/SKILL.md` is packaged but not registered or auto-discovered. Its name, description, path and body are absent from ordinary model startup context. Users may execute the terminal command directly, or explicitly supply the manual path in a separate conversation. See [ADMIN_CLI.md](ADMIN_CLI.md) for legacy migration and maintenance.
