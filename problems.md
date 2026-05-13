# Codex-Scientist upgrade 6 full-function simulation problems and fixes

更新时间：2026-05-13 21:46 CST+0800
测试对象：当前 `main` 分支升级后的 Codex-Scientist 工作区
测试方式：模拟 Codex 通过 MCP stdio smoke / native CLI 使用插件；运行态写入 `/tmp` 临时项目，不写入仓库运行态。

## 0. 当前修复状态

本轮根据 2026-05-13 20:56 的全功能模拟测试问题清单完成修复。

已修复：

1. `docs/USAGE.md` 与升级 6 实际 profile / tool surface 不一致。
2. MCP 参数 `project` / `project_root` 混用时可能回落到当前工作目录并生成仓库内运行态。
3. `cs_tool_schema` 描述为“任意 MCP tool schema”，但此前只覆盖 runtime/native schema。
4. `cs_paper_reliability_verify` 对 URL-only 外部检查缺少 bounded / dry-run / fail-fast 行为。
5. `cs_submit_paper_outline` 对 `detailed_outline` 列表形状返回 Python 内部异常文本。
6. baseline gate 错误提示引用内部 API 名称 `artifact.confirm_baseline(...)` / `artifact.waive_baseline(...)`。
7. `cs_submit_idea` 缺 nested novelty contract 字段时缺少可执行 retry template。
8. native CLI 与 MCP-only core 工具边界不清，`cs_status` native 调用容易被误解为工具不存在。

新增回归测试：

- `tests/test_problems_md_regressions.py`
  - docs/profile contract stale phrase 检查。
  - `project_root` alias 不写入 cwd 检查。
  - `cs_tool_schema` 覆盖所有 admin tool 的最小 schema 检查。
  - paper reliability dry-run / network=false bounded 检查。
  - paper reliability URL-only 默认网络模式 fail-fast 检查。
  - paper outline `list[str]` 规范化检查。
  - baseline gate MCP 工具名 guidance 检查。
  - idea novelty nested retry template 检查。
  - native CLI `cs_status` boundary hint 检查。

同步更新测试：

- `tests/test_mcp_stress_regression.py`
  - 将旧的 `cs_status` schema miss 合同改为 registry-minimal schema 合同。

## 1. 验收基线与最终验证

仓库：`/home/xu/project/autoscientist/Codex-Scientist`

最终已运行：

```bash
python -m pytest tests/test_problems_md_regressions.py tests/test_docs_long_run_migration.py tests/test_mcp_stress_regression.py -q
python -m pytest -q
python scripts/p4_acceptance.py
```

结果：

- 定向回归：13 passed in 1.33s。
- 全量 pytest：242 passed in 30.75s。
- P4 acceptance：47 targeted tests passed；MCP `tools/list` / `initialize` smoke passed；agent-facing CLI violations 0；`P4 acceptance passed`。

额外 Codex/MCP smoke：

- 正向路径已验证：`cs_new_quest`、`cs_create_local_baseline`、`cs_confirm_baseline`、完整 `cs_submit_idea`、`cs_record_main_experiment`、`cs_create_analysis_campaign`、`cs_paper_reliability_verify(dry_run=true, network=false)`。
- fail-fast 路径已验证：`cs_paper_reliability_verify` 对 URL-only 默认网络模式快速返回 `error_type=external_io_requires_bounded_mode`，不再 timeout。
- 仓库运行态副作用：未生成仓库内 `CodexScientist/` 目录。

## 2. 模拟测试范围

模拟入口：

- MCP stdio helper：`python scripts/cs_mcp.py --stdio-smoke call <tool> <json>`。
- Native CLI：`python scripts/cs_native_cli.py --format json call <tool> --json <json>`。
- 临时项目：`/tmp/cs_*`。

覆盖面：

- profile 暴露面：`core`、`evidence`、`formal_run`、`literature`、`paper_write`、`goal`、`autonomous`、`admin`、`legacy_compat`。
- 代表性 MCP 功能域：quest、checkpoint/resume/context pack、quest memory、manifest、baseline、artifact、runner/queue/log digest、experiment、analysis、claim gate、bash formal provenance gate、idea/method frontier、strict research/literature/paper、skill retrieval、legacy/autonomous diagnostic、trial、cost、soak、wiki。
- 安全 gate：global memory fail-closed、bash run without formal provenance fail-closed、invalid log run fail-closed、paper reliability URL-only fail-fast。
- 文档一致性：`docs/USAGE.md` 与实际 profile/tool surface 对照。
- 仓库副作用：模拟后仓库根目录不得生成 `CodexScientist/` 运行态目录。

