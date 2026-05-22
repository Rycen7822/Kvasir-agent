# Long Run Validation

CodexScientist is a Codex CLI plugin with an MCP-only default research control plane. Long-run validation records whether each run used MCP-only default tools, hidden admin/debug compatibility commands, or both; default Codex research work should use MCP tools and project-local state.

## Validation layers

1. `accelerated soak`: CI-friendly fake-clock validation for ten equivalent days. It must inject heartbeat timeout, runner exit, queue retry terminal state, state reload, event replay, log compaction, passive checkpoint recovery, manual watchdog diagnostics, and cost cap checks.
2. `overnight soak`: a local wall-clock run of at least 12 hours with real process/log/reconcile behavior.
3. `wall-clock soak`: a release validation of at least ten natural days.

The accelerated layer writes `CodexScientist/summaries/long_run_validation.md` and must mark real wall-clock coverage as `wall-clock: not_run` unless a real wall-clock soak was actually executed.

## Crash resume smoke

A crash/resume smoke should demonstrate that a stuck or interrupted run can be recovered without chat history:

1. create or load a quest;
2. start a runner or simulate a runner heartbeat gap;
3. inspect public recovery state through `cs_status` and `cs_resume_brief`;
4. run hidden/admin-only watchdog diagnostics only in explicit admin/CI validation, without writing a `runner_stuck` goal gate;
5. call `cs_resume_brief` and verify `active_run_id`, passive `recovery_anchor`, and `source_refs` are present;
6. call `cs_checkpoint` after the bounded recovery action is complete.

Expired leases move to `reconcile_required`; they are not silently requeued as pending jobs.

## Recovery artifacts

Long-run recovery state is project-local under `CodexScientist/` and must never be committed into the plugin repository root. Important files include:

- `events/events.jsonl` plus `events/events.lock` for append-only event sequencing and cross-process append safety;
- `events/corrupt/` for quarantined malformed JSONL lines;
- `runs/<run_id>/runner.json`, `runs/<run_id>/run.log`, `runs/<run_id>/stderr.log`, `runs/<run_id>/heartbeat.txt`, and `runs/<run_id>/exit_code.txt` for process lifecycle, bounded log digest, stderr digest, cross-process exit status recovery, and stale-run detection;
- `summaries/checkpoints.jsonl` and `summaries/latest_checkpoint.json` for passive checkpoint anchors;
- `queue/queue_state.json` for job/run linkage, attempts, expected outputs, terminal status, and all_done_reason;
- `summaries/context_pack.md` and checkpoint records for context recovery.

## Watchdog/checkpoint/resume contract

Use the bounded MCP-first recovery path before reading raw files:

1. `cs_status` verifies the target project and state root.
2. `cs_resume_brief` reports current quest state, active run id, passive recovery anchor, and source refs.
3. `cs_pack_delta` fetches post-checkpoint events when the latest brief is not enough.
4. `cs_log_digest` summarizes long logs and classifies common failures before any raw log read.
5. `cs_artifact_index` lists artifact path, type, size, and hash before opening full artifact content.
6. Hidden/admin-only watchdog diagnostics may be used in explicit admin/CI validation for runner heartbeat and stuck-state questions, without writing goal gates.
7. `cs_checkpoint` records completed stage boundaries and factual validation state.

State-changing MCP tools do not auto-inject checkpoint gates. Recovery payloads should remain passive and may return:

- `recovery_anchor`: the latest factual checkpoint anchor;
- `active_run_id`: the run id to inspect after crash/restart recovery;
- `source_refs`: state files used to build the recovery view;
- bounded log or artifact summaries when explicitly requested.

Queue reconciliation classifies important stuck/failure states explicitly. Examples: `failed_artifact` for completed runs with missing expected outputs, `missing_heartbeat` for a running run whose heartbeat file vanished, `runner_stuck` for stale active runners, and `reconcile_required` for expired leases or missing run snapshots.

## Claim limits

If the report says `wall-clock: not_run`, do not claim stable ten-day wall-clock operation. A passing accelerated soak is necessary for CI, but it is not a substitute for the real wall-clock soak.
