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
  <a href=".codex-plugin/plugin.json"><img alt="Codex Native" src="https://img.shields.io/badge/Codex-Native-4D6A7A?style=for-the-badge"></a>
  <a href="#不提供的内容"><img alt="Stable curated MCP" src="https://img.shields.io/badge/MCP-Stable%20Curated-2E7D32?style=for-the-badge"></a>
  <a href="docs/USAGE.md"><img alt="48 public cs tools" src="https://img.shields.io/badge/Public%20Tools-48%20canonical%20cs__%2A-2563EB?style=for-the-badge"></a>
  <a href="#项目本地-runtime"><img alt="Project local runtime" src="https://img.shields.io/badge/Runtime-Project%20Local-7C3AED?style=for-the-badge"></a>
</p>

<p align="center">
  <strong>稳定 curated MCP</strong> ·
  <strong>CLI fallback</strong> ·
  <strong>项目本地研究状态</strong> ·
  <strong>可审计 CodexScientist provenance</strong>
</p>

<p align="center">
  <strong>Codex 做机械动作，CodexScientist 记录研究意义。</strong>
</p>

---

CodexScientist-codex 是基于 DeepScientist 二次开发、给 Codex CLI 使用的 CodexScientist 插件，默认提供稳定 curated MCP 控制面，并保留 `scripts/csctl.py` 作为 CLI fallback。它把 headless runtime、curated `cs_*` schemas、Codex skills、support skills、`scripts/cs_mcp.py` 和 `scripts/csctl.py` 打包进一个可安装的 Codex 插件目录。

本 README 参考上游 DeepScientist 的展示风格，但边界保持清楚：MCP 是小而稳定的高频研究控制面，常规 file、shell、Git、test、build、process 工作仍由 Codex 原生能力完成。

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

CodexScientist 适合长周期研究工作：quest、baseline、experiment、artifact、memory、analysis 和 paper-ready output。Codex 则擅长文件编辑、命令执行、测试和 Git 工作流。这个适配器把两者分工明确地接在一起：

| 常见痛点 | 这个适配器保留下来的内容 |
| --- | --- |
| 研究状态容易散落在聊天记录里 | quest state、memory cards、artifacts 和 milestones 保存在项目 runtime 中。 |
| 实验和日志分散在终端、脚本和笔记里 | 正式证据命令可通过 `cs_bash_exec` 记录 quest-local logs 和 session state。 |
| paper / reliability 工作后续难审计 | paper bundles、strict-research ledgers、reliability cards 和 analysis slices 会作为 CodexScientist artifacts 留痕。 |
| 所有 Codex 操作都被插件包装会变慢 | 常规 file、shell、Git、test、build、process 工作继续使用 Codex 原生能力。 |

## 一眼看懂

| 范围 | 内容 |
| --- | --- |
| 控制面 | `scripts/cs_mcp.py` 暴露稳定 curated MCP；`scripts/csctl.py` 保留为 CLI fallback。 |
| 公开工具面 | 当前公开 48 个 canonical `cs_*` 工具；历史 `codexscientist_*` 名称只作为隐藏兼容别名保留。 |
| 研究状态 | 项目本地 quest、memory、artifact、baseline、experiment、paper bundle、analysis campaign 和 event 读取。 |
| Codex skills | `codexscientist-codex` 以及实验、handoff、writing plan、paper reliability、review 等 adapted stage/support skills。 |
| 安全边界 | 只暴露稳定 curated MCP；不提供 all-tools/full-runtime MCP；正常路径不调用外部 cs 命令。 |

## 它能让 Codex 做什么？

### 1. 启动并维护真实 CodexScientist quest

- 使用 canonical `cs_*` 工具创建或检查 quest
- 保留 durable requirements 和 mode state
- 将 runtime 数据放在研究项目目录下，而不是全局 agent 状态里

### 2. 把研究操作变成可审计 artifact

- 写入 memory cards、milestones、decision records 和 artifacts
- 记录 baselines、main experiment runs、analysis slices 和 paper bundles
- 通过 `cs_events` 读取 quest events

### 3. 保持 Codex 的正常开发效率

- 文件读写搜索、普通 shell、测试、Git/GitHub、进程监控、本地文档编辑继续走 Codex 原生能力
- `cs_bash_exec` 只用于正式 experiment、baseline、analysis 或 paper-facing evidence commands

### 4. 为 Codex 打包 CodexScientist 专用支持流程

- `codexscientist-experiment-execution`
- `codexscientist-quest-handoffs`
- `codexscientist-writing-plans`
- `codexscientist-paper-reliability-verification`
- `codexscientist-review`

