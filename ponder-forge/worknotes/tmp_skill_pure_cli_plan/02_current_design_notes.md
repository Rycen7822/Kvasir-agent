# Current Design Notes

## Evidence inspected

- `plugin.yaml` lists `provides_tools` for all nine `ponder_forge_*` tools and `provides_hooks` for six hooks.
- `__init__.py` loops over `TOOL_NAMES` and calls `ctx.register_tool(...)`; loops over `HOOK_NAMES` and calls `ctx.register_hook(...)`; also registers `/ponder-forge` command and bundled skill.
- `schemas.py` defines `TOOL_NAMES`, `HOOK_NAMES`, and schema descriptions. Schemas allow `additionalProperties: true` and no structured per-command parameters.
- `tools.py` contains thin JSON-returning wrappers over core functions: profile selection, planning, delegation payload creation, report ingestion, gate evaluation, verification, final rendering, and reconcile.
- `commands.py` slash command only creates a run and instructs the model to call `ponder_forge_plan` next, so it is not a complete workflow surface.
- `hooks.py` provides subagent tracking, pre-tool role policy, post-tool observation, pre-LLM status injection, and session cleanup. These are runtime conveniences, not required for the core SQLite graph/gate/finalize workflow.
- `store.py` owns durable state using `HERMES_HOME` and SQLite; this is independent of Hermes tool registration.
- Existing tests currently lock in the model-visible plugin surface and direct tool contract.
- Hermes docs confirm plugin registration can separately add tools, hooks, slash commands, CLI commands, and bundled skills. `ctx.register_tool` makes tools visible to the model. Plugin-bundled skills are namespaced and opt-in via `skill_view("plugin:skill")`.

## Implications

1. The core Ponder-Forge graph/gate/report logic is already a Python library. CLI can call it without a Hermes tool surface.
2. The current slash command is insufficient for pure CLI because it still depends on model-visible follow-up tools.
3. The clean implementation is not to wrap nine tools behind one more tool; the user explicitly asked for true skill + pure CLI.
4. The first implementation should avoid deleting internal modules aggressively. Public registration can be removed first; internal dead modules can be removed after tests prove no dependency remains.
5. Tests must be rewritten so they protect the new contract rather than preserving the old tool count.

## Current confidence gaps before plan

- Need exact CLI argument design that is compact but complete.
- Need decide whether report submission reads JSON from `--file`, stdin, or inline string. Minimal robust choice: `--file` plus `-` for stdin if easy; avoid inline shell quoting for large reports.
- Need decide how plugin slash command behaves when no tools exist. Minimal choice: return JSON with CLI instructions and a command example; no hidden tool dispatch.
- Need decide whether `ctx.register_cli_command` is available in current runtime. Docs say yes, but current tests' FakeContext lacks it. Implementation can use `hasattr(ctx, "register_cli_command")` to register when available without adding runtime dependency; tests can cover the no-cli-command context and a context with it.
