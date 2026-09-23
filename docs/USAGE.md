# Usage

## Install and inspect

Follow [installation](INSTALL.md), including `python3 -m pip install -e .` for Python dependencies. Open a new Codex thread after updating the plugin.

```bash
python3 scripts/ka_mcp.py --stdio-smoke initialize
python3 scripts/ka_mcp.py --stdio-smoke tools/list
python3 scripts/doctor.py
```

The default MCP catalog has 24 public research tools with parameter schemas. Explicit `core`, `evidence`, `formal_run`, `execution_planning`, `literature`, and `paper_write` profiles are optional filters. Executors remain gated. The goal profile is deprecated and aliases evidence; stage labels do not filter tool discovery.

## Project identity

Pass an absolute `project` on every public call. Research records live under `<project>/Kvasir-agent/`; the plugin cache is never the implicit research directory. Quest identity is derived from `research.yaml`. Do not pass `project_root` or `quest_id` on the public API. Existing research files retain their provenance ids.

## Start and recover

1. Call `ka_research_read` with `operation="status"`. Read-only status does not create a project.
2. Record user constraints with `ka_record_user_requirement`; the first durable write initializes research state.
3. Call `ka_research_read` with `operation="resume"` and `max_chars=6000` for current constraints, autonomy mode, checkpoint, risks and evidence references.
4. Use `operation="delta"` for changes since an event sequence or checkpoint.
5. Use `ka_log_digest` and `ka_artifact_index` before opening large files.
6. Save `ka_checkpoint` at meaningful milestones.

Use 4K-8K chars for normal recovery and 12K-24K for necessary incident/debug/audit context. Raw logs and full artifacts are explicit bounded inspections, not default recovery content.

## Research workflow

- **Baseline/environment:** `ka_baseline` creates or confirms baselines; `ka_environment` registers and checks protected evaluation environments. A readiness record or stub is not measured baseline evidence.
- **Methods:** `ka_method_record(operation="idea")` requires a mechanism, related-work references and expected difference; no automatic novelty score is generated. Record measured outcomes with `operation="result"`, and failed approaches with `operation="negative"`.
- **Results:** formal provenance commands use `ka_bash_exec`; `ka_feedback_ingest` reconciles environment-linked results. `ka_record_main_experiment` stores data without verifying scientific validity.
- **Analysis:** `ka_analysis` creates/reads campaigns and records slices. Writing-facing campaigns preserve selected-outline bindings. `ka_claim_gate` checks material completeness.
- **Literature:** `ka_literature_setup` prepares the workspace; upsert candidates, verify references, fetch PDFs, initialize bibliography, and record reading notes.
- **Writing:** `ka_paper_record` records outlines/bundles. Draft and update SUMMARY.md through Codex file editing. `ka_research_read(operation="methods")` reads persisted method state without refreshing it.

Codex owns task continuation, experiment planning, skill discovery and ordinary coding work. Research tools preserve baselines, protected hashes, provenance, evidence and durable constraints. Default copilot mode does not authorize autonomous experiments; existing executor, environment and budget gates remain required.

See [MCP operations](MCP.md), [migration](TOOL_MIGRATION.md), [architecture](ARCHITECTURE.md), and [offline admin commands](ADMIN_CLI.md).
