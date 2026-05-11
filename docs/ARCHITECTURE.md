# Codex-Scientist Architecture

Codex-Scientist is a Codex CLI plugin. It is not an MCP transport, not a standalone autonomous research platform, and not a replacement for Codex-native file, shell, Git, test, build, or process capabilities.

## Runtime boundary

The plugin contributes skills and local control scripts. Runtime state remains project-local under:

```text
<project>/DeepScientist/
```

This tree stores quest state, events, runtime files, artifacts, memory, and future queue/runner ledgers. Source-code paths outside `DeepScientist/` are modified only by ordinary Codex-native operations or by explicit project allowlists in later manifest/trial phases.

## Default autonomy boundary

The default mode is `copilot`.

In default mode, Codex-Scientist records, validates, organizes, retrieves, summarizes, and audits research state. It does not automatically invent or improve ideas. Automatic idea or novelty improvement requires an explicit user request or a manifest/handoff that explicitly enables autonomous idea improvement.

## Adapter layer

`codex_scientist/adapters` owns process-facing compatibility code:

- `scripts/csctl.py` is the primary native CLI control surface.
- `scripts/dsctl.py` is the legacy-compatible entry point.
- Adapter code normalizes JSON envelopes: `ok`, `transport="codex-native-cli"`, `mcp=false`, error type or code, recoverability, and redaction.
- Adapter code does not contain research business logic.

## Service layer

`codex_scientist/services` owns testable business and state primitives:

- project-local layout under `DeepScientist/`;
- append-only event logs;
- atomic snapshots;
- corruption quarantine;
- future manifest, trial, runner, queue, wiki, review, and cost services.

`deepscientist_native` remains the compatibility runtime while services are migrated incrementally. New implementation work moves stable logic into services behind tests rather than adding more behavior to one large script.

## Operation boundary

Codex-native operation layer:

- read/search/edit/patch files;
- run ordinary shell commands;
- run tests/builds/lints;
- manage Git/GitHub and processes;
- inspect dependencies and local project state.

DeepScientist semantic/provenance layer:

- quest lifecycle and active mode;
- durable user requirements;
- memory and artifact records;
- baseline, experiment, analysis, paper, reliability, and evidence ledgers;
- formal commands whose logs must become quest-local provenance.

Codex does the mechanical action; DeepScientist records the research meaning.

## No-MCP contract

The default plugin manifest does not register MCP servers. The repository must not create `.mcp.json`, install FastMCP transport, or instruct Codex to use MCP-style calls for this adapter. Business-equivalence with older DeepScientist/Hermes surfaces is implemented through native `ds_*` wrappers and local service code.
