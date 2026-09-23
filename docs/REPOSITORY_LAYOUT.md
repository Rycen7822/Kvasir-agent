# Repository layout

This repository is intentionally organized as a small Codex plugin plus a packaged local runtime. Keep the split simple: protocol and terminal compatibility adapters call the service layer; bundled resources are data snapshots, not a second implementation.

## Canonical source trees

- `kvasir_agent/services/` — business logic and project-local state primitives: manifest, trial, runner, queue, wiki, review, cost, migration, soak, goal loop, stage router, method improvement, progress watchdog, checkpoint, resume, and context-pack services.
- `kvasir_agent/mcp/` — MCP stdio server, tool registry, goal context helpers, research tool wrappers, surface allowlist, and bounded skill retrieval. MCP handlers call services directly and do not shell out to terminal compatibility entrypoints.
- `kvasir_agent/adapters/` — compatibility and envelope helpers shared by CLI/MCP surfaces.
- `kvasir_agent/runtime/` — packaged native runtime surface used by the plugin.
- `kvasir_agent/runtime/vendor/` — vendored upstream-style runtime code. Avoid feature work here unless the change is explicitly a vendor/runtime compatibility patch.
- `kvasir_agent/runtime/resources/` — packaged prompts, templates, and skill snapshots installed into generated projects.
- `skills/` — active Codex plugin skills loaded directly from this repository.
- `scripts/` — human/CI entrypoints. `scripts/ka_mcp.py` is the MCP stdio entrypoint; `scripts/p4_acceptance.py` is the P4 local/CI acceptance gate; hidden admin/debug CLI files are documented only in `docs/ADMIN_CLI.md`.
- `docs/` — human-facing architecture, installation, usage, migration, MCP, long-run, admin, and maintenance notes.
- `tests/` — contract and regression tests. Keep new behavior covered by tests before changing implementation.

## Runtime state

Project runtime state belongs under a user's research project directory, not in this plugin repository. The default runtime directory inside a research project is `Kvasir-agent/`.

Important project-local files include:

- `Kvasir-agent/events/events.jsonl` and `Kvasir-agent/events/events.lock`;
- `Kvasir-agent/events/corrupt/` for quarantined corrupt JSONL lines;
- `Kvasir-agent/research.yaml` for the root-bound manifest and provenance id;
- `Kvasir-agent/memory/`, `artifacts/`, `runtime/`, `method_memory/`, `trials/`, `variants/`, and `trajectories/` for root-bound durable research state;
- `Kvasir-agent/runs/<run_id>/runner.json`, `run.log`, `stderr.log`, `heartbeat.txt`, and `exit_code.txt` for project-local run ledgers;
- `Kvasir-agent/queue/queue_state.json`;
- `Kvasir-agent/artifacts/` and `Kvasir-agent/results/` indexed by `ka_artifact_index`;
- `Kvasir-agent/summaries/` for context packs, long-run validation, and recovery reports.

`Kvasir-agent/quests/<quest_id>/` is reserved for legacy migration input. New runtime writes must not create it.

The plugin repository root should not contain `Kvasir-agent/` or `DeepScientist/`. If either directory appears here, treat it as accidental local runtime state and remove it after checking that it contains no user data.

Do not commit runtime journals, queues, artifacts, or generated research state.

## Resource policy

For now the repository deliberately keeps both active plugin skills and packaged resource snapshots:

- edit `skills/kvasir-agent-*` when changing the active plugin prompt surface;
- edit `kvasir_agent/runtime/resources/` only when the packaged install/runtime snapshot must change;
- if a change touches both, keep names and high-level wording aligned and add/update a regression test.

This avoids a premature sync generator while still making the current duplication explicit.

## What not to move without a separate plan

- Do not move core packages into `src/` without first updating plugin install scripts and smoke tests.
- Do not collapse `kvasir_agent/runtime/` into `kvasir_agent/services/`; runtime/vendor/resources and service-layer orchestration serve different maintenance roles.
- Do not expand MCP into an all-tools runtime surface. Keep the MCP default compact and stage-gated.
