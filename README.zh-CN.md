<h1 align="center">
  CodexScientist × Codex MCP 控制面
</h1>

<p align="center">
  <a href="https://github.com/ResearAI/DeepScientist">上游 DeepScientist</a> |
  <a href="README.md">English README</a> |
  <a href="docs/INSTALL.md">安装指南</a> |
  <a href="docs/USAGE.md">使用指南</a> |
  <a href=".codex-plugin/plugin.json">Codex Manifest</a>
</p>

<p align="center">
  <strong>MCP-only default</strong> ·
  <strong>Codex 原生 /goal 边界</strong> ·
  <strong>项目本地研究状态</strong> ·
  <strong>可审计 CodexScientist provenance</strong>
</p>

---

CodexScientist-codex 是基于 DeepScientist 二次开发、给 Codex CLI 使用的 CodexScientist 插件。默认研究控制面是 MCP-only：Codex 通过紧凑的 `cs_*` MCP 工具记录研究语义，常规文件读写、搜索、编辑、shell、Git、测试、构建和进程工作继续走 Codex 原生能力。

`/goal` 是 Codex 原生能力。CodexScientist 不实现、不注册、不拦截、不模拟 slash command。Codex 进入 goal 语境后，CodexScientist 只提供用于 root-bound research state、持久需求、memory、artifact、baseline、experiment、analysis、paper/reliability、checkpoint/resume、手动诊断、novelty support 和 claim gate 的 MCP 工具。

管理员终端命令只在 [docs/ADMIN_CLI.md](docs/ADMIN_CLI.md) 中说明。它们服务 human/admin/debug/CI/recovery compatibility，不是默认 Codex research path。

## 项目基础与参考项目

