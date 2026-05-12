# Codex-Scientist Architecture

Codex-Scientist is a Codex CLI plugin with a stable curated MCP control plane. It is not a standalone autonomous research platform and it is not a replacement for Codex-native file, shell, Git, test, build, or process capabilities.

## Runtime boundary

Runtime state remains project-local under:

```text
<project>/CodexScientist/
```

This tree stores quest state, events, runtime files, artifacts, memory, queue/runner ledgers, summaries, and validation reports.

## Default autonomy boundary

The default mode is `copilot`.

In default mode, Codex-Scientist records, validates, organizes, retrieves, summarizes, and audits research state. It does not automatically invent or improve ideas. Automatic idea or novelty improvement requires an explicit user request or a manifest/handoff that explicitly enables autonomous idea improvement.

## Adapter and service layers

`codex_scientist/adapters` owns process-facing compatibility code:

- `scripts/cs_mcp.py` is the stable curated MCP entrypoint for repeated high-frequency research-control workflows.
- `scripts/csctl.py` is the CLI fallback for CI, debugging, migration, recovery, and MCP-unavailable environments.
- Adapter code normalizes JSON envelopes, redaction, transport markers, and structured recoverable errors.
- Adapter code does not contain research business logic.

`codex_scientist/services` owns testable business and state primitives:

- project-local layout under `CodexScientist/`;
- append-only event logs and atomic snapshots;
- manifest, trial, runner, queue, wiki, frontier, journal, review, claim, cost, migration, and soak services.

MCP handlers and CLI parsers call the same service layer. The implementation must not shell out to `csctl.py` as the main MCP path.

## CodexScientist native runtime

`codex_scientist/runtime` is the canonical local runtime package. Public schemas and tool handlers use `cs_*` names. Historical legacy package paths and non-`cs_*` public names are not part of the default surface.

## Operation boundary

Codex-native operation layer:

- read/search/edit/patch files;
- run ordinary shell commands;
- run tests/builds/lints;
- manage Git/GitHub and processes;
- inspect dependencies and local project state.

CodexScientist semantic/provenance layer:

- quest lifecycle and active mode;
- durable user requirements;
- memory and artifact records;
- baseline, experiment, analysis, paper, reliability, and evidence ledgers;
- formal commands whose logs must become quest-local provenance.

Codex does the mechanical action; CodexScientist records the research meaning.

## MCP boundary

The stable curated MCP exposes a small `cs_*` tool family for repeated workflows such as doctor/status, manifest validation, queue status, context packs, and bounded skill retrieval. It deliberately avoids an all-tools/full-runtime MCP.

Long procedures stay in skills and references, but the default access path is `cs_skill_search` followed by a bounded `cs_skill_load` view. CLI fallback remains available and should continue to pass parity smoke tests against representative MCP calls.
