# CodexScientist MCP

CodexScientist provides an MCP-only default research control plane for Codex. It exposes compact `cs_*` tool profiles for repeated research-control workflows while Codex-native file/search/edit/shell/Git/test/build/process capabilities remain the normal mechanical operation layer.

`/goal` is Codex-native. CodexScientist does not implement slash commands; after Codex has entered goal context, this plugin supplies MCP tool routing, bounded skill/context views, project-local state, progress watchdog, checkpoint, resume, novelty, and claim gate contracts.

## Goals

- Keep the default Codex research surface MCP-only default and fail closed when a tool or server is unavailable.
- Expose compact tool cards through `tools/list`; load full schemas lazily through `cs_tool_schema`.
- Keep the hidden admin/debug CLI isolated in `docs/ADMIN_CLI.md` for human/admin/debug/CI/recovery compatibility.
- Reuse `codex_scientist/services` directly rather than shelling out to terminal compatibility commands.

## Smoke commands

```bash
python scripts/cs_mcp.py --stdio-smoke initialize
python scripts/cs_mcp.py --stdio-smoke tools/list
python scripts/cs_mcp.py --stdio-smoke call cs_doctor '{}'
python scripts/cs_mcp.py --stdio-smoke call cs_goal_context '{"active_stage":"experiment"}'
```

## Current MCP profiles

- core profile: 14 tools. This is the default `tools/list` surface and contains doctor/status, goal/context state, checkpoint/resume/delta, and bounded skill retrieval.
- goal profile: 47 tools. CodexScientist uses it only after Codex has entered a goal context.
- active stage subset: goal profile calls should pass the active stage so the current turn sees only the relevant stage tools.
- admin profile: not registered as default MCP; human/admin/debug/CI/recovery commands are documented separately.

Important goal tools include:

```text
cs_goal_context
cs_goal_state
cs_goal_next_action
cs_new_quest
cs_record_user_requirement
cs_create_local_baseline
cs_confirm_baseline
cs_submit_idea
cs_update_method_scoreboard
cs_select_next_idea
cs_claim_gate
cs_record_main_experiment
cs_goal_watchdog
cs_checkpoint
cs_resume_brief
cs_pack_delta
cs_runner_start
cs_runner_status
cs_log_digest
cs_artifact_index
cs_queue_submit
cs_queue_status
cs_trial_propose
cs_trial_plan
cs_trial_show
cs_create_analysis_campaign
cs_record_analysis_slice
```

## Method improvement and claim gate

After experiment or analysis evidence, `cs_record_main_experiment` or related analysis tools may create a method improvement gate. The safe loop is:

1. record evidence and negative memory where applicable;
2. call `cs_update_method_scoreboard` to update method scores and frontier state;
3. call `cs_select_next_idea` to choose a novelty-checked next candidate;
4. call `cs_claim_gate` before making any external-facing claim.

Evidence-poor or duplicate candidates fail closed and return a required next MCP tool rather than encouraging an ungrounded claim.

## Progress watchdog, checkpoint, and resume

Long-running goal work should keep recovery anchors fresh:

1. state-changing MCP tools return `checkpoint_due` and `progress_watchdog` metadata when a checkpoint is needed;
2. `cs_goal_watchdog` reconciles running jobs, stale heartbeat state, and stuck runners;
3. `cs_checkpoint` records completed stage boundaries, decisions, validation, and artifact refs;
4. `cs_resume_brief` returns `current_quest`, `active_stage`, `current_gate`, `active_run_id`, `next_required_mcp_tool`, `source_refs`, and bounded text for compaction recovery.

## Skill retrieval

`cs_skill_search` returns short cards only. `cs_skill_load` loads bounded views and rejects forged handles, path traversal, unknown ids, and full-view loads without explicit `allow_full=true`.

## Safety

- No all-tools/full-runtime MCP.
- Tool annotations expose read-only/destructive/idempotent/open-world hints.
- Outputs must be bounded and redacted.
- Errors return `ok=false`, `error_type`, `recoverable`, and a suggested next MCP action when useful.
- Missing tools fail closed: fix MCP/doctor/config or implement the missing MCP tool; do not switch the default research flow to terminal compatibility commands.
