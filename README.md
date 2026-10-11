# Kvasir-agent for Codex and Pi

[中文](README.zh-CN.md) · [Install](docs/INSTALL.md) · [Usage](docs/USAGE.md) · [MCP](docs/MCP.md)

A compact research evidence plugin: **three MCP tools**, the research skill and two Delphi workflow skills, explicit project state and automatic experiment records. Codex/Pi handles planning, files, literature, code and research interpretation.

| Tool | Purpose |
| --- | --- |
| `ka_research_status` | Read bounded project/run state without writes |
| `ka_experiment` | `action=run` starts a managed run; `action=stop` stops a recorded run and preserves terminal facts |
| `ka_evidence` | `action=check` checks evidence and saves a report; `action=import` preserves external results and unverified origin |

Specifications are versioned files, loaded only as needed. Runs retain declared inputs, metrics, logs and request snapshots; a detached wrapper completes recording even after MCP disconnects. Ordinary research needs no hash identifiers or repeated byte checks. Research versions use automatic `v1`, `v2`, etc. and retain material copies. Execution, available evidence and scientific validity remain separate.

## Start

Follow [installation](docs/INSTALL.md), then explicitly create project state using the [manual maintenance command](docs/ADMIN_CLI.md). Initialization has no MCP tool and its independent manual is outside automatic skill discovery. It does not generate AGENTS.md or Codex project notes.

Read [file contracts](docs/EVIDENCE_SPECS.md) for a managed run, paired comparison or saved-version check. Use [research records](docs/RESEARCH_RECORDS.md) for papers, ideas, history and reviews. Old v2/quest state requires reviewed plan/apply migration; ordinary calls never create, migrate or repair state. The [migration table](docs/TOOL_MIGRATION.md) describes replacements for the earlier 24-tool API.

## Foundation and References


This project is primarily a secondary development and Codex-oriented adaptation based on [DeepScientist](https://github.com/ResearAI/DeepScientist). The `Kvasir-agent` naming in this repository refers to this Codex plugin adaptation layer rather than a claim of an independent upstream origin.

The design and implementation also reference or draw inspiration from:

- [Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep)
- [autoresearch](https://github.com/karpathy/autoresearch)
- [EvoScientist](https://github.com/EvoScientist/EvoScientist)
- [ai-researcher](https://github.com/hkuds/ai-researcher)
- [AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2)
- [AgentLaboratory](https://github.com/SamuelSchmidgall/AgentLaboratory)
- [ml-intern](https://github.com/huggingface/ml-intern)
