# Kvasir-agent：Codex 研究证据插件

[English](README.md) · [安装](docs/INSTALL.md) · [使用](docs/USAGE.md) · [接口](docs/MCP.md)

默认只提供 **5 个 MCP 工具、1 个研究技能**。Codex 原生功能负责计划、文件、文献、代码和研究判断；插件保留正式运行、指标校验和证据来源记录。

| 工具 | 职责 |
| --- | --- |
| `ka_research_status` | 只读查询项目或运行状态，返回有限摘要和路径 |
| `ka_experiment_run` | 校验文件规范与受保护输入，启动正式运行 |
| `ka_experiment_stop` | 停止受管运行，保留真实终态 |
| `ka_evidence_check` | 检查环境、运行或主张材料，保存报告 |
| `ka_evidence_import` | 保存外部结果，保留未验证来源 |

运行规范采用按需读取的版本化文件。独立包装进程负责日志、超时、指标、输入哈希复查和派生结果；MCP 连接关闭后仍可完成收尾。材料完整性通过不等于科学结论成立。

## 使用入口

按[安装说明](docs/INSTALL.md)安装并打开新会话。初始化只能由用户手动执行 [CLI](docs/ADMIN_CLI.md)，或明确提供独立 `manual/init/SKILL.md` 路径要求执行。它不注册到默认技能目录，不注入名称、描述、路径或正文，也不生成 AGENTS.md、Codex 项目说明或旧目录树。

研究项目使用 v3 清单和稳定身份。旧 v2/quest 数据通过显式预览、审查、应用迁移；读取和普通业务调用不会自动初始化、迁移或修复。查看[文件规范](docs/EVIDENCE_SPECS.md)和[接口迁移表](docs/TOOL_MIGRATION.md)。

## 项目来源

本项目基于 [DeepScientist](https://github.com/ResearAI/DeepScientist) 进行 Codex 适配与二次开发。参考项目及来源见 [英文 README](README.md#foundation-and-references)。