## 3. 问题与修复记录

### P1-1. `docs/USAGE.md` 与升级后实际工具面不一致

原问题：

- 文档仍写默认 `tools/list` 返回 14-tool core profile、goal profile 47 tools、按 active stage subset 过滤。
- 实际为 `core=11`、`evidence=31`、`formal_run=32`、`literature=23`、`paper_write=27`；`goal` 已 deprecated；stage 只是 label。
- 文档仍暗示默认 progress watchdog state 和旧 goal context / allowed_tools_for_stage。
- 文档建议 `cs_skill_search/load`，但这些不是默认 profile tool。

修复：

- 重写 `docs/USAGE.md` 的默认控制面说明。
- 明确 Codex-native `/goal` 是 planner，CodexScientist 只记录 evidence / recovery anchors。
- 明确 stage label-only。
- 明确 manual watchdog diagnostic，而不是默认 watchdog state writes。
- 明确 `cs_skill_search/load` 是 hidden/direct compatibility/debug surface，不属于默认 Codex-facing control plane。

验证：

- `test_usage_doc_matches_upgrade6_profile_contract`。
- `test_docs_long_run_migration.py`。
- P4 no CLI surface scan。

状态：已修复。

### P1-2. MCP 参数名 `project` / `project_root` 不一致

原问题：

- 部分 registry handler 只读取 `project`。
- 如果 client 使用 `project_root`，会回落到 cwd，在插件仓库根目录生成 `CodexScientist/` 运行态。

修复：

- 在 `codex_scientist/mcp/tool_registry.py` 增加统一 `_project_root_arg()`。
- `_layout()`、`_simple_status()` 等 registry 入口接受 `project` 和 `project_root` 两个别名。
- retry/template 的 known args 也保留 `project_root`。
- `docs/USAGE.md` 明确 `project` 为首选，`project_root` 为兼容别名。

验证：

- `test_project_root_alias_is_honored_and_does_not_write_to_cwd`。
- 正向 smoke 后确认仓库内无 `CodexScientist/`。

状态：已修复。

### P1-3. `cs_tool_schema` 覆盖范围不完整

原问题：

- `cs_tool_schema` 描述为返回 MCP tool schema，但此前只覆盖 runtime/native schema。
- 对 `cs_status`、`cs_context_pack`、`cs_checkpoint`、queue/runner/trial/goal/soak/wiki 等 registry-only tools 返回 `unknown_tool`。

修复：

- `tool_registry.py` 新增 registry fallback schema。
- `cs_tool_schema` 现在先返回 runtime/native detailed schema；若不存在，则从 ToolSpec 构造 minimal registry schema。
- minimal schema 包含 `name`、`description`、`input_schema.required`、annotations、group、read_only/destructive/idempotent/open_world 等信息。

验证：

- `test_tool_schema_returns_minimal_schema_for_every_registered_tool` 遍历 admin profile 全部工具。
- `tests/test_mcp_stress_regression.py` 同步新合同。

状态：已修复。

### P1-4. `cs_paper_reliability_verify` URL-only 外部检查可能卡住

原问题：

- 模拟调用 `title + url=https://example.com/toy` 时子进程 timeout。
- 工具缺少清晰 bounded / dry-run / network=false / fail-fast 行为。

修复：

- `tool_registry.py` 增加 `_paper_reliability_preflight()`。
- 支持 `dry_run=true` 或 `network=false`：返回计划、所需证据和下一步建议，不执行外部 verifier，不写 reliability card。
- 对 URL-only 且未提供 DOI/arXiv identifier 的默认网络模式 fail-fast：返回 `ok=false`、`error_type=external_io_requires_bounded_mode`、`recoverable=true` 和 bounded retry template。
- `runtime/schemas.py` 增加 `url`、`dry_run`、`network`、`timeout_seconds` 字段说明。
- `docs/USAGE.md` 增加 open-world literature checks 的 bounded 使用说明。

验证：

- `test_paper_reliability_verify_supports_bounded_dry_run`。
- `test_paper_reliability_verify_external_url_without_bounded_mode_fails_fast`。
- 正向 smoke 验证 dry-run；fail-fast smoke 验证 URL-only 不再 timeout。

状态：已修复。

### P1-5. `cs_submit_paper_outline` 对 `detailed_outline` 错误不结构化

原问题：

- `detailed_outline` 传 `list[str]` 时返回 Python 内部异常：`dictionary update sequence element #0 has length ...`。

