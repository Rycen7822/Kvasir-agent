# Repository layout

This repository is intentionally organized as a small Codex plugin plus a packaged local runtime. Keep the split simple: protocol and CLI adapters call the service layer; bundled resources are data snapshots, not a second implementation.

## Canonical source trees

- `codex_scientist/services/` — business logic and project-local state primitives: manifest, trial, runner, queue, wiki, review, cost, migration, and soak services.
- `codex_scientist/mcp/` — stable curated MCP stdio server, tool registry, and bounded skill retrieval. MCP handlers call services directly and do not shell out to `scripts/csctl.py`.
- `codex_scientist/adapters/` — compatibility and envelope helpers shared by CLI/MCP surfaces.
- `codexscientist_native/` — packaged native runtime surface used by the plugin.
- `codexscientist_native/vendor/` — vendored upstream-style runtime code. Avoid feature work here unless the change is explicitly a vendor/runtime compatibility patch.
- `codexscientist_native/resources/` — packaged prompts, templates, and skill snapshots installed into generated projects.
- `skills/` — active Codex plugin skills loaded directly from this repository.
- `scripts/` — human/CI entrypoints. `scripts/cs_mcp.py` is the MCP stdio entrypoint; `scripts/csctl.py` is the CLI fallback; `scripts/cs_native_cli.py` is the lower-level native CLI bridge.
- `docs/` — human-facing architecture, installation, usage, migration, MCP, and maintenance notes.
- `tests/` — contract and regression tests. Keep new behavior covered by tests before changing implementation.

## Runtime state

Project runtime state belongs under a user's project directory, not in this plugin repository. The default runtime directory name is `CodexScientist/`; `DeepScientist/` is ignored only to keep migrated local worktrees clean while legacy state is being retired.

These directories are ignored at repository root:

- `CodexScientist/`
- `DeepScientist/`

Do not commit runtime journals, queues, artifacts, or generated quest state.

## Resource policy

For now the repository deliberately keeps both active plugin skills and packaged resource snapshots:

- edit `skills/codexscientist-*` when changing the active plugin prompt surface;
- edit `codexscientist_native/resources/` only when the packaged install/runtime snapshot must change;
- if a change touches both, keep names and high-level wording aligned and add/update a regression test.

This avoids a premature sync generator while still making the current duplication explicit.

## What not to move without a separate plan

- Do not move core packages into `src/` without first updating plugin install scripts and smoke tests.
- Do not merge `codex_scientist` and `codexscientist_native`; they serve different maintenance roles.
- Do not expand MCP into an all-tools runtime surface. Keep it curated and keep `scripts/csctl.py` as fallback.
