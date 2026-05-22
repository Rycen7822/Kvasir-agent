# Codex-Scientist user-path problem log

更新时间：2026-05-14 11:44 CST+0800
仓库：`/home/xu/project/autoscientist/Codex-Scientist`

用途：保留真实/近真实 Codex + MCP 用户路径模拟后仍有价值的结论、边界决策和验收证据；详细流水账保留在 `/tmp` findings，不在本文重复展开。

## 维护原则

- 先分类再修改：代码 contract、文档/schema、installer、skill、设计说明分开处理。
- 不为修文档而把 hidden/admin/autonomous tools 加回 public MCP profile。
- public MCP surface 以 `core/evidence/formal_run/literature/paper_write` 为准；`goal` 是 deprecated evidence-style profile，不作为新增默认面。
- skill 只有在用户操作流程或提示模板错误时才改；Cycle 5 的 skill 项仅限安装副本会暴露的 Codex-facing 文本和默认路径，不改研究逻辑。
- 大型 JSON、transcript 和长命令输出放 `/tmp`，本文只保留摘要、路径和最终验收。

## 证据来源

历史 findings：`/tmp/codex_scientist_user_simulation_20260514.md`、`/tmp/codex_scientist_user_sim_A_install_docs_20260514.md`、`/tmp/codex_scientist_user_sim_B_research_workflow_20260514.md`、`/tmp/codex_scientist_user_sim_C_schema_failclosed_20260514.md`、`/tmp/codex_scientist_problems_fix_classification_20260514.md`、`/tmp/codex_scientist_final_integration_review_20260514.md`。

Cycle findings：
- Cycle 1：`/tmp/cs_cycle1_A_install_discovery_20260514.md`、`/tmp/cs_cycle1_B_research_workflow_20260514.md`、`/tmp/cs_cycle1_C_longrun_recovery_20260514.md`、`/tmp/cs_cycle1_D_surface_schema_docs_20260514.md`
- Cycle 2：`/tmp/cs_cycle2_A_install_discovery_20260514.md`、`/tmp/cs_cycle2_B_research_workflow_20260514.md`、`/tmp/cs_cycle2_C_longrun_recovery_20260514.md`、`/tmp/cs_cycle2_D_surface_schema_docs_20260514.md`
- Cycle 3：`/tmp/cs_cycle3_A_install_discovery_20260514.md`、`/tmp/cs_cycle3_B_research_workflow_20260514.md`、`/tmp/cs_cycle3_C_longrun_recovery_20260514.md`、`/tmp/cs_cycle3_D_surface_schema_docs_20260514.md`
- Cycle 4：`/tmp/cs_cycle4_A_install_discovery_20260514.md`、`/tmp/cs_cycle4_B_research_workflow_20260514.md`、`/tmp/cs_cycle4_C_longrun_recovery_20260514.md`、`/tmp/cs_cycle4_D_surface_schema_docs_20260514.md`
- Cycle 5：`/tmp/cs_cycle5_A_install_discovery_20260514.md`、`/tmp/cs_cycle5_B_research_workflow_20260514.md`、`/tmp/cs_cycle5_C_longrun_recovery_20260514.md`、`/tmp/cs_cycle5_D_surface_schema_docs_20260514.md`

当前 public contract（主会话复核）：`core=11`、`evidence=33`、`formal_run=34`、`literature=23`、`paper_write=27`、deprecated `goal=33`。

## 已关闭项

