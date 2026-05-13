# Codex-Scientist simulation problems

更新时间：2026-05-13 23:17 CST+0800
仓库：`/home/xu/project/autoscientist/Codex-Scientist`
用途：记录升级 6 后，用真实 Codex / MCP 用户路径模拟插件时发现的问题、修复状态、证据与验证命令。

## 0. 历史已修复摘要

上一轮全功能模拟发现的 8 类问题已修复并提交（commit `8fe60898346a33adf45ab97882fe73ce2b2d0b14`）：

- `docs/USAGE.md` 旧 profile / tool surface 描述已更新。
- MCP `project` / `project_root` alias 已统一，避免运行态误写仓库 cwd。
- `cs_tool_schema` 已为 registry-only tools 提供 minimal schema fallback。
- `cs_paper_reliability_verify` 已支持 bounded dry-run / network=false，并对 URL-only 默认外部 IO fail-fast。
- `cs_submit_paper_outline` 已规范化 `detailed_outline` list 输入并返回结构化错误。
- baseline gate 错误提示已改为 MCP 工具名 guidance。
- `cs_submit_idea` 缺 nested novelty contract 时已返回 retry template。
- native CLI 已提供轻量 `cs_status` 边界提示。

历史验证：定向回归 13 passed；全量 pytest 242 passed；P4 acceptance passed；已 push 到 `origin/main`。

## 1. 本轮模拟方法

2026-05-13 22:10 -> 22:32，按用户要求重新从更接近真实用户的 Codex 视角模拟插件使用：

1. 先压缩本文档，避免把已修复历史问题当成当前 blockers。
2. 使用干净上下文 subagent / 临时 workspace 测试 Codex 正常使用路径，而不只直接 import Python handler。
3. 对非通过项分类为产品问题、文档问题、预期 fail-closed、探针错误或设计约束。
4. 模拟后检查仓库不应产生 `CodexScientist/` 运行态副作用。

本轮 subagent findings 原始记录：

- `/tmp/codex_scientist_subagent_install_codex_findings.md`
- `/tmp/codex_scientist_subagent_mcp_workflow_findings.md`
- `/tmp/codex_scientist_subagent_docs_findings.md`

## 2. 本轮基线与主路径结果

基线命令：

```bash
python -m pytest tests/test_problems_md_regressions.py tests/test_docs_long_run_migration.py tests/test_mcp_stress_regression.py -q
python scripts/p4_acceptance.py
python scripts/cs_mcp.py --stdio-smoke tools/list
```

基线结论：

- MCP server 入口可用：initialize/tools-list/cs_doctor 均 ok。
- 小型 quest 主路径可用：quest、requirement、baseline、idea、experiment、analysis、memory、checkpoint/resume/delta、bounded paper reliability dry-run 均通过。
- 预期 fail-closed 正常：global memory、缺 provenance 的 bash run、证据不足 claim gate 均被拒绝。
- 未发现仓库根目录生成 `CodexScientist/` 或 `.codex/CODEXSCIENTIST_CODEX.md` 运行态污染。

## 3. 本轮发现问题与修复状态

### P1-1. 安装后没有把 MCP server 接入 Codex CLI

状态：已修复。

修复：

- `scripts/install.sh` 现在在安装后写入 `[mcp_servers.codexscientist-codex]`，指向安装副本的 `scripts/cs_mcp.py`。
- 安装输出提示 `codex mcp list && codex mcp get codexscientist-codex` 验证链路。
- `docs/INSTALL.md` / README / README.zh-CN 已把 MCP 注册列为安装结果，并提供等价手动命令：
  `codex mcp add codexscientist-codex -- python ~/.codex/plugins/codexscientist-codex/scripts/cs_mcp.py`。

回归：`tests/test_codex_user_path_fixbacks.py::test_installer_registers_codex_mcp_server_and_keeps_install_tree_clean`。

### P1-2. `scripts/init_project.sh` 生成 no-MCP/native-only 项目提示

状态：已修复。

修复：

- `scripts/init_project.sh` 生成 `CodexScientist Codex MCP Project Note`。
- 删除默认 `No MCP transport is used`、`Native control script` 和 `scripts/csctl.py doctor` 提示。
- 项目 note 改为 MCP-first smoke：initialize、tools/list、call cs_doctor。

