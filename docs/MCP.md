# Research MCP

The bundled stdio server is `scripts/ka_mcp.py`. Standard discovery exposes exactly four tools in one server. Delphi has one aggregated entrypoint; low-level ledger operations are not individual MCP tools.

| Tool | Required inputs | Behavior |
| --- | --- | --- |
| `ka_research_status` | project | Read project state; optional run_id selects a run. No filesystem writes. |
| `ka_experiment` | project, action; run: spec_path, idempotency_key; stop: run_id | Validate and start a managed process, or stop its recorded instance and preserve terminal facts. |
| `ka_evidence` | project, action, spec_path | check: save an evidence report; import: preserve external artifacts and unverified provenance. |
| `ka_delphi` | project, workflow, action; action-specific identity and file arguments | Prepare native research, collect complete files and query bounded Delphi state. |

`action` is required and has no default. Experiment actions are `run` and `stop`; evidence actions are `check` and `import`. The public schema is flat; the server checks action-specific required and unused fields before opening project services. Stop calls omit `spec_path` and `idempotency_key`; run calls omit `run_id`. Both evidence actions use `spec_path`, pointing to the existing CheckSpec or import manifest respectively. File formats and saved state are unchanged.

`project` is an explicit absolute directory. Evidence specifications are project-contained; contracts and examples are in [EVIDENCE_SPECS.md](EVIDENCE_SPECS.md). Missing evidence state returns a short error without creating directories. Delphi open explicitly creates its own workflow state under `<project>/.kvasir/delphi`; other calls require an existing room/run. Old method names are rejected without dispatching to legacy handlers. Routine files, plans, literature, logs and research prose use Codex/Pi native tools.

## Delphi

Use `workflow=idea_spark` with open/status/prepare/collect/update/finish. Open defaults to `mode=open_discussion`; choose deep_exploration for proposal development. Use `workflow=ponder_forge` with open/status/plan/prepare/record/collect/verify/finish. Ponder open defaults to `effort=max`; high retains the complete high strategy. Mode is checked by the selected engine, so additional supported research modes can reuse the tool.

Open requires goal and request_id. Prepare and verify also require request_id; new allocations get new IDs, retries reuse the original ID and input. Allocation reservations preserve identities across interrupted responses; changed inputs are rejected. Open returns instruction_path, editable input_templates and a complete next_call. Read the selected controller once. Prepare returns complete worker instructions, input/output/scratch paths and receipt identity; the MCP does not create native agents.

Use native launch/wait/follow-up/cancellation tools. For Ponder, record a confirmed start with task_id, status=started and host_agent_id; record confirmed cancellation with status=cancelled. Workers deliver complete UTF-8 reports and return paths; writing failure returns the complete body for parent recovery. Collect uses receipt_paths; Ponder also accepts task_id + file_path with optional metadata input_path/status. Each batch entry gets its own result. Different reviewer identities retain identical prose independently; no content hash is used.

Update uses a JSON file containing a checkpoint and optionally messages, links, needs, need_updates, artifact_statuses or gates. These are explicit ledger batches, each scoped to the existing room. Open discussion finishes through its parent gate template; deep exploration finishes completed with a registered ResearchProposal file, or stopped with a reason. Ponder plan uses the board template, verify prepares native final/local verification, and finish saves the full Markdown file_path. Partial finish uses status=partial and an input_path JSON reason. Collection does not decide scientific validity or resolve board questions.

Status defaults to 20 entries, at most 50, and returns current facts, complete-file paths and history indexes. Large report bodies and full policies stay on disk. Init, configuration, maintenance and dashboard launch remain manual CLI operations; see [HOSTS.md](../delphi/HOSTS.md). Existing CLI workflows remain available.

MCP results contain `content`, `structuredContent` and `isError`; business data is not repeated at the protocol top level. Both structured/text representations contain only the bounded receipt. Complete requests, artifacts and reports stay on disk. Only status is annotated read-only. Experiment declares destructive side effects and conservatively uses `idempotentHint=false` and `openWorldHint=true` for the combined capability. Matching run keys still reuse saved requests and repeated stop still preserves terminal facts. Evidence check writes its report; imports remain externally unverified.

Use `python3 scripts/ka_mcp.py --stdio-smoke tools/list` for local discovery. A process start receipt is not evidence of success. Inspect saved terminal status, evidence status and referenced report files. Invalid arguments and unknown tools do not write project state.
