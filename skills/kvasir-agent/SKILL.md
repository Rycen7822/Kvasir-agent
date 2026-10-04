---
name: kvasir-agent
description: Run research experiments and inspect project-local evidence with Kvasir-agent.
---

# Research evidence

Use the five research tools when the task needs managed experiments or recorded evidence. Codex handles research reasoning, literature searches, document editing, code, tests, Git, and task coordination through its native capabilities. A recorded result is not a scientifically validated conclusion.

## Choose an operation

| Tool | Use |
| --- | --- |
| `ka_research_status` | Read saved project or run state without filesystem changes. |
| `ka_experiment_run` | Validate a RunSpec and declared settings, then start an authorized run. |
| `ka_experiment_stop` | Stop a recorded run and retain its actual terminal state. |
| `ka_evidence_check` | Check a versioned evidence specification; save a report. |
| `ka_evidence_import` | Preserve external results with unverified origin. |

Pass `project` as the absolute research project directory. A specification path resolves within that project. Do not use a plugin installation directory as the research project. Tools return bounded summaries and file paths; read only the referenced detail relevant to the task.

## Managed experiments

Read [file contracts](../../docs/EVIDENCE_SPECS.md) when preparing a run, check or import. Load only the matching example/schema. Write specifications using ordinary file tools. Environment records declare evaluator/dataset paths and the metric. An experiment references a completed baseline with available metrics and matching declared settings. Ordinary records need no hashes.

Use a stable `idempotency_key` for the same RunSpec. Repeating it returns the saved run and original snapshots, even after separate input documents are edited. Deliberately running again requires a new key. A start receipt does not prove completion. Read status after useful work or with a reasonable polling interval. If a wrapper is interrupted, report that uncertainty; do not automatically launch a replacement.

The process receives `KVASIR_RUN_DIR`, `KVASIR_RUN_ID` and `KVASIR_SEED`. Store declared outputs under that run directory. The wrapper writes logs, parses the metric and records completion even after MCP disconnects. It does not repeatedly hash inputs or outputs.

## Evidence interpretation

`completed` records process success; `evidence_status=recorded` means its metric and outputs were recorded. Neither proves unchanged bytes or scientific validity. Metric issues do not rewrite successful process exit. `derivation_status=partial` means downstream result recording is incomplete. Preserve these distinctions.

Checks return reports even when evidence is insufficient. Use the issues for the relevant decision; do not repeat checks or rerun successful experiments just to clear labels. Claim checks resolve saved metrics and declared seeds. External imports remain `external_unverified`. Keep uncertainty and negative findings using native file editing; missing evidence stays unknown.

Load [research records and templates](../../docs/RESEARCH_RECORDS.md) only when recording sources, ideas, candidates or a saved-version review. Use the project research index to locate existing material and history. Detailed file contracts remain on disk.
