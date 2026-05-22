# CodexScientist MCP

CodexScientist provides an MCP-only default research control plane for Codex. It exposes compact `cs_*` tool profiles for repeated research-control workflows while Codex-native file/search/edit/shell/Git/test/build/process capabilities remain the normal mechanical operation layer.

`/goal` is Codex-native. CodexScientist does not implement slash commands; after Codex has entered goal context, this plugin supplies MCP tools for project-local research state, bounded context views, passive checkpoint/resume anchors, manual diagnostics, novelty support, and claim gates.

## Goals

- Keep the default Codex research surface MCP-only and fail closed when a tool or server is unavailable.
- Expose compact tool cards through `tools/list`; load detailed schemas lazily through `cs_tool_schema`.
- Keep the hidden admin/debug CLI isolated in `docs/ADMIN_CLI.md` for human/admin/debug/CI/recovery compatibility.
- Reuse `codex_scientist/services` directly rather than shelling out to terminal compatibility commands.

## Smoke commands

```bash
python scripts/cs_mcp.py --stdio-smoke initialize
python scripts/cs_mcp.py --stdio-smoke tools/list
python scripts/cs_mcp.py --stdio-smoke tools/list '{"profile":"evidence"}'
python scripts/cs_mcp.py --stdio-smoke call cs_doctor '{}'
```

## Current MCP profiles

- `core`: default tools for doctor/status, root-bound research anchoring, schema lookup, passive context/resume/checkpoint/delta.
- `evidence`: evidence recording profile for root-bound memory, manifest, baseline, artifact, experiment, analysis, method, and claim-gate workflows.
- `formal_run`: evidence plus `cs_bash_exec` for formal provenance-gated commands.
- `literature`: strict literature, paper fetch, paper reliability, bibliography, and project-local reading notes.
- `paper_write`: literature plus outline, paper bundle, summary refresh, and review status.
- `goal`: deprecated compatibility alias for `evidence`; prefer `evidence` for Codex-native goal work.
- `admin`, `autonomous`, and `legacy_compat`: not registered as default MCP surfaces; use only for explicit human/admin/debug/CI/recovery compatibility.

Planned execution-grounded profiles are fail-closed until their services and tests exist:

- `execution_planning`: plan-only profile for environment summaries, feedback ingestion, trajectory lookup, and `cs_evolutionary_round_plan`; it records or proposes research state but does not run jobs or apply patches.
- `executor_local`: local executor profile for gated variant and run tools such as `cs_variant_create`; it is not registered by default and remains blocked unless `CODEXSCIENTIST_ENABLE_EXECUTOR_MCP=1`, manifest authorization, budget, and environment validation all pass.

The default profile must not expose executor tools. Missing execution-grounded tools fail closed; do not replace them with hidden admin/debug commands.

The `stage` argument is a context label for records and prompts. It does not filter `tools/list` output.

Important evidence/formal tools include:

```text
cs_status
cs_record_user_requirement
cs_create_local_baseline
cs_confirm_baseline
cs_submit_idea
cs_record_main_experiment
cs_create_analysis_campaign
cs_get_analysis_campaign
cs_record_analysis_slice
cs_claim_gate
cs_checkpoint
cs_resume_brief
cs_pack_delta
cs_log_digest
cs_artifact_index
```

## Method improvement and claim gate

After experiment or analysis evidence, `cs_record_main_experiment` and related tools record evidence only; Codex remains the planner. The safe loop is:

1. record evidence and negative memory where applicable;
2. call `cs_update_method_scoreboard` when the method ledger should record an outcome;
3. let Codex decide any next idea or follow-up action;
4. call `cs_claim_gate` before making any external-facing claim.

Evidence-poor or duplicate candidates fail closed with structured evidence gaps rather than encouraging an ungrounded claim.

## Manual diagnostics, checkpoint, and resume

Long-running goal work should keep recovery anchors fresh:

1. state-changing MCP tools do not auto-inject checkpoint/manual-diagnostic gate metadata;
2. public recovery uses `cs_status`, `cs_resume_brief`, `cs_pack_delta`, `cs_log_digest`, and `cs_artifact_index`; hidden/admin-only watchdog diagnostics stay outside the default MCP surface;
3. `cs_checkpoint` records completed phase boundaries, decisions, validation, and artifact refs;
4. `cs_resume_brief` returns current root-bound research state, active run id, passive recovery anchor, source refs, and bounded text for compaction recovery.

## Skills and support procedures

Bundled support skills are loaded by the Codex plugin skill mechanism, not by the default MCP profile. Use them when a subtask needs a procedure, then use visible MCP tools from the selected profile to record durable research state.

## Safety

- No all-tools/full-runtime MCP.
- Tool annotations expose read-only/destructive/idempotent/open-world hints.
- State-changing tools with declared required context keys fail closed on missing arguments before handlers create default resources.
- Outputs must be bounded and redacted.
- Errors return `ok=false`, stable `error_type`, `recoverable`, and a suggested next MCP action when useful; known recoverable missing-resource cases should not leak raw `FileNotFoundError` / `ValueError` class names.
- Missing tools fail closed: fix MCP/doctor/config or implement the missing MCP tool; do not switch the default research flow to terminal compatibility commands.
