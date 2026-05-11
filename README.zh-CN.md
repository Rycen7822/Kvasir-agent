<h1 align="center">
  DeepScientist × Codex 原生适配器
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
  <a href="#不提供的内容"><img alt="MCP Free" src="https://img.shields.io/badge/MCP-Free-2E7D32?style=for-the-badge"></a>
  <a href="docs/USAGE.md"><img alt="48 public ds tools" src="https://img.shields.io/badge/Public%20Tools-48%20canonical%20ds__%2A-2563EB?style=for-the-badge"></a>
  <a href="#项目本地-runtime"><img alt="Project local runtime" src="https://img.shields.io/badge/Runtime-Project%20Local-7C3AED?style=for-the-badge"></a>
</p>

<p align="center">
  <strong>Codex 原生安装</strong> ·
  <strong>不走 MCP transport</strong> ·
  <strong>项目本地研究状态</strong> ·
  <strong>可审计 DeepScientist provenance</strong>
</p>

<p align="center">
  <strong>Codex 做机械动作，DeepScientist 记录研究意义。</strong>
</p>

---

DeepScientist-codex 是给 Codex CLI 使用的 DeepScientist 原生适配器。它把已有的 headless runtime、curated `ds_*` schemas、Codex skills、support skills 和 `scripts/dsctl.py` 控制面打包进一个可安装的 Codex 插件目录。

本 README 参考上游 DeepScientist 的展示风格，但边界保持清楚：这里追求的是原 Hermes/MCP 业务面的 Codex-native 功能等价，不是 MCP 协议克隆。

## 为什么需要这个适配器？

DeepScientist 适合长周期研究工作：quest、baseline、experiment、artifact、memory、analysis 和 paper-ready output。Codex 则擅长文件编辑、命令执行、测试和 Git 工作流。这个适配器把两者分工明确地接在一起：

| 常见痛点 | 这个适配器保留下来的内容 |
| --- | --- |
| 研究状态容易散落在聊天记录里 | quest state、memory cards、artifacts 和 milestones 保存在项目 runtime 中。 |
| 实验和日志分散在终端、脚本和笔记里 | 正式证据命令可通过 `ds_bash_exec` 记录 quest-local logs 和 session state。 |
| paper / reliability 工作后续难审计 | paper bundles、strict-research ledgers、reliability cards 和 analysis slices 会作为 DeepScientist artifacts 留痕。 |
| 所有 Codex 操作都被插件包装会变慢 | 常规 file、shell、Git、test、build、process 工作继续使用 Codex 原生能力。 |

## 一眼看懂

| 范围 | 内容 |
| --- | --- |
| 原生传输 | `scripts/dsctl.py` 返回 `transport="codex-native-cli"` 和 `mcp=false`。 |
| 公开工具面 | 当前公开 48 个 canonical `ds_*` 工具；历史 `deepscientist_*` 名称只作为隐藏兼容别名保留。 |
| 研究状态 | 项目本地 quest、memory、artifact、baseline、experiment、paper bundle、analysis campaign 和 event 读取。 |
| Codex skills | `deepscientist-codex` 以及实验、handoff、writing plan、paper reliability、review 等 adapted stage/support skills。 |
| 安全边界 | 不创建 `.mcp.json`，不启动 FastMCP，不注册 MCP server transport，正常路径不调用外部 npm `ds` 命令。 |

## 它能让 Codex 做什么？

### 1. 启动并维护真实 DeepScientist quest

- 使用 canonical `ds_*` 工具创建或检查 quest
- 保留 durable requirements 和 mode state
- 将 runtime 数据放在研究项目目录下，而不是全局 agent 状态里

### 2. 把研究操作变成可审计 artifact

- 写入 memory cards、milestones、decision records 和 artifacts
- 记录 baselines、main experiment runs、analysis slices 和 paper bundles
- 通过 `ds_events` 读取 quest events

### 3. 保持 Codex 的正常开发效率

- 文件读写搜索、普通 shell、测试、Git/GitHub、进程监控、本地文档编辑继续走 Codex 原生能力
- `ds_bash_exec` 只用于正式 experiment、baseline、analysis 或 paper-facing evidence commands

### 4. 为 Codex 打包 DeepScientist 专用支持流程

