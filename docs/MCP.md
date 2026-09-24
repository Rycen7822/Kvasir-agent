# Research MCP

The bundled stdio server is `scripts/ka_mcp.py`. Standard discovery always exposes exactly five tools. There are no profiles, hidden executor aliases or schema-lookup calls.

| Tool | Required inputs | Behavior |
| --- | --- | --- |
| `ka_research_status` | project | Read project state; optional run_id selects a run. No filesystem writes. |
| `ka_experiment_run` | project, spec_path, idempotency_key | Validate protected inputs and start a managed process. |
| `ka_experiment_stop` | project, run_id | Stop the recorded process instance and preserve terminal facts. |
| `ka_evidence_check` | project, spec_path | Save a material-integrity report and return bounded findings. |
| `ka_evidence_import` | project, manifest_path | Preserve external artifacts and unverified provenance. |

`project` is an explicit absolute directory. Specification files are project-contained; contracts and examples are in [EVIDENCE_SPECS.md](EVIDENCE_SPECS.md). Missing state returns a short error without creating directories. Old method names are rejected without dispatching to legacy handlers. Routine files, plans, literature, logs and research prose use Codex native tools.

MCP results contain `content`, `structuredContent` and `isError`; business data is not repeated at the protocol top level. Both structured/text representations contain only the bounded receipt. Complete requests, artifacts and reports stay on disk. Only status is annotated read-only. Run and stop declare destructive side effects; check writes its report.

Use `python3 scripts/ka_mcp.py --stdio-smoke tools/list` for local discovery. A process start receipt is not evidence of success. Inspect saved terminal status, evidence status and referenced report files. Invalid arguments and unknown tools do not write project state.
