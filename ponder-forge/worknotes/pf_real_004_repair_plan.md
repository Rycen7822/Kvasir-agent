# PF-REAL-004 Repair Plan

规划文档状态：全部完成。
事实信心：100%。这是 public tool lifecycle bug：completed run 已由 `store.update_final_report` 标记，但 `ponder_forge_report_submit` 和 `ponder_forge_finalize` 没有尊重 completed 状态。修复只在 `tools.py` public tool seam，不改 store schema，不做 daemon/queue/polling。

## Goal

让 Ponder-Forge completed run 不再被 late child reports 污染，并让 repeated finalize 对 completed run 幂等返回已有 final artifact。

## Architecture

使用现有 `runs.status=completed` 和 `runs.final_report_md` 作为 lifecycle boundary。

- `ponder_forge_report_submit`: completed run is closed to new reports.
- `ponder_forge_finalize`: completed run with stored final is already final; return stored final and paths.
- `render_final_report`: 继续负责从当前 accepted graph 生成 final；不承担 lifecycle enforcement。

## Implementation tasks

### Task 1 — Add lifecycle RED coverage

Modify `tests/test_tools_contract.py` public tool chain test:

1. Finalize once.
2. Call `ponder_forge_finalize` again and assert it still returns `status=final`, `final_report_markdown`, and `artifact_paths.final_md`.
3. Call `ponder_forge_report_submit` after final and assert `success=false`, error mentions completed/closed, and `pool_status.counts.reports` remains unchanged.
4. Keep existing final text assertions plus the PF-REAL-003 evidence trace assertions.

### Task 2 — Implement public lifecycle guard

Modify `tools.py`:

- add helper `_final_artifact_paths(store, run_id)`;
- add helper `_completed_final_payload(store, run)`;
- in `ponder_forge_report_submit`, reject completed run before `ingest_report`;
- in `ponder_forge_finalize`, return completed final payload before `evaluate_gate`.

### Task 3 — Verify and reinstall

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_tools_contract.py tests/test_gates_profiles.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge
cd /home/xu/.hermes/plugins/ponder_forge && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
```

## Confidence review

No ambiguity remains. The completed status is already persisted and is the correct owner of final-run immutability. The implementation is small, lifecycle-specific, and avoids overdesign.
