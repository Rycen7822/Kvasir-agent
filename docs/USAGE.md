# Research workflow

Kvasir-agent supplies three tools for managed runs and evidence. Codex supplies research reasoning, file editing, literature work, coding, tests and task coordination.

1. Call `ka_research_status(project=absolute_path)` to inspect saved evidence.
2. When a managed experiment is needed, read the relevant [file contract](EVIDENCE_SPECS.md), write the environment and RunSpec files, and obtain the task's normal execution authorization.
3. Call `ka_experiment` with `action=run`, `spec_path` and a stable `idempotency_key`. Inspect returned paths instead of requesting full history. The wrapper finishes after the MCP connection closes. To stop, use `action=stop` and `run_id`, omitting the run-only parameters.
4. Check the actual terminal record before using metrics. Run a baseline before a comparative experiment, which references that baseline ID.
5. Use `ka_evidence` with `action=check` for versioned environment/run/import/comparison/research checks, or `action=import` for external results. Both actions use `spec_path` for the corresponding CheckSpec or import manifest. Keep scientific interpretation and sources in ordinary project documents.

`completed` records successful process exit; `evidence_status=recorded` means outputs and a metric were recorded. A successful process can have unavailable evidence without being relabeled failed. Ordinary workflows need no hashes and do not prove byte integrity. Checks with issues return completed reports rather than tool errors. `failed`, `cancelled`, `timed_out` and `interrupted` remain distinct. A partial derived result does not erase the authoritative run record. External and migrated results retain unverified provenance.

There is one active skill, `kvasir-agent`. No phase skill, task controller, planning MCP, literature CRUD API or mandatory checkpoint ceremony is needed. Historical domain material is retained under `docs/reference/workflows/` for deliberate human reference, with obsolete tool names labelled as historical.

Use [research records](RESEARCH_RECORDS.md) to locate papers, ideas and preserved historical files, and to bind reviews to saved versions. For fair paired experiments load the [comparison example](specs/comparison.example.json) and [RunSpec v2 example](specs/run-v2.example.json). Read run_id status for detailed observations; project lists stay compact.