| ID | 分类 | 状态 | 处理结论 / 回归 |
| --- | --- | --- | --- |
| P1 `cs_resume_brief` 误报 `blocked_missing_goal` | 代码 | 已修复 | fallback 到 `quest.yaml` title / `brief.md` Goal；回归 `test_resume_brief_uses_mcp_first_quest_goal_without_missing_goal_blocker`。 |
| P2 JSON-RPC `tools/call` 绕过 public profile | 代码/安全边界 | 已修复 | `tools/call` 和 `cs_tool_schema` 对非 public MCP tools fail-closed；回归 `test_jsonrpc_tools_call_enforces_public_mcp_profile_boundary`。 |
| P3 `cs_artifact_index` 与 compact state artifact scope 不一致 | 代码/语义 | 已修复 | 支持 `quest_id` scope；回归 `test_artifact_index_can_scope_to_quest_artifacts_seen_by_compact_state`。 |
| D1 README/docs 推荐 hidden 或不存在 tools | 文档 | 已修复 | 默认 docs 改用 public method/recovery tools；hidden selection/watchdog 保持 hidden/admin-only。 |
| D2 profile 数量和 Codex-neutral wording 过期 | 文档/schema | 已修复 | profile 数量更新；public metadata/schema 去除 Hermes wording。 |
| I1/I2 `cs_bash_exec` / recovery schema 不够可发现 | schema | 已修复 | formal provenance conditional required 和常用 optional fields 已补。 |
| I4 `workdir_outside_quest` 错误太 terse | 错误质量 | 已修复 | 返回 `allowed_roots` 和 `retry_template`。 |
| I5/I6 installer Python command / non-default `CODEX_HOME` path | installer | 已修复 | 写检测到的 interpreter；非默认 `CODEX_HOME` 用绝对安装路径。 |
| I7 `/tmp` Codex helper warning | 环境噪声 | 无需修复 | `/tmp` helper warning 不影响 MCP discovery/smoke。 |
| C2-B1 `cs_claim_gate` 可用不存在的 `analysis_slice_ids` 通过 | 代码/安全门 | 已修复 | 验证每个 analysis slice 在 `.cs/analysis_campaigns/*.json` 中存在且状态为 `completed/accepted`；缺失/未完成时 fail-closed；回归 `test_claim_gate_blocks_unknown_analysis_slice_id`。 |
| C2-I1 安装后普通 Python MCP 启动生成 installed plugin bytecode | installer/launcher hygiene | 已修复 | installer 写入 Codex MCP config `args = ["-B", ...]`，安装后 smoke 仍不生成 `__pycache__/*.pyc`；回归 `test_installer_registers_codex_mcp_server_and_keeps_install_tree_clean`。 |
| C2-I2 `cs_artifact_record` schema generic 但 kind 枚举有限 | schema/错误质量 | 已修复 | schema 暴露 canonical enum；unknown kind 返回 `invalid_argument`、`allowed_kinds`、`retry_template`；回归 `test_public_tool_metadata_and_schemas_are_codex_discoverable`。 |
| C2-I3 writing-facing `cs_create_analysis_campaign` 分步失败 | schema/preflight | 已修复 | preflight 一次性报告写作字段和 todo paper contract 字段，并返回最小 retry template；回归 `test_analysis_campaign_preflight_reports_all_missing_writing_contract_fields`。 |
| C2-I4 `cs_pack_delta` 缺 checkpoint artifact/risk detail | recovery payload | 已修复 | `checkpoint.created` event 携带 `artifact_refs/risk_flags`，pack delta 输出 `changed_artifacts/changed_risks`；回归 `test_pack_delta_surfaces_checkpoint_artifacts_and_risks`。 |
| C2-M1 `cs_claim_gate` blocked 响应偏泛 | 错误质量 | 已修复 | blocked 响应补 claim-gate 专用 retry template 与 suggested_next_action。 |
| C3-H1/C3-I1 recovery schema 不可操作 | schema/恢复工具发现性 | 已修复 | `cs_checkpoint` 暴露 phase/completed/decisions/validation/next_action/artifact_refs/risk_flags/idempotency_key；`cs_context_pack` 暴露 quest_id/max_chars；回归 `test_public_tool_metadata_and_schemas_are_codex_discoverable`。 |
| C3-I2 installer stdout smoke 和手动 docs 缺 `-B` | installer/docs hygiene | 已修复 | installer stdout smoke 与 README/README.zh-CN/docs/INSTALL manual `codex mcp add` 均带 `-B`；回归 `test_installer_registers_codex_mcp_server_and_keeps_install_tree_clean`、`test_user_entry_docs_have_current_upgrade6_profile_contract`。 |
| C3-I3 public skills 默认 wording 暗示 hidden queue/trial/wiki family | skill wording | 已修复 | 顶层 public skills 改成“only when visible in selected profile”并列 public families；回归 `test_public_skills_do_not_advertise_hidden_tool_families_by_default`。 |
| C3-I4/C4-M1 packaged skill 用户可见 Hermes/.hermes/csctl wording | packaged skill wording / Codex-facing hygiene | 已修复 | broad scan 忽略内部 `metadata/hermes` YAML 键，禁止用户可见正文 `Hermes`、`.hermes`、`scripts/csctl.py`/`csctl.py`；先修 runtime resources，再修顶层 `skills/**` legacy references。 |
| C5-H1 安装副本会携带顶层 `skills/*/references/legacy-playbook.md` 旧 CLI/Hermes 文本 | packaged install skill references | 已修复 | 顶层 legacy-playbook 全部改为 public MCP `cs_*`/`tools/list`/`cs_tool_schema` wording；移除 `author: Hermes Agent`、`scripts/csctl.py`/`csctl.py`、`.hermes`；回归 `test_public_plugin_metadata_and_packaged_support_skills_are_codex_neutral`。 |
| C5-H2 runtime/top-level verifier config/script user-local `.hermes` path | packaged resource defaults | 已修复 | `sources.yaml` 改 `$CODEX_HOME/secrets/openreview.env`；`verifier.py` 改 `OPENREVIEW_ENV_FILE`/`CODEX_OPENREVIEW_ENV_FILE`/`$CODEX_HOME/secrets/openreview.env` fallback；同步顶层和 runtime resource。 |
| C5-L1 `docs/INSTALL.md` 默认安装文档直接说 “Use hidden admin/debug CLI” | docs wording | 已修复 | 默认安装页改为 “Advanced admin/debug CLI commands are documented separately”，普通 Codex 用户继续 public MCP path；回归 `test_user_entry_docs_have_current_upgrade6_profile_contract`。 |
| C5-L2 顶层 public skills 仍有普通概念词 `wiki` / `trial(s)` | skill wording | 已修复 | 这些词虽非 hidden tool name，但会增加 Codex agent 对隐藏 family/运行态概念的误读风险；已将 `full wiki` 改为 `full background notes`，`trial changes` 改为 `experiment/run changes`，`running trials` 改为 `running experiments`；严格回归改为 word-boundary 扫描，顶层 `skills/*/SKILL.md` offenders=0。 |

