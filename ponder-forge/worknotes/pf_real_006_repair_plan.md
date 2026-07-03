# PF-REAL-006 Repair Plan

规划文档状态：全部完成。
事实信心：100%。根因和 owner seam 已明确：`ponder_forge_report_submit` 公开入口接受开放 JSON，但 `report_ingest.py` 只消费 canonical nested keys，导致 alias-shaped real report 静默丢证据。修复必须在 `report_ingest.py` 做窄规范化和验证，不改 Hermes core，不改 idea-spark，不引入通用 schema 框架。

## Goal

让真实 agent 提交的报告在 public tool seam 上稳定可靠：常见 alias payload 被窄规范化成 canonical Ponder-Forge report；无法安全规范化的 payload 在任何数据库 mutation 前失败，并返回明确错误。PF-REAL-006 修复后重新安装插件，重启 fresh real run，重新累计 clean passes。

## Evidence read

- `worknotes/tmp_pf_real_006_plan/00_scope_requirements.md`
- `worknotes/tmp_pf_real_006_plan/01_code_inventory.md`
- `report_ingest.py`: 当前只读取 `assertion_type`、`text`、`assertions[*].evidence`、`evidence_type`、`source_ref`、`quote_or_observation`、`artifact_type`。
- `schemas.py`: public schema 是 `additionalProperties: true`，不能靠 tool schema 阻止 field mismatch。
- `profiles.py`: analysis profile 的 critical type 是 `data_result`，gate 需要 metric_output + transform/reproduction + sanity evidence。
- `gates.py`: gate 只看已落库的 assertion/evidence rows；如果 ingest 静默丢 evidence，gate 只能产生误导性 gap。
- `tests/test_report_ingest.py` 和 `tests/test_tools_contract.py`: 覆盖 canonical payload，没有覆盖 alias/malformed payload。

## Architecture decision

修改 owner seam：`report_ingest.py` 在创建 report/assertion/evidence/artifact rows 前执行 payload normalization + validation。

不新增独立 schema engine，不改 SQLite schema，不改 profile/gate，不改 public tool registration，不改 Hermes core。原因：问题不是 gate 判定，也不是工具可见性；问题是 report ingest 接受开放 payload 后没有稳定 contract boundary。

## Exact behavior

### Accepted alias normalization

在 `report_ingest.py` 增加小 helper：

1. assertion aliases:
   - `assertion_type` 保持 canonical。
   - `type` 作为 `assertion_type` alias。
   - `statement` 作为 `text` alias。
   - `evidence_refs` 保留在 raw，不用于建 evidence rows。
   - `critical`、`importance`、`confidence` 原样保留。
2. evidence aliases:
   - canonical nested `assertions[*].evidence` 保持原样。
   - 若 assertion 没有 nested `evidence`，允许用 top-level `evidence`/`evidence_items` 按 `id` 与 assertion 的 `evidence_refs` 匹配并嵌入。
   - `type` 作为 `evidence_type` alias。
   - `source` 作为 `source_ref` alias。
   - `summary` 作为 `quote_or_observation` alias。
   - `path` 作为 `artifact_path` alias only when evidence has no `artifact_path`.
3. artifact aliases:
   - `artifact_type` 保持 canonical。
   - `kind` 作为 `artifact_type` alias。
   - `description` 作为 `summary` alias。

### Fail-loud validation

在写数据库前验证：

- 每个 assertion 必须有非空 `assertion_type` 和非空 `text`。
- 如果 payload 中存在 top-level `evidence`/`evidence_items`，但没有任何 assertion 通过 nested evidence 或 `evidence_refs` 消费它们，抛出 `ValueError`，错误文本包含 `unlinked evidence`。
- 如果 assertion 声明了 `evidence_refs` 但找不到对应 top-level evidence id，抛出 `ValueError`，错误文本包含 `missing evidence_refs`。
- 不要求每个 assertion 都有 evidence；一些 reviewer/verdict report 可以只写 summary/artifact。但如果用户显式传了 evidence，不能静默丢弃。

## Implementation steps

1. Add tests first.
   - `tests/test_report_ingest.py::test_ingest_report_normalizes_alias_payload_with_top_level_evidence`
   - `tests/test_report_ingest.py::test_ingest_report_rejects_unlinked_top_level_evidence`
   - `tests/test_report_ingest.py::test_ingest_report_rejects_missing_evidence_ref`
2. Run the three tests and confirm RED before code change.
3. Patch `report_ingest.py` with small helpers:
   - `_first_nonempty`
   - `_normalize_evidence_payload`
   - `_normalize_artifact_payload`
   - `_normalize_assertion_payloads`
   - `_normalize_payload`
4. Use normalized payload for `create_report`, assertion/evidence/artifact loops, and report raw JSON.
5. Run focused tests.
6. Run full source tests with `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q`.
7. Run `python3 -m compileall -q .`.
8. Copy install with `python3 scripts/copy_install_smoke.py --target /home/xu/.hermes/plugins/ponder_forge`.
9. Run installed-copy tests and compileall.
10. Restart real-run loop from a new fresh run. The contaminated `pf_run_496b1615dbc7` remains evidence for PF-REAL-006 and does not count as clean.

## Verification gates

- Alias-shaped Round 4 payload must create non-empty `evidence_ids` and a `data_result` critical assertion.
- Malformed payloads must fail before mutation; row counts must not increase.
- Source and installed copy tests must pass.
- New fresh real run must prove start/plan/prepare/report/verify/gate/finalize/immutability with the fixed installed plugin.

## Non-goals

- No Hermes core edit.
- No idea-spark edit.
- No broad JSON schema framework.
- No automatic guessing from arbitrary natural-language fields beyond the listed aliases.
- No quest path writes.

## Confidence review

I am factually 100% confident in this plan because the real failure maps directly to the only owner seam that can prevent silent evidence loss before state mutation. The fix is narrow, testable, and does not duplicate gate or profile logic. The only remaining uncertainty is whether background Round 4 children started before the fix submit stale malformed reports; that is handled operationally by marking Round 4 first attempt non-clean and restarting fresh after installation.