- `deepscientist-experiment-execution`
- `deepscientist-quest-handoffs`
- `deepscientist-writing-plans`
- `deepscientist-paper-reliability-verification`
- `deepscientist-review`

## 快速开始

在 `DeepScientist-codex` 目录内检查：

```bash
python scripts/dsctl.py doctor --format json
python scripts/dsctl.py list-tools --format json
```

安装到 Codex：

```bash
bash scripts/install.sh
```

安装后在研究项目根目录初始化提示文件，并验证项目本地 runtime：

```bash
bash ~/.codex/plugins/deepscientist-codex/scripts/init_project.sh /path/to/project
python ~/.codex/plugins/deepscientist-codex/scripts/dsctl.py --project-root /path/to/project doctor --format json
```

从研究项目根目录创建 quest：

```bash
python ~/.codex/plugins/deepscientist-codex/scripts/dsctl.py call ds_new_quest \
  --json '{"goal":"my research goal","title":"My Quest","workspace_mode":"copilot"}' \
  --format json
```

之后使用：

```bash
python ~/.codex/plugins/deepscientist-codex/scripts/dsctl.py call <ds_tool_name> \
  --json '<object>' \
  --format json
```

执行持久化 quest、memory、artifact、baseline、experiment、analysis、strict-research、paper-fetch 和 paper-bundle 操作。

## 项目本地 runtime

从研究项目根目录运行时，DeepScientist 状态保存在：

```text
<project>/DeepScientist/
```

这会把 quests、artifacts、memory、bash provenance 和 paper bundles 留在研究项目里，而不是散落到全局 Codex 或 Hermes 状态中。

## 安装细节

`scripts/install.sh` 执行 local-personal Codex 插件安装：

1. 复制本目录到 `~/.codex/plugins/deepscientist-codex`。
2. 如果目标目录已存在，先备份为 `~/.codex/plugins/deepscientist-codex.backup-<timestamp>`。
3. 注册 `~/.agents/plugins/marketplace.json`。
4. 在 `~/.codex/config.toml` 中启用 `[plugins."deepscientist-codex@local-personal"]`。
5. 运行 `scripts/doctor.py`。

常规 Codex 使用建议保持 `CODEX_HOME` 和 `AGENTS_HOME` 默认值；这两个环境变量主要用于隔离 smoke test 或明确的非默认安装。

更多细节见 [docs/INSTALL.md](docs/INSTALL.md) 和 [docs/USAGE.md](docs/USAGE.md)。

## 与原 Hermes MCP 插件的功能等价边界

这里的“等价”指研究业务效果、状态写入、文件产物和错误语义尽量保持一致，不指 MCP 协议形态一致：

| 原 DeepScientist/Hermes 表面 | Codex-native 等价工具 |
| --- | --- |
| `memory.write/read/search/list_recent` | `ds_memory_write`、`ds_memory_read`、`ds_memory_search`、`ds_memory_list_recent` |
| `artifact.record` 和 quest artifact 流程 | `ds_artifact_record` 以及各类专用 `ds_*` artifact 工具 |
| quest event 读取 | `ds_events` |
| `bash_exec` | `ds_bash_exec`，保留 quest-local execution state 和日志 |
| artifact convenience / introspection helpers | 对应的 `ds_*` wrappers，例如 `ds_get_global_status`、`ds_get_method_scoreboard`、`ds_refresh_summary`、`ds_arxiv` |

因此它是原 DeepScientist Hermes MCP 插件业务能力的 Codex native 功能等价实现，不是 FastMCP / `.mcp.json` / MCP transport 的协议克隆。

## 不提供的内容

- 不使用 MCP：没有 `.mcp.json`，`plugin.json` 没有 server-transport 注册字段。
- 正常路径不调用外部 npm `ds` 命令。
- 不恢复 Web UI、TUI、social/browser connector 或 raw dispatcher。

## Codex 原生操作边界

DeepScientist-codex 负责研究语义层：quest 状态、持久用户需求、memory、artifact、baseline、正式实验记录、analysis campaign 状态、paper/reliability 流程，以及正式证据命令的 `ds_bash_exec` provenance。

常规操作层继续使用 Codex 原生能力：文件读写搜索、普通 shell、Git/GitHub、测试/构建/lint、进程监控和本地文档编辑。