回归：`tests/test_codex_user_path_fixbacks.py::test_init_project_writes_mcp_first_project_note`。

### P1-3. README / README.zh-CN / docs/MCP.md 残留旧 profile、stage subset、旧工具入口

状态：已修复。

修复：

- README / README.zh-CN / docs/MCP.md / docs/ARCHITECTURE.md / docs/MCP_CONTEXT_BUDGET.md / docs/INSTALL.md / docs/USAGE.md 已统一到升级 6 表述。
- 默认 core profile 现在记录为 11 tools。
- 显式 profile 记录为 `evidence`、`formal_run`、`literature`、`paper_write`。
- `stage` 记录为 context/record label，不再描述为工具列表过滤器。
- 默认用户入口不再推荐 `cs_goal_context`。

当前真实 profile 盘点：`core=11`、`evidence=33`、`formal_run=34`、`literature=23`、`paper_write=27`；`goal` 是 deprecated compatibility alias for `evidence`。

回归：

- `tests/test_codex_user_path_fixbacks.py::test_user_entry_docs_have_current_upgrade6_profile_contract`
- `tests/test_docs_context_budget.py`
- `tests/test_docs_p4_contract.py`

### P1-4. 打包 skill 名称超出 Codex 限制，导致 paper reliability skill 未加载

状态：已修复。

修复：

- `skills/codexscientist-paper-reliability-verification/SKILL.md` frontmatter name 改为 `cs-paper-reliability`。
- namespaced skill name `codexscientist-codex:cs-paper-reliability` 低于 Codex 64 字符限制。

回归：`tests/test_codex_user_path_fixbacks.py::test_packaged_skill_names_fit_codex_namespace_limit`。

### P1-5. 插件 `defaultPrompt` 太长，Codex 返回为 null

状态：已修复。

修复：

- `.codex-plugin/plugin.json` 的 `interface.defaultPrompt` 改为 3 条短 prompt，每条不超过 128 字符。
- 内容保留 MCP-only default、`/goal` Codex-native、routine work Codex-native / `cs_bash_exec` formal provenance only 的核心边界。

回归：`tests/test_codex_user_path_fixbacks.py::test_manifest_default_prompts_fit_codex_plugin_limits`。

### P1-6. `skills/codexscientist-codex/SKILL.md` 默认流程推荐 hidden skill tools

状态：已修复。

修复：

- 主 router skill 删除默认 `cs_skill_search` / `cs_skill_load` 指引。
- 默认流程改为 visible MCP surface：tools/list -> `cs_status`/`cs_doctor` -> `cs_new_quest` / `cs_record_user_requirement` -> 选择显式 profile -> profile 内工具。
- 支持 skill 改由 Codex plugin skill mechanism 加载，而不是默认 MCP profile tools。

回归：`tests/test_codex_user_path_fixbacks.py::test_router_skill_default_flow_uses_visible_profile_tools_not_hidden_skill_helpers`。

### P2-1. `evidence` / `formal_run` profile 暴露 analysis slice 但不暴露 campaign create/read

状态：已修复。

修复：

- `codex_scientist/profiles.py` 将 `cs_create_analysis_campaign` 和 `cs_get_analysis_campaign` 加入 evidence additions。
- `formal_run` 继承 evidence，因此同样可见。

回归：`tests/test_codex_user_path_fixbacks.py::test_analysis_campaign_creator_is_visible_when_slice_recorder_is_visible`。

### P2-2. `cs_bash_exec` schema 未暴露 formal provenance gate 的实际字段

状态：已修复。

修复：

- `codex_scientist/runtime/schemas.py` 的 `CS_BASH_EXEC` schema 增加 `command_class`、`provenance_reason`、`experiment_or_artifact_id`、`cwd_policy`、`expected_outputs`、`evidence_paths`。
- schema description 明确 `operation=run` 是 formal provenance tool，不是 general shell。

回归：`tests/test_codex_user_path_fixbacks.py::test_bash_exec_schema_exposes_formal_run_provenance_fields`。

### P2-3. 插件安装/发现状态对普通 CLI 用户不透明

状态：已缓解，仍受 Codex CLI 上游能力限制。

修复/说明：

- 文档现在明确推荐 `codex mcp list` / `codex mcp get codexscientist-codex` 作为可用验证链路。
- installer 输出这些验证命令。
- 当前 Codex CLI 仍缺公开 `plugin list/status` 命令；这属于上游 CLI 限制，本文档不再声称普通 CLI 能直接查看 plugin installed 状态。