## 已接受/暂不修项

| ID | 分类 | 结论 |
| --- | --- | --- |
| C2-M2 `context_pack` 无 manifest 时 project/goal 显示 unknown/unset | recovery payload | 暂不修；`cs_resume_brief` 已是恢复主路径并能从 quest metadata/brief 兜底。 |
| C2-M3 `--stdio-smoke call` helper 可绕过 public MCP 注册边界 | developer helper | 暂不修；普通 Codex JSON-RPC `tools/call` 已 fail-closed。若后续把 helper 定义为 public-equivalent，再加同样 guard。 |
| C2-D1 `cs_log_digest` 与 `cs_bash_exec` 日志体系不同 | docs/guidance | 暂不修；public recovery 可用 `cs_bash_exec read/status/wait`、`cs_artifact_index`、`cs_resume_brief`。 |

## 最近验收基线

- Cycle5 targeted RED→GREEN：`python -m pytest tests/test_codex_user_path_fixbacks.py::test_user_entry_docs_have_current_upgrade6_profile_contract tests/test_codex_user_path_fixbacks.py::test_public_plugin_metadata_and_packaged_support_skills_are_codex_neutral -q` → 先 fail，修复后 2 passed。
- Cycle5 packaged broad scan：`skills/`、`codex_scientist/runtime/resources/skills`、`codex_scientist/runtime/resources/repo/src/skills` 的 `.md/.txt/.yaml/.yml/.py/.json/.toml` 文本，忽略内部 `metadata/hermes` YAML 键后，`Hermes`、`.hermes`、`scripts/csctl.py`、`csctl.py` offenders → 0。
- Cycle5 related tests：`python -m pytest tests/test_codex_user_path_fixbacks.py tests/test_skill_prompt_contract.py tests/test_problems_md_regressions.py -q` → 30 passed。
- Cycle5 full suite：`python -m pytest -q` → 263 passed。
- Cycle5 P4 acceptance：`python scripts/p4_acceptance.py` → P4 acceptance passed，targeted pytest 48 passed；MCP `tools/list`、`initialize`、no CLI surface scan 通过。
- Cycle5 hygiene：`git diff --check && test ! -d CodexScientist && test ! -d .codex` → `cycle5_diff_pollution_check=PASS`；subagents 后复核 → `post_cycle5_subagents_hygiene=PASS` / `final_cycle5_hygiene=PASS`。
- Cycle5 subagents：A clean install/discovery/hygiene PASS；B bounded research workflow PASS；C long-run recovery/compaction PASS；D public/hidden surface + schema/docs/packaged-source PASS for all blocking checks；后续已修复当时唯一 `FAIL LOW` 的普通概念词 `wiki` / `trial(s)`，严格回归 now covers word-boundary scan。
- Public skill wording tightening：`python -m pytest tests/test_skill_prompt_contract.py::test_public_skills_do_not_advertise_hidden_tool_families_by_default -q` → RED 后 GREEN；`top_level_public_skill_wiki_trial_offenders=0`；`python -m pytest tests/test_skill_prompt_contract.py tests/test_codex_user_path_fixbacks.py -q` → 13 passed；`python -m pytest -q` → 263 passed；`python scripts/p4_acceptance.py` → P4 acceptance passed；`final_wording_hygiene=PASS`。

## 当前判断

Cycle 5 已完成步骤 1→2→3→4。当前没有已知 BLOCKER/IMPORTANT；安装、public MCP discovery、JSON-RPC fail-closed、claim gate、artifact/analysis schema、checkpoint/resume/pack-delta recovery、docs `-B`、packaged source hygiene、全量测试、P4 acceptance、干净上下文用户模拟均已通过。顶层 public skills 的 `wiki` / `trial(s)` 普通概念词已按用户确认修复，不再作为非阻塞残留项。

结论：可以让用户通过 Codex 使用 Codex Scientist 做长程稳定自动化研究。
