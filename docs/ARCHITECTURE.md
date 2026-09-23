# Kvasir-agent Architecture

Kvasir-agent is a Codex CLI plugin with an MCP-only default research control plane. It is not a standalone autonomous research platform and it is not a replacement for Codex-native file, shell, Git, test, build, or process capabilities.

## Runtime boundary

Runtime state remains project-local under:

```text
<project>/Kvasir-agent/
```

This tree stores one root-bound research state: `research.yaml`, events, runtime files, artifacts, memory, queue/runner ledgers, summaries, manual diagnostic records, checkpoints, validation reports, novelty decisions, and claim gate records. `Kvasir-agent/quests/<quest_id>/` is a legacy migration input only; new writes target the root-bound state tree directly.

## Default autonomy boundary

The default mode is `copilot`.

In default mode, Kvasir-agent records, validates, organizes, retrieves, summarizes, and audits research state. It does not automatically invent or improve ideas. Automatic idea or novelty improvement requires an explicit user request or a manifest/handoff that explicitly enables autonomous idea improvement.

## Adapter and service layers

`kvasir_agent/adapters` owns process-facing compatibility code:

- `scripts/ka_mcp.py` is the MCP stdio entrypoint for repeated high-frequency research-control workflows.
- hidden admin/debug CLI entrypoints are isolated for CI, debugging, migration, recovery, and MCP-unavailable environments.
- Adapter code normalizes JSON envelopes, redaction, transport markers, and structured recoverable errors.
- Adapter code does not contain research business logic.

`kvasir_agent/services` owns testable business and state primitives:

- project-local layout under `Kvasir-agent/`;
- append-only event logs and atomic snapshots;
- manifest, trial, runner, queue, wiki, frontier, journal, review, claim, cost, migration, and soak services;
- method improvement, manual diagnostics, checkpoint, resume, and context-pack services.

MCP handlers and terminal compatibility parsers call the same service layer. The MCP implementation must not shell out to terminal compatibility commands as its main path.

## Kvasir-agent native runtime

`kvasir_agent/runtime` is the canonical local runtime package. Public schemas and tool handlers use `ka_*` names. Historical legacy package paths and non-`ka_*` public names are not part of the default surface.

## Operation boundary

Codex-native operation layer:

- read/search/edit/patch files;
- run ordinary shell commands;
- run tests/builds/lints;
- manage Git/GitHub and processes;
- inspect dependencies and local project state.

Kvasir-agent semantic/provenance layer:

- root-bound research state and provenance metadata;
- durable user requirements;
- memory and artifact records;
- baseline, experiment, analysis, paper, reliability, and evidence ledgers;
- method scoreboard/frontier, novelty input records, duplicate block, related-work gate, claim gate, manual diagnostics, checkpoint, and resume anchors;
- formal commands whose logs must become project-local research provenance.

Codex does the mechanical action; Kvasir-agent records the research meaning.

## Execution-grounded extension boundary

Execution-grounded research is an explicit extension of the semantic/provenance layer, not a replacement for Codex-native mechanical work. The default `copilot` mode does not automatically invent, implement, schedule, or execute ideas. It may record environments, feedback, trajectories, and plans only when the user request or project state makes that research meaning explicit.

Automatic idea search, variant implementation, experiment scheduling, or executor-backed execution requires an explicit user request or manifest. Until that gate exists, execution-grounded services must stay local, auditable, and plan-first: `ResearchEnvironment` describes trusted evaluation contracts, feedback ingestion records bounded evidence, trajectory storage records lineage and outcomes, and evolutionary planning proposes next candidates without submitting them.

## MCP boundary

Default standard MCP discovery advertises all 24 public research tools with parameter schemas. Explicit profiles are optional filters:

- `core`: three tools for bounded research reads, durable user requirements, and checkpoints.
- `evidence`: root-bound memory, manifest, baseline, artifact, experiment, analysis, method, and claim-gate workflows.
- `formal_run`: evidence plus formal `ka_bash_exec` provenance-gated execution.
- `literature`: strict literature, paper fetch, reliability, bibliography, and reading-note workflows.
- `paper_write`: literature plus outline/bundle recording; review status is available through research reads.
- `admin`, `autonomous`, and `legacy_compat`: not registered as default MCP surfaces.

The `stage` argument is a label for context and records. It does not select a smaller tool subset.

Long procedures stay in Codex plugin skills and reference files. Load them through the Codex skill mechanism when the current subtask needs a procedure, then record durable state through visible MCP tools.

Context recovery should preserve enough structure to continue correctly: normal resume uses 4K-8K chars, incident/debug/audit may use 12K-24K chars, and full raw log/artifact/reference reads require explicit opt-in.

## Native ownership and retained references

Codex owns goal continuation, native skill discovery and ordinary execution. Kvasir-agent keeps domain evidence and passive recovery. Custom skill retrieval and the duplicate goal controller were removed. Seven native skills cover distinct research workflows; historical domain detail is retained under `docs/research-playbooks/`. Context-pack export remains an admin/legacy service. The plugin manifest bundles `.mcp.json`, and installation delegates to the native Codex plugin CLI.
