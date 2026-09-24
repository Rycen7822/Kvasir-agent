# Kvasir-agent for Codex

[中文](README.zh-CN.md) · [Install](docs/INSTALL.md) · [Usage](docs/USAGE.md) · [MCP](docs/MCP.md)

A compact research evidence plugin: **five MCP tools, one active skill**, explicit project state and automatic experiment records. Codex handles planning, files, literature, code and research interpretation.

| Tool | Purpose |
| --- | --- |
| `ka_research_status` | Read bounded project/run state without writes |
| `ka_experiment_run` | Validate and start one reproducible managed run |
| `ka_experiment_stop` | Stop a run while preserving terminal facts |
| `ka_evidence_check` | Check environment, run or claim material integrity |
| `ka_evidence_import` | Preserve external results and unverified origin |

Specifications are versioned files, loaded only as needed. Runs retain input hashes, metrics, logs and request snapshots; a detached wrapper completes recording even after MCP disconnects. Verified material integrity is not scientific validity.

## Start

Follow [installation](docs/INSTALL.md), then explicitly create project state using the [manual maintenance command](docs/ADMIN_CLI.md). Initialization has no MCP tool and its independent manual is outside automatic skill discovery. It does not generate AGENTS.md or Codex project notes.

Read [file contracts](docs/EVIDENCE_SPECS.md) for a managed run. Old v2/quest state requires reviewed plan/apply migration; ordinary calls never create, migrate or repair state. The [migration table](docs/TOOL_MIGRATION.md) describes replacements for the earlier 24-tool API.

## Foundation and References


This project is primarily a secondary development and Codex-oriented adaptation based on [DeepScientist](https://github.com/ResearAI/DeepScientist). The `Kvasir-agent` naming in this repository refers to this Codex plugin/runtime adaptation layer rather than a claim of an independent upstream origin.

The design and implementation also reference or draw inspiration from:

- [Auto-claude-code-research-in-sleep](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep)
- [autoresearch](https://github.com/karpathy/autoresearch)
- [EvoScientist](https://github.com/EvoScientist/EvoScientist)
- [ai-researcher](https://github.com/hkuds/ai-researcher)
- [AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2)
- [AgentLaboratory](https://github.com/SamuelSchmidgall/AgentLaboratory)
- [ml-intern](https://github.com/huggingface/ml-intern)
