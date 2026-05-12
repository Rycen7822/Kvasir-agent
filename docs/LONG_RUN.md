# Long Run Validation

Codex-Scientist is a Codex CLI plugin with a stable curated MCP control plane and `scripts/csctl.py` CLI fallback. Long-run validation must state whether each run used MCP, CLI fallback, or both.

## Validation layers

1. `accelerated soak`: CI-friendly fake-clock validation for ten equivalent days. It must inject heartbeat timeout, runner exit, queue retry terminal state, state reload, event replay, log compaction, and cost cap checks.
2. `overnight soak`: a local wall-clock run of at least 12 hours with real process/log/reconcile behavior.
3. `wall-clock soak`: a release validation of at least ten natural days.

The accelerated layer writes `CodexScientist/summaries/long_run_validation.md`:

```bash
python scripts/csctl.py soak accelerated --days 10 --inject-failures --format json
```

## Crash resume smoke

```bash
python scripts/csctl.py queue lease-next --worker-id worker-1 --ttl-seconds 30 --format json
python scripts/csctl.py soak crash-resume --restart-label plugin-restart --format json
```

Expired leases move to `reconcile_required`; they are not silently requeued as pending jobs.

## P3 recovery artifacts

Long-run recovery state is project-local under `CodexScientist/` and must never be committed into the plugin repository root. The important recovery files are:

- `events/events.jsonl` plus `events/events.lock` for append-only event sequencing and cross-process append safety;
- `events/corrupt/` for quarantined malformed JSONL lines;
- `runs/<run_id>/runner.json`, `runs/<run_id>/run.log`, `runs/<run_id>/stderr.log`, `runs/<run_id>/heartbeat.txt`, and `runs/<run_id>/exit_code.txt` for process lifecycle, bounded log digest, stderr digest, cross-process exit status recovery, and stale-run detection;
- `queue/queue_state.json` for job/run linkage, attempts, expected outputs, terminal status, and all_done_reason;
- `summaries/context_pack.md` and checkpoint records for context recovery.

## Recovery flow

Use the bounded MCP-first recovery path before reading raw files:

1. `cs_status` verifies the target project and state root.
2. `cs_resume_brief` reconstructs the current task in a normal 4K-8K recovery budget.
3. `cs_pack_delta` fetches post-checkpoint events when the latest brief is not enough.
4. `cs_log_digest` summarizes long logs and classifies common failures before any raw log read.
5. `cs_artifact_index` lists artifact path, type, size, and hash before opening full artifact content.
6. `cs_checkpoint` records completed stage boundaries and factual validation state.

Queue reconciliation classifies important stuck/failure states explicitly. Examples: `failed_artifact` for completed runs with missing expected outputs, `missing_heartbeat` for a running run whose heartbeat file vanished, and `reconcile_required` for expired leases or missing run snapshots.

## Claim limits

If the report says `wall-clock: not_run`, do not claim stable ten-day wall-clock operation. A passing accelerated soak is necessary for CI, but it is not a substitute for the real wall-clock soak.