修复：

- `runtime/tools.py` 增加 `_normalize_mcp_detailed_outline()`。
- 接受：
  - object；
  - `list[str]`，规范化为 `experimental_designs`；
  - `list[dict]`，规范化为 `sections`。
- 对其他非法形状返回结构化 `invalid_argument` 和 retry_template。
- `runtime/schemas.py` 将 `detailed_outline` 类型更新为 object 或 array，并补说明。

验证：

- `test_submit_paper_outline_accepts_string_list_as_section_titles`。

状态：已修复。

### P2-1. Baseline gate 错误信息仍引用内部 API

原问题：

- `cs_record_main_experiment` / `cs_create_analysis_campaign` 的 gate 错误提示引用 `artifact.confirm_baseline(...)` / `artifact.waive_baseline(...)`。
- `baseline_path` 需要位于 quest_root 的约束不够可执行。

修复：

- `tool_registry.py` 的 failure envelope normalization 将内部 API 文案替换为 MCP 工具名 `cs_confirm_baseline` / `cs_waive_baseline`。
- `cs_confirm_baseline` 的 path 错误补 `retry_template` 和 `suggested_next_action`，指向 `cs_create_local_baseline`。

验证：

- `test_baseline_gate_errors_use_mcp_tool_guidance`。
- 旧模拟脚本仍把 quest_root 外 baseline 当作 ok 预期，因此仍显示 contract_fail；这是正确 fail-closed，不再是产品缺陷。

状态：已修复。

### P2-2. Idea novelty contract nested required 字段不易发现

原问题：

- 顶层 schema 只显示 `quest_id/title/novelty_contract`。
- 缺 `novelty_contract.mechanism` 时需要失败一次才知道 nested 必填。

修复：

- `research_tools.py` 增加 `_novelty_contract_retry_payload()`。
- 缺 nested 字段时返回 `retry_template.minimal_novelty_contract`，包含 `mechanism`、`related_work_refs`、`expected_difference`。
- `suggested_next_action` 明确指出缺失字段。

验证：

- `test_submit_idea_missing_nested_contract_fields_returns_retry_template`。
- 正向 smoke 用完整 novelty_contract 通过。
- 旧模拟脚本传旧字段名 `claim/difference` 时仍 fail-closed；这是正确行为。

状态：已修复。

### P2-3. Native CLI 与 MCP-only core 工具边界容易误解

原问题：

- `scripts/cs_native_cli.py --format json call cs_status ...` 返回 unknown tool。
- 用户可能误以为 `cs_status` 不存在。

修复：

- `scripts/cs_native_cli.py` 增加轻量 `cs_status` handler。
- 返回 project、state_root、state_root_exists，并明确提示默认 MCP registry surface 应通过 `scripts/cs_mcp.py` 使用。
- 保持 native CLI 非默认控制面，不恢复 legacy alias 自动映射。

验证：

- `test_native_cli_accepts_cs_status_as_lightweight_mcp_boundary_hint`。
- `test_upgrade6_admin_legacy_sunset.py` 仍通过。

状态：已修复。

## 4. 当前剩余注意点

1. 旧的 `/tmp/codex_scientist_codex_simulation_final.py` 是临时模拟脚本，不属于仓库测试资产；它仍用部分修复前参数和旧判断统计，例如把 quest_root 外 baseline confirm、缺 mechanism idea submit 当作应当 ok 的正向路径。该脚本重跑时剩余 contract_fail 属于预期 fail-closed，不再作为产品缺陷。
2. `cs_tool_schema` 对 registry-only 工具返回的是 minimal schema，不是 runtime/native detailed schema。这是为了保持 context budget；若未来需要更完整参数 schema，应逐步扩展 ToolSpec，而不是恢复 all-tools heavy payload。
3. `cs_paper_reliability_verify` 的完整 DOI/arXiv verifier 路径仍可能执行外部/open-world 检查；当前修复保证 URL-only 任意外部链接不再无界卡住，并提供 bounded dry-run/network=false 路径。

## 5. 本轮结论

升级后的 Codex-Scientist 经过全功能模拟后暴露的 8 类问题已完成修复，并补充了自动化回归测试。当前默认 MCP 面仍保持升级 6 的边界：薄 core、profile-driven、stage label-only、无默认 planner/watchdog state 写入、quest-local memory、formal bash provenance gate、legacy alias 默认拒绝。

最终验证为绿色：定向回归 13 passed，全量 pytest 242 passed，P4 acceptance passed，额外正向 Codex/MCP smoke passed。