## 快速开始

在 `CodexScientist-codex` 目录内检查：

```bash
python scripts/cs_mcp.py --stdio-smoke initialize
python scripts/cs_mcp.py --stdio-smoke tools/list
python scripts/csctl.py doctor --format json
```

安装到 Codex：

```bash
bash scripts/install.sh
```

安装后在研究项目根目录初始化提示文件，并验证项目本地 runtime：

```bash
bash ~/.codex/plugins/codexscientist-codex/scripts/init_project.sh /path/to/project
python ~/.codex/plugins/codexscientist-codex/scripts/csctl.py --project-root /path/to/project doctor --format json
```

从研究项目根目录创建 quest：

```bash
python ~/.codex/plugins/codexscientist-codex/scripts/csctl.py call cs_new_quest \
  --json '{"goal":"my research goal","title":"My Quest","workspace_mode":"copilot"}' \
  --format json
```

之后使用：

```bash
python ~/.codex/plugins/codexscientist-codex/scripts/csctl.py call <cs_tool_name> \
  --json '<object>' \
  --format json
```

执行持久化 quest、memory、artifact、baseline、experiment、analysis、strict-research、paper-fetch 和 paper-bundle 操作。

## 项目本地 runtime

从研究项目根目录运行时，CodexScientist 状态保存在：

```text
<project>/CodexScientist/
```

这会把 quests、artifacts、memory、bash provenance 和 paper bundles 留在研究项目里，而不是散落到全局 Codex 或 Hermes 状态中。

## 安装细节

`scripts/install.sh` 执行 local-personal Codex 插件安装：

1. 复制本目录到 `~/.codex/plugins/codexscientist-codex`。
2. 如果目标目录已存在，先备份为 `~/.codex/plugins/codexscientist-codex.backup-<timestamp>`。
3. 注册 `~/.agents/plugins/marketplace.json`。
4. 在 `~/.codex/config.toml` 中启用 `[plugins."codexscientist-codex@local-personal"]`。
5. 运行 `scripts/doctor.py`。

常规 Codex 使用建议保持 `CODEX_HOME` 和 `AGENTS_HOME` 默认值；这两个环境变量主要用于隔离 smoke test 或明确的非默认安装。

更多细节见 [docs/INSTALL.md](docs/INSTALL.md)、[docs/USAGE.md](docs/USAGE.md) 和 [docs/REPOSITORY_LAYOUT.md](docs/REPOSITORY_LAYOUT.md)。

## Stable curated MCP 与 CLI fallback 边界

当前默认控制面是 `scripts/cs_mcp.py` 提供的 stable curated MCP stdio 入口；`scripts/csctl.py` 保留为 CI、调试、批量迁移和恢复场景的 CLI fallback。两者复用同一 service layer，避免把 MCP 实现成 shell 包装。

| 能力族 | 默认 MCP 工具 / fallback |
| --- | --- |
| 状态与诊断 | `cs_status`、`cs_doctor` / `scripts/csctl.py doctor` |
| context / manifest / trial | `cs_context_pack`、`cs_manifest_validate`、`cs_trial_show` / `summary context-pack`、`manifest validate`、`trial show` |
| runner / queue / soak | `cs_runner_status`、`cs_queue_status`、`cs_queue_reconcile`、`cs_soak_accelerated`、`cs_soak_crash_resume` / 对应 `runner`、`queue`、`soak` CLI |
| wiki / review / cost | `cs_wiki_query_pack`、`cs_review_status`、`cs_cost_status` / 对应 CLI 命令 |
| skill retrieval | `cs_skill_search`、`cs_skill_load`，用于按需加载 thin skill 片段 |

`plugin.json` 仍不内联 `mcpServers`，安装脚本也不会直接改写 Codex 全局 MCP 配置；MCP 入口以可审计脚本 `scripts/cs_mcp.py` 暴露。

## 不提供的内容

- 不提供 all-tools MCP，也不把所有 runtime 内部函数暴露成工具。
- 正常路径不调用外部 legacy CLI。
- 不恢复 Web UI、TUI、social/browser connector 或 raw dispatcher。

## Codex 原生操作边界

CodexScientist-codex 负责研究语义层：quest 状态、持久用户需求、memory、artifact、baseline、正式实验记录、analysis campaign 状态、paper/reliability 流程，以及正式证据命令的 `cs_bash_exec` provenance。

常规操作层继续使用 Codex 原生能力：文件读写搜索、普通 shell、Git/GitHub、测试/构建/lint、进程监控和本地文档编辑。
