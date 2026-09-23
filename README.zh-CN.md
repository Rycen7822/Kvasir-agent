<h1 align="center">
  Kvasir-agent × Codex MCP 控制面
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
  <strong>可审计 Kvasir-agent provenance</strong>
</p>

---

Kvasir-agent 是基于 DeepScientist 二次开发、给 Codex CLI 使用的 Kvasir-agent 插件。默认研究控制面是 MCP-only：Codex 通过紧凑的 `ka_*` MCP 工具记录研究语义，常规文件读写、搜索、编辑、shell、Git、测试、构建和进程工作继续走 Codex 原生能力。

`/goal` 是 Codex 原生能力。Kvasir-agent 不实现、不注册、不拦截、不模拟 slash command。Codex 进入 goal 语境后，Kvasir-agent 只提供用于 root-bound research state、持久需求、memory、artifact、baseline、experiment、analysis、paper/reliability、checkpoint/resume、手动诊断、novelty support 和 claim gate 的 MCP 工具。

管理员终端命令只在 [docs/ADMIN_CLI.md](docs/ADMIN_CLI.md) 中说明。它们服务 human/admin/debug/CI/recovery compatibility，不是默认 Codex research path。

## 项目基础与参考项目

本项目主要以 [DeepScientist](https://github.com/ResearAI/DeepScientist) 为基础进行二次开发，并面向 Codex CLI / Codex 插件运行方式做适配与重组。本仓库中的 `Kvasir-agent` 命名主要指向这一 Codex 插件化/runtime 适配层，而不是声明一个独立于 DeepScientist 的上游来源。

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
| 实验和日志分散在终端、脚本和笔记里 | 正式证据命令可通过 `ka_bash_exec` 记录 project-local logs 和 session state。 |
| paper / reliability 工作后续难审计 | paper bundles、strict-research ledgers、reliability cards、claim gate decisions 和 analysis slices 会作为 Kvasir-agent artifacts 留痕。 |
| 所有 Codex 操作都被插件包装会变慢 | 常规 file、shell、Git、test、build、process 工作继续使用 Codex 原生能力。 |

## 一眼看懂

| 范围 | 内容 |
| --- | --- |
| 控制面 | 默认通过 `scripts/ka_mcp.py` 走 MCP-only default；管理员终端命令隔离在 `docs/ADMIN_CLI.md`。 |
| 公开工具面 | 精选的 `ka_*` 工具。 |
| MCP profile | 默认发现 24 个公开研究工具和参数定义；显式 profile 仅用于筛选，执行器仍需通过权限门槛。 |
| 长程恢复 | `ka_research_read(operation="status")`、`ka_research_read(operation="resume")`、`ka_research_read(operation="delta")` 和 `ka_checkpoint` 提供被动恢复锚点；watchdog 风格诊断在默认 Codex MCP 面中保持 hidden/admin-only。 |
| 方法改进 | `ka_method_record(operation="result")`、`ka_research_read(operation="methods")` 和 `ka_claim_gate` 等 public 工具闭合 experiment -> novelty -> evidence loop；自动 idea selection 不暴露在默认 MCP 面。 |
| 研究状态 | 项目本地 root-bound manifest、memory、artifact、baseline、experiment、paper bundle、analysis campaign 和有界 event/delta 摘要。 |
| Codex skills | 7 个入口：研究工作区、实验、写作审稿、严格文献研究、论文可靠性、图表和交接。 |

## 快速开始

需要 Python 3.10+、PyYAML、jsonschema 和支持插件的 Codex CLI。按照 [安装指南](docs/INSTALL.md) 把源目录加入 marketplace，然后安装：

```bash
bash scripts/install.sh kvasir-agent@local-personal
codex plugin list
```

开启新对话后，Codex 会发现 7 个原生技能和随插件声明的 MCP。默认工具列表包含 24 个研究工具及其参数定义；不需要切换 profile 来解锁常规研究工具。

本地检查和可选的项目说明文件：

```bash
python3 scripts/ka_mcp.py --stdio-smoke tools/list
bash scripts/init_project.sh /path/to/project
```

每次研究 MCP 调用都用 `project` 明确传入项目绝对路径，从 `ka_research_read(operation="status")` 和 `ka_research_read(operation="resume")` 开始，通过 `ka_record_user_requirement` 保存约束，首次写入会初始化研究状态。

## 项目本地 runtime

从研究项目根目录运行时，Kvasir-agent 状态保存在：

```text
<project>/Kvasir-agent/
```

这会把 root-bound `research.yaml`、artifacts、memory、bash provenance、manual diagnostic records、checkpoints、analysis slices、claim decisions 和 paper bundles 留在研究项目里，而不是散落到全局 Codex 状态中。`Kvasir-agent/quests/` 仅作为 legacy migration 输入保留，新写入不会创建该路径。

## 安装与升级

`.codex-plugin/plugin.json` 声明技能目录和 `.mcp.json`。`scripts/install.sh` 调用 `codex plugin add`，由 Codex 管理缓存、启用状态和 MCP 生命周期。升级时更新源版本后重新安装，并开启新对话。旧版全局 MCP 注册的迁移步骤见 [安装指南](docs/INSTALL.md)。

## 研究能力的边界

保留基线、保护文件哈希、实验谱系、正式日志、反馈对账和研究交接。目标推进、技能发现、普通命令和 Git 使用 Codex 原生能力。创新性契约保存待验证假设，不生成自动分数；`ka_record_main_experiment` 仅记录数据；`ka_claim_gate` 检查材料完整性，科学有效性需要结合证据判断。

## 原 Kvasir-agent MCP 等价关系

本适配器保留业务效果，而不是复制协议形态：

| 原 Kvasir-agent surface | Codex-native equivalent |
| --- | --- |
| `memory.write/read/search/list_recent` | `ka_memory_write`, `ka_memory_query` |
| `artifact.record` 和旧 artifact flows | `ka_artifact_record` 以及 `ka_artifact_index` 等 public artifact tools |
| event reads | `ka_research_read(operation="status")`、`ka_research_read(operation="delta")` 和 compact root-bound summaries |
| `bash_exec` | `ka_bash_exec`，在需要 formal provenance 时保留 project-local execution state 和 logs |
| artifact convenience/introspection helpers | `ka_research_read(operation="status")`, `ka_research_read(operation="methods")`; update summaries through Codex file editing. |

## 不提供的内容

- 不提供 all-tools/full-runtime MCP surface。
- 不实现 slash commands。
- 正常研究路径不使用 terminal compatibility commands。
- 不恢复 Web UI、TUI、social/browser connector 或 raw dispatcher。

## Codex 原生操作边界

Kvasir-agent 负责研究语义层：root-bound research state、持久用户需求、memory、artifact、baseline、正式实验记录、analysis campaign 状态、paper/reliability 流程、manual diagnostics、checkpoint/resume、claim gate，以及正式证据命令的 `ka_bash_exec` provenance。

常规操作层继续使用 Codex 原生能力：文件读写搜索、普通 shell、Git/GitHub、测试/构建/lint、进程监控和本地文档编辑。

See [public tool migration](docs/TOOL_MIGRATION.md) for the 24-tool API and retired entries.
