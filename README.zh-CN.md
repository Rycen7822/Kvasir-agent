# Kvasir-agent：Codex / Pi 研究证据插件

[English](README.md) · [安装](docs/INSTALL.md) · [使用](docs/USAGE.md) · [接口](docs/MCP.md)

默认提供 **1 个 MCP 服务器、4 个工具、1 个研究技能和 2 个 Delphi 入口技能**。宿主原生功能负责计划、文件、文献、代码、subagent 调度和研究判断；插件保留正式运行、指标校验、配对比较、证据来源和 Delphi 研究状态。Pi 默认使用 codemode 按需暴露工具。

| 工具 | 职责 |
| --- | --- |
| `ka_research_status` | 只读查询项目或运行状态，返回有限摘要和路径 |
| `ka_experiment` | `action=run` 校验配置并启动受管运行；`action=stop` 停止运行并保留真实终态 |
| `ka_evidence` | `action=check` 检查证据并保存报告；`action=import` 保存外部结果并保留未验证来源 |
| `ka_delphi` | 单入口操作 Idea-Spark 开放讨论/深度挖掘及 Ponder high/max；准备原生任务、收集完整文件和查询有限状态 |

运行规范采用按需读取的版本化文件。独立包装进程负责日志、超时、指标和派生结果；MCP 连接关闭后仍可完成收尾。日常研究无需维护哈希身份，也不反复扫描输入、产物或状态文件；进程完成、证据可用和科学结论分开记录。

研究记录保存资料、想法、候选、结论、审查及负结果，自动生成 v1、v2 等普通版本并保留正文、引文材料和审查目标副本；显式 CLI 注册与派生索引供宿主检索。旧哈希记录可直接读取，最新父版本或当前原文编辑不会使已保存的历史引用失效。Run v2 支持比较协议、候选快照、程序声明的进度与成本；未测量的成本和统计支持保持未知。见[研究记录](docs/RESEARCH_RECORDS.md)。

## 使用入口

按[安装说明](docs/INSTALL.md)安装并打开新会话。初始化只能由用户手动执行 [CLI](docs/ADMIN_CLI.md)，或明确提供独立 `manual/init/SKILL.md` 路径要求执行。它不注册到默认技能目录，不注入名称、描述、路径或正文，也不生成 AGENTS.md、Codex 项目说明或旧目录树。

研究证据项目使用 v3 清单和稳定身份。旧 v2/quest 数据通过显式预览、审查、应用迁移；证据读取和普通业务调用不会自动初始化、迁移或修复。Delphi 的 open 显式创建独立流程状态，其他操作使用已有 room_id/run_id。查看[文件规范](docs/EVIDENCE_SPECS.md)和[接口迁移表](docs/TOOL_MIGRATION.md)。

使用 `$kvasir-agent:delphi-idea-spark` 或 `$kvasir-agent:delphi-ponder-forge`。父端读取返回的完整策略和输入模板，通过 ka_delphi 准备/收集文件，通过宿主原生工具启动、等待和取消 agent。新增模式复用单一工具，专用说明按需读取。新分配使用新的 request_id，重试原操作沿用同一身份，不使用内容哈希。

## 项目来源

本项目基于 [DeepScientist](https://github.com/ResearAI/DeepScientist) 进行 Codex 适配与二次开发。参考项目及来源见 [英文 README](README.md#foundation-and-references)。
