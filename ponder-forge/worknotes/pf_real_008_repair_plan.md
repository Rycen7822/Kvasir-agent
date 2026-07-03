# PF-REAL-008 Repair Plan

规划文档状态：全部完成。
事实信心：100%。

## Problem

A real clean run reached `gate_status=passed`, but the returned metrics still reported:

- `independent_review_coverage: 0.0`
- `artifact_reproducibility_coverage: 0.0`
- `final_statement_trace_coverage: 0.0`

`gates.py` also sets `unsupported_critical_assertions = len(gaps)`, which can exceed the number of critical assertions because one assertion can produce multiple gaps.

This does not mis-block or mis-pass the gate, but it makes the status surface untrustworthy for operators and long-running stability decisions.

## Boundary

- Do not alter gate pass/fail semantics.
- Do not change profiles or required evidence groups.
- Do not touch renderer output semantics.
- Do not edit Hermes core, idea-spark, or the quest path.

## Owner seam

Only `gates.py` owns these metrics. The fix belongs inside `evaluate_gate` after each critical assertion is evaluated.

## Implementation

1. Track per-critical-assertion booleans:
   - has required profile evidence
   - has accepted independent reviewer verdict
   - parent report has at least one artifact
2. Compute:
   - `unsupported_critical_assertions`: number of critical assertions missing required profile evidence.
   - `blocking_gap_count`: total gate gaps, preserving the old operational count under a truthful name.
   - `independent_review_coverage`: accepted independent verdict count / critical count.
   - `artifact_reproducibility_coverage`: artifact-backed critical assertion count / critical count.
   - `final_statement_trace_coverage`: assertions that are both supported and independently accepted / critical count.
3. Keep all zero when there are no critical assertions.

## Tests

- Add a RED test proving a passed gate reports independent/final trace coverage as `1.0` and artifact coverage as `1.0` when the accepted critical assertion's report has an artifact.
- Add a RED test proving an assertion with both missing evidence and missing independent verdict yields `unsupported_critical_assertions == 1` and `blocking_gap_count == 2`.
- Run focused gate tests, full suite, compileall, copy install, installed-copy suite, then rerun one fresh installed real workflow probe or gate check.

## Self-review

This is narrow and not overdesigned. It does not invent new verifier behavior; it only makes already-returned metrics reflect the state Ponder-Forge already uses for gate decisions and final rendering.