本项目主要以 [DeepScientist](https://github.com/ResearAI/DeepScientist) 为基础进行二次开发，并面向 Codex CLI / Codex 插件运行方式做适配与重组。本仓库中的 `CodexScientist` 命名主要指向这一 Codex 插件化/runtime 适配层，而不是声明一个独立于 DeepScientist 的上游来源。

本项目的设计与实现也参考或受到以下开源自动化研究 / AI Scientist 项目的启发：

- [Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep)
- [autoresearch](https://github.com/karpathy/autoresearch)
- [EvoScientist](https://github.com/EvoScientist/EvoScientist)
- [ai-researcher](https://github.com/hkuds/ai-researcher)
- [AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2)
- [AgentLaboratory](https://github.com/SamuelSchmidgall/AgentLaboratory)
- [ml-intern](https://github.com/huggingface/ml-intern)

## 为什么需要这个适配器？

| 常见痛点 | 这个适配器保留下来的内容 |
| --- | --- |
| 研究状态容易散落在聊天记录里 | root-bound research state、requirements、checkpoints、source refs 和 milestones 保存在项目 runtime 中。 |
| 实验和日志分散在终端、脚本和笔记里 | 正式证据命令可通过 `cs_bash_exec` 记录 project-local logs 和 session state。 |
| paper / reliability 工作后续难审计 | paper bundles、strict-research ledgers、reliability cards、claim gate decisions 和 analysis slices 会作为 CodexScientist artifacts 留痕。 |
| 所有 Codex 操作都被插件包装会变慢 | 常规 file、shell、Git、test、build、process 工作继续使用 Codex 原生能力。 |

## 一眼看懂

| 范围 | 内容 |
| --- | --- |
| 控制面 | 默认通过 `scripts/cs_mcp.py` 走 MCP-only default；管理员终端命令隔离在 `docs/ADMIN_CLI.md`。 |
| 公开工具面 | curated canonical `cs_*` 工具；历史 `codexscientist_*` 名称只作为隐藏兼容别名保留。 |
| MCP profile | 默认 core profile 暴露 bounded root-bound recovery 工具；更宽的显式 profile 是 `evidence`、`formal_run`、`literature` 和 `paper_write`；`stage` 是 label，不过滤工具列表。 |
| 长程恢复 | `cs_status`、`cs_resume_brief`、`cs_pack_delta` 和 `cs_checkpoint` 提供被动恢复锚点；watchdog 风格诊断在默认 Codex MCP 面中保持 hidden/admin-only。 |
| 方法改进 | `cs_update_method_scoreboard`、`cs_get_optimization_frontier` 和 `cs_claim_gate` 等 public 工具闭合 experiment -> novelty -> evidence loop；自动 idea selection 不暴露在默认 MCP 面。 |
| 研究状态 | 项目本地 root-bound manifest、memory、artifact、baseline、experiment、paper bundle、analysis campaign 和有界 event/delta 摘要。 |
| Codex skills | `codexscientist-codex` 以及 experiment、handoff、writing plan、paper reliability、review 等 adapted support skills。 |

## 快速开始

在 `CodexScientist-codex` 目录内检查：

```bash
python scripts/cs_mcp.py --stdio-smoke initialize
python scripts/cs_mcp.py --stdio-smoke tools/list
python scripts/p4_acceptance.py
```

安装到 Codex：

```bash
bash scripts/install.sh
```

安装脚本会复制插件、启用 `[plugins."codexscientist-codex@local-personal"]`，并在 Codex config 中注册 MCP server。若需要手动注册，使用同一个 stdio 入口：

```bash
codex mcp add codexscientist-codex -- python -B ~/.codex/plugins/codexscientist-codex/scripts/cs_mcp.py
```

安装后在研究项目根目录初始化提示文件：

```bash
bash ~/.codex/plugins/codexscientist-codex/scripts/init_project.sh /path/to/project
```

之后通过 MCP `cs_*` 工具执行：`cs_status`、`cs_record_user_requirement`、`cs_create_local_baseline`、`cs_confirm_baseline`、`cs_submit_idea`、`cs_record_main_experiment`、`cs_create_analysis_campaign`、`cs_record_analysis_slice`、`cs_resume_brief`、`cs_checkpoint` 等。首次 durable write 会 lazy-create `<project>/CodexScientist/research.yaml`；不需要单独的 lifecycle 初始化步骤。

## 项目本地 runtime

从研究项目根目录运行时，CodexScientist 状态保存在：

```text
<project>/CodexScientist/
```

这会把 root-bound `research.yaml`、artifacts、memory、bash provenance、manual diagnostic records、checkpoints、analysis slices、claim decisions 和 paper bundles 留在研究项目里，而不是散落到全局 Codex 状态中。`CodexScientist/quests/` 仅作为 legacy migration 输入保留，新写入不会创建该路径。

## 安装细节

`scripts/install.sh` 执行 local-personal Codex 插件安装：

1. 复制本目录到 `~/.codex/plugins/codexscientist-codex`。
2. 如果目标目录已存在，先备份为 `~/.codex/plugins/codexscientist-codex.backup-<timestamp>`。
3. 注册 `~/.agents/plugins/marketplace.json`。
4. 在 `~/.codex/config.toml` 中启用 `[plugins."codexscientist-codex@local-personal"]`。
5. 在 `~/.codex/config.toml` 中注册 `[mcp_servers.codexscientist-codex]`。
6. 运行 `scripts/doctor.py`，且不在安装副本中保留 Python bytecode。

常规 Codex 使用建议保持 `CODEX_HOME` 和 `AGENTS_HOME` 默认值；这两个环境变量主要用于隔离 smoke test 或明确的非默认安装。

更多细节见 [docs/INSTALL.md](docs/INSTALL.md)、[docs/USAGE.md](docs/USAGE.md)、[docs/MCP.md](docs/MCP.md) 和 [docs/REPOSITORY_LAYOUT.md](docs/REPOSITORY_LAYOUT.md)。

## 原 CodexScientist MCP 等价关系

本适配器保留业务效果，而不是复制协议形态：

| 原 CodexScientist surface | Codex-native equivalent |
| --- | --- |
| `memory.write/read/search/list_recent` | `cs_memory_write`, `cs_memory_read`, `cs_memory_search`, `cs_memory_list_recent` |
| `artifact.record` 和旧 artifact flows | `cs_artifact_record` 以及 `cs_artifact_index` 等 public artifact tools |
| event reads | `cs_status`、`cs_pack_delta` 和 compact root-bound summaries |
| `bash_exec` | `cs_bash_exec`，在需要 formal provenance 时保留 project-local execution state 和 logs |
| artifact convenience/introspection helpers | `cs_status`、`cs_get_method_scoreboard`、`cs_refresh_summary`、`cs_arxiv` 等 public `cs_*` wrappers |

## 不提供的内容

- 不提供 all-tools/full-runtime MCP surface。
- 不实现 slash commands。
- 正常研究路径不使用 terminal compatibility commands。
- 不恢复 Web UI、TUI、social/browser connector 或 raw dispatcher。

## Codex 原生操作边界

CodexScientist-codex 负责研究语义层：root-bound research state、持久用户需求、memory、artifact、baseline、正式实验记录、analysis campaign 状态、paper/reliability 流程、manual diagnostics、checkpoint/resume、claim gate，以及正式证据命令的 `cs_bash_exec` provenance。

常规操作层继续使用 Codex 原生能力：文件读写搜索、普通 shell、Git/GitHub、测试/构建/lint、进程监控和本地文档编辑。
