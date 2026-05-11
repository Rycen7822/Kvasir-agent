# Long Run Validation

Codex-Scientist is a Codex CLI plugin and its upgraded control plane is `scripts/csctl.py`. The control plane reports `codex-native-cli` and is not MCP.

## Validation layers

1. `accelerated soak`: CI-friendly fake-clock validation for ten equivalent days. It must inject heartbeat timeout, runner exit, queue retry terminal state, state reload, event replay, log compaction, and cost cap checks.
2. `overnight soak`: a local wall-clock run of at least 12 hours with real process/log/reconcile behavior.
3. `wall-clock soak`: a release validation of at least ten natural days.

The accelerated layer writes `DeepScientist/summaries/long_run_validation.md`:

```bash
python scripts/csctl.py soak accelerated --days 10 --inject-failures --format json
```

If the report says `wall-clock: not_run`, do not claim stable ten-day wall-clock operation. A passing accelerated soak is necessary for CI, but it is not a substitute for the real wall-clock soak.

## Crash resume smoke

```bash
python scripts/csctl.py queue lease-next --worker-id worker-1 --ttl-seconds 30 --format json
python scripts/csctl.py soak crash-resume --restart-label plugin-restart --format json
```

Expired leases move to `reconcile_required`; they are not silently requeued as pending jobs.