### P3-1. `--stdio-smoke tools/list` 不能传 profile 参数

状态：已修复。

修复：

- `scripts/cs_mcp.py --stdio-smoke tools/list '{"profile":"evidence"}'` 现在会把 JSON 参数传给 `tools/list`。

回归：`tests/test_codex_user_path_fixbacks.py::test_stdio_smoke_tools_list_accepts_profile_json_argument`。

### P3-2. Installer 运行 doctor 后安装目录含 `__pycache__`

状态：已修复。

修复：

- installer 运行 doctor 时设置 `PYTHONDONTWRITEBYTECODE=1`。
- 非源码原地安装时，doctor 后清理安装副本内 `__pycache__` 和 `*.pyc`。

回归：`tests/test_codex_user_path_fixbacks.py::test_installer_registers_codex_mcp_server_and_keeps_install_tree_clean`。

## 4. 本轮新增/更新回归

新增主回归：

```bash
python -m pytest tests/test_codex_user_path_fixbacks.py -q
```

覆盖：installer MCP 注册、init_project MCP note、用户入口文档合同、plugin defaultPrompt 长度、skill namespace 长度、router skill 可见工具路径、analysis campaign profile 可见性、bash provenance schema、profile-aware stdio smoke。

同步更新旧合同测试：

- `tests/test_codex_adapter_contract.py`
- `tests/test_docs_context_budget.py`
- `tests/test_docs_p4_contract.py`
- `tests/test_mcp_stress_regression.py`

## 5. 验证记录

已通过的定向验证：

```bash
python -m pytest tests/test_codex_user_path_fixbacks.py -q
python -m pytest tests/test_codex_user_path_fixbacks.py tests/test_codex_adapter_contract.py tests/test_docs_context_budget.py tests/test_docs_p4_contract.py tests/test_mcp_goal_tool_surface.py tests/test_no_cli_prompt_surface.py tests/test_docs_long_run_migration.py tests/test_mcp_stress_regression.py -q
git diff --check
python -m pytest -q
python scripts/p4_acceptance.py
```

当前结果：

- `tests/test_codex_user_path_fixbacks.py`：9 passed。
- 合并定向旧/新合同：58 passed（含 problems regression / docs / profile / stress / router surface 相关测试）。
- 全量 pytest：251 passed。
- P4 acceptance：47 targeted tests passed；MCP tools/list / initialize smoke passed；agent-facing CLI violations 0；`P4 acceptance passed`。
- `git diff --check`：无输出。

干净 HOME 安装/MCP smoke：

- 在临时 `HOME` / `CODEX_HOME` / `AGENTS_HOME` 下运行 `bash scripts/install.sh`。
- 安装副本写入 `[plugins."codexscientist-codex@local-personal"]` 和 `[mcp_servers.codexscientist-codex]`。
- 安装副本 `scripts/cs_mcp.py --stdio-smoke initialize` 通过。
- 安装副本 `scripts/cs_mcp.py --stdio-smoke tools/list '{"profile":"evidence"}'` 通过，返回 33 tools，包含 `cs_create_analysis_campaign` 和 `cs_record_analysis_slice`。
- 安装副本无 `__pycache__` / `*.pyc`。
- `codex mcp list` 能看到 `codexscientist-codex` server，status enabled。

补充模拟：

- `/tmp/codex_scientist_codex_simulation_final.py` 退出码 0，未污染仓库根目录；`stale_usage_phrase_count=0`。
- 该旧脚本仍报告 4 个 `contract_fail`，原因是脚本自身仍用非法 `baseline_path`、缺 baseline gate 后继续期待 experiment/analysis 成功、以及缺 `novelty_contract.mechanism`；这些与当前产品合同一致，不作为本轮新问题。

## 6. 当前结论

本轮 problems.md 记录的真实产品/文档/可发现性问题已完成修复并有回归覆盖。核心变化是把普通 Codex 用户入口从“插件安装但 MCP 未接入 / init_project 回到 native-only / docs 仍讲旧 profile”收敛为“installer 直接注册 MCP server、项目 note MCP-first、README/docs/skills/profile/schema/smoke 与升级 6 当前合同一致”。
