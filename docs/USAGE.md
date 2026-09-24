# Research workflow

Kvasir-agent supplies five tools for managed runs and evidence. Codex supplies research reasoning, file editing, literature work, coding, tests and task coordination.

1. Call `ka_research_status(project=absolute_path)` to inspect saved evidence.
2. When a managed experiment is needed, read the relevant [file contract](EVIDENCE_SPECS.md), write the environment and RunSpec files, and obtain the task's normal execution authorization.
3. Call `ka_experiment_run` with a stable idempotency key. Inspect returned paths instead of requesting full history. The wrapper finishes after the MCP connection closes.
4. Check the actual terminal record before using metrics. Run a baseline before a comparative experiment, which references that baseline ID.
5. Use `ka_evidence_check` for environment/run/claim material checks, or `ka_evidence_import` for external results. Keep scientific interpretation and sources in ordinary project documents.

`completed` and `evidence_status=verified` mean the local process succeeded and declared material checks passed. `failed`, `cancelled`, `timed_out` and `interrupted` remain distinct. A partial derived result does not erase the authoritative run record. External and migrated results retain unverified provenance.

There is one active skill, `kvasir-agent`. No phase skill, task controller, planning MCP, literature CRUD API or mandatory checkpoint ceremony is needed. Historical domain material is retained under `docs/reference/workflows/` for deliberate human reference, with obsolete tool names labelled as historical.
