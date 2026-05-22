# Codex-Scientist Architecture

Codex-Scientist is a Codex CLI plugin with an MCP-only default research control plane. It is not a standalone autonomous research platform and it is not a replacement for Codex-native file, shell, Git, test, build, or process capabilities.

## Runtime boundary

Runtime state remains project-local under:

```text
<project>/CodexScientist/
```

This tree stores quest state, events, runtime files, artifacts, memory, queue/runner ledgers, summaries, manual diagnostic records, checkpoints, validation reports, novelty decisions, and claim gate records. P4 quest-scoped state lives under `CodexScientist/quests/<quest_id>/` while compatibility indexes may remain under project-local global state roots.

## Default autonomy boundary

The default mode is `copilot`.

In default mode, Codex-Scientist records, validates, organizes, retrieves, summarizes, and audits research state. It does not automatically invent or improve ideas. Automatic idea or novelty improvement requires an explicit user request or a manifest/handoff that explicitly enables autonomous idea improvement.

## Adapter and service layers

`codex_scientist/adapters` owns process-facing compatibility code:

- `scripts/cs_mcp.py` is the MCP stdio entrypoint for repeated high-frequency research-control workflows.
- hidden admin/debug CLI entrypoints are isolated for CI, debugging, migration, recovery, and MCP-unavailable environments.
- Adapter code normalizes JSON envelopes, redaction, transport markers, and structured recoverable errors.
- Adapter code does not contain research business logic.

`codex_scientist/services` owns testable business and state primitives:

- project-local layout under `CodexScientist/`;
- append-only event logs and atomic snapshots;
- manifest, trial, runner, queue, wiki, frontier, journal, review, claim, cost, migration, and soak services;
- method improvement, manual diagnostics, checkpoint, resume, and context-pack services.

MCP handlers and terminal compatibility parsers call the same service layer. The MCP implementation must not shell out to terminal compatibility commands as its main path.

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
- method scoreboard/frontier, novelty scoring, duplicate block, related-work gate, claim gate, manual diagnostics, checkpoint, and resume anchors;
- formal commands whose logs must become quest-local provenance.

Codex does the mechanical action; CodexScientist records the research meaning.

## Execution-grounded extension boundary

Execution-grounded research is an explicit extension of the semantic/provenance layer, not a replacement for Codex-native mechanical work. The default `copilot` mode does not automatically invent, implement, schedule, or execute ideas. It may record environments, feedback, trajectories, and plans only when the user request or project state makes that research meaning explicit.

Automatic idea search, variant implementation, experiment scheduling, or executor-backed execution requires an explicit user request or manifest. Until that gate exists, execution-grounded services must stay local, auditable, and plan-first: `ResearchEnvironment` describes trusted evaluation contracts, feedback ingestion records bounded evidence, trajectory storage records lineage and outcomes, and evolutionary planning proposes next candidates without submitting them.

## MCP boundary

The MCP boundary uses explicit profiles:

- `core`: 11 default tools for doctor/status, quest anchoring, schema lookup, passive context/resume/checkpoint/delta.
- `evidence`: quest-local memory, manifest, baseline, artifact, experiment, analysis, method, and claim-gate workflows.
- `formal_run`: evidence plus formal `cs_bash_exec` provenance-gated execution.
- `literature`: strict literature, paper fetch, reliability, bibliography, and reading-note workflows.
- `paper_write`: literature plus paper outline/bundle/summary/review work.
- `admin`, `autonomous`, and `legacy_compat`: not registered as default MCP surfaces.

The `stage` argument is a label for context and records. It does not select a smaller tool subset.

Long procedures stay in Codex plugin skills and reference files. Load them through the Codex skill mechanism when the current subtask needs a procedure, then record durable state through visible MCP tools.

Context recovery should preserve enough structure to continue correctly: normal resume uses 4K-8K chars, incident/debug/audit may use 12K-24K chars, and full raw log/artifact/reference reads require explicit opt-in.
