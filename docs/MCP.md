# Research MCP

The bundled stdio server is `scripts/ka_mcp.py`. Standard discovery always exposes exactly three tools. There are no profiles, hidden executor aliases or schema-lookup calls.

| Tool | Required inputs | Behavior |
| --- | --- | --- |
| `ka_research_status` | project | Read project state; optional run_id selects a run. No filesystem writes. |
| `ka_experiment` | project, action; run: spec_path, idempotency_key; stop: run_id | Validate and start a managed process, or stop its recorded instance and preserve terminal facts. |
| `ka_evidence` | project, action, spec_path | check: save an evidence report; import: preserve external artifacts and unverified provenance. |

`action` is required and has no default. Experiment actions are `run` and `stop`; evidence actions are `check` and `import`. The public schema is flat; the server checks action-specific required and unused fields before opening project services. Stop calls omit `spec_path` and `idempotency_key`; run calls omit `run_id`. Both evidence actions use `spec_path`, pointing to the existing CheckSpec or import manifest respectively. File formats and saved state are unchanged.

`project` is an explicit absolute directory. Specification files are project-contained; contracts and examples are in [EVIDENCE_SPECS.md](EVIDENCE_SPECS.md). Missing state returns a short error without creating directories. Old method names are rejected without dispatching to legacy handlers. Routine files, plans, literature, logs and research prose use Codex/Pi native tools.

MCP results contain `content`, `structuredContent` and `isError`; business data is not repeated at the protocol top level. Both structured/text representations contain only the bounded receipt. Complete requests, artifacts and reports stay on disk. Only status is annotated read-only. Experiment declares destructive side effects and conservatively uses `idempotentHint=false` and `openWorldHint=true` for the combined capability. Matching run keys still reuse saved requests and repeated stop still preserves terminal facts. Evidence check writes its report; imports remain externally unverified.

Use `python3 scripts/ka_mcp.py --stdio-smoke tools/list` for local discovery. A process start receipt is not evidence of success. Inspect saved terminal status, evidence status and referenced report files. Invalid arguments and unknown tools do not write project state.
