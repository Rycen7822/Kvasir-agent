# Ponder-Forge Smoke Report Template

## Run metadata

- date:
- source_revision:
- install_path:
- install_is_symlink: false
- benchmark_summary_json:

## Metrics

- unsupported_assertion_rate:
- blocked_final_attempts:
- successful_finalizations:
- average_case_latency_seconds:
- live_delegate_status: not-run | passed | blocked | unavailable

## Profile results

| profile | status | final artifact | blocked reason |
|---|---|---|---|
| research |  |  |  |
| coding |  |  |  |
| design |  |  |  |
| analysis |  |  |  |
| math |  |  |  |

## Notes

- Source-level mocked benchmark proves profile gates and final renderer behavior.
- Live delegate smoke must be recorded separately; do not claim live readiness when `live_delegate_status` is `not-run` or `unavailable`.
