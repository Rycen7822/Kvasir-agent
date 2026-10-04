# PF-REAL-007 Repair Plan

规划文档状态：全部完成。
事实信心：100%。

## Problem

`tests/test_mini_cases_static.py` reads `worknotes/ponder_forge_smoke_report_template.md`, but `.gitignore` ignores `ponder-forge/worknotes/`. After legitimate worknotes cleanup, full source tests failed with `FileNotFoundError`.

This is not a runtime gate defect, but it is a real Ponder-Forge stability defect: a fresh checkout or cleaned workspace cannot reliably run the full test suite.

## Boundary

- Do not edit Hermes core.
- Do not edit idea-spark.
- Do not write under `/home/xu/project/loop/DeepScientist/quests/001`.
- Keep the fix local to tests/fixtures plus the one test reference.

## Owner seam

- Move the smoke report template content into a tracked test fixture under `tests/fixtures/ponder_forge_smoke_report_template.md`.
- Update `tests/test_mini_cases_static.py` to read that tracked fixture.
- Remove the restored ignored worknotes copy so future worknotes cleanup cannot affect the test.

## Verification

- Run `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_mini_cases_static.py -q`.
- Run the full source suite.
- Run installed-copy suite after copy install.

## Self-review

The plan is intentionally narrow. It does not change runtime behavior, plugin APIs, gates, renderer, or report ingest. It removes a hidden dependency on ignored scratch state and makes the full test suite reproducible in a clean checkout.
