---
name: kvasir-agent
description: Run reproducible research experiments and inspect project-local evidence with Kvasir-agent.
---

# Research evidence

Use the five research tools when the task needs managed experiments or recorded evidence. Codex handles research reasoning, literature searches, document editing, code, tests, Git, and task coordination through its native capabilities. A recorded result is not a scientifically validated conclusion.

## Choose an operation

| Tool | Use |
| --- | --- |
| `ka_research_status` | Read saved project or run state without filesystem changes. |
| `ka_experiment_run` | Validate a RunSpec file and protected inputs, then start an authorized run. |
| `ka_experiment_stop` | Stop a recorded run and retain its actual terminal state. |
| `ka_evidence_check` | Check environment, run or claim evidence; save a report. |
| `ka_evidence_import` | Preserve external results with unverified origin. |

Pass `project` as the absolute research project directory. A specification path resolves within that project. Do not use a plugin installation directory as the research project. Tools return bounded summaries and file paths; read only the referenced detail relevant to the task.

## Managed experiments

Read [file contracts](../../docs/EVIDENCE_SPECS.md) when preparing a run, check or import. Load only the matching example/schema. Write specifications using ordinary file tools. Environment records pin evaluator and dataset hashes and define the metric. An experiment must reference a completed, verified baseline in the same environment.

Use a stable `idempotency_key` for the same request. Repeating that request returns the saved run; changing the request requires a new key. A start receipt does not prove completion. Read status after useful work or with a reasonable polling interval. If a wrapper is interrupted, report that uncertainty; do not automatically launch a replacement under a new key.

The process receives `KVASIR_RUN_DIR`, `KVASIR_RUN_ID` and `KVASIR_SEED`. Store declared output files under that run directory. The wrapper writes logs, checks protected inputs again, parses the metric, and records a result when execution ends, even after the MCP connection closes. There is no separate trajectory or method registration step.

## Evidence interpretation

`completed` plus `evidence_status=verified` establishes local execution and checked material integrity. Inspect failures, missing artifacts and the saved report before using a result. `derivation_status=partial` means the run record exists but downstream result recording is incomplete. Preserve that distinction in reports.

Claim checks resolve actual run records and observed seeds. They do not judge novelty, statistical adequacy or scientific validity. External imports remain `external_unverified`; a successful checksum check cannot upgrade their execution origin. Keep uncertainty and negative findings in project documents using native file editing. Never reinterpret missing evidence as success.
