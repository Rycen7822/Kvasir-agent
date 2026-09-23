<h1 align="center">
  Kvasir-agent × Codex MCP Control Plane
</h1>

<p align="center">
  <a href="https://github.com/ResearAI/DeepScientist">Upstream DeepScientist</a> |
  <a href="README.zh-CN.md">中文文档</a> |
  <a href="docs/INSTALL.md">Install Guide</a> |
  <a href="docs/USAGE.md">Usage Guide</a> |
  <a href=".codex-plugin/plugin.json">Codex Manifest</a>
</p>

<p align="center">
  <strong>MCP-only default</strong> ·
  <strong>Codex-native /goal boundary</strong> ·
  <strong>Project-local research state</strong> ·
  <strong>Auditable Kvasir-agent provenance</strong>
</p>

---

Kvasir-agent presents a DeepScientist-derived research runtime as a Codex CLI plugin. The default research control plane is MCP-only: Codex uses compact `ka_*` MCP tools for research semantics, while Codex-native file/search/edit/shell/Git/test/build/process capabilities handle ordinary mechanical work.

`/goal` is Codex-native. Kvasir-agent does not implement, register, intercept, or simulate slash commands. After Codex has entered goal context, Kvasir-agent provides curated MCP tools for root-bound research state, durable requirements, memory, artifacts, baselines, experiments, analysis, paper/reliability work, checkpoint/resume anchors, manual diagnostics, novelty support, and claim gates.

Administrative terminal commands are documented only in [docs/ADMIN_CLI.md](docs/ADMIN_CLI.md). They are for human/admin/debug/CI/recovery compatibility, not the default Codex research path.

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

## Why This Adapter Exists

| Common pain point | What this adapter keeps durable |
| --- | --- |
| Research state disappears into chat history | Root-bound research state, requirements, checkpoints, source refs, and milestones stay in the project runtime. |
| Experiments and logs are scattered | Formal evidence commands can go through `ka_bash_exec` with project-local logs and session state. |
| Paper/reliability work is hard to audit later | Paper bundles, strict-research ledgers, reliability cards, claim gate decisions, and analysis slices are recorded as Kvasir-agent artifacts. |
| Native Codex work gets buried under plugin ceremony | Routine file, shell, Git, test, build, and process work remains Codex-native. |

## At A Glance

| Area | What you get |
| --- | --- |
| Control plane | MCP-only default through `scripts/ka_mcp.py`; admin terminal commands are isolated in `docs/ADMIN_CLI.md`. |
| Public tool surface | Curated `ka_*` tools. |
| MCP profiles | Default discovery exposes 24 public research tools with parameter schemas; explicit profiles are optional filters. Executor tools remain gated. |
| Long-run recovery | `ka_research_read(operation="status")`, `ka_research_read(operation="resume")`, `ka_research_read(operation="delta")`, and `ka_checkpoint` provide passive recovery anchors; watchdog-style diagnostics remain hidden/admin-only in the default Codex MCP surface. |
| Method improvement | Public tools such as `ka_method_record(operation="result")`, `ka_research_read(operation="methods")`, and `ka_claim_gate` close the experiment -> novelty -> evidence loop; autonomous idea selection remains hidden from default MCP. |
| Research state | A project-local `Kvasir-agent/` research root with memory, artifacts, baselines, experiments, paper bundles, analysis campaigns, and bounded event/delta summaries. |
| Codex skills | Seven workflows: research workspace, experiments, writing/review, strict research, paper reliability, figures and handoffs. |

## Quick Start

Requires Python 3.10+, PyYAML, jsonschema and a Codex CLI with plugin support. Follow the [installation guide](docs/INSTALL.md) to register the source in a marketplace, then install:

```bash
bash scripts/install.sh kvasir-agent@local-personal
codex plugin list
```

Open a new thread. Codex discovers seven native skills and the bundled MCP server. Default discovery advertises 24 research tools with parameter schemas; ordinary research tools need no profile switching.

Local discovery check and optional project note:

```bash
python3 scripts/ka_mcp.py --stdio-smoke tools/list
bash scripts/init_project.sh /path/to/project
```

Pass the absolute research root as `project` on every MCP research call, starting with `ka_research_read(operation="status")` and `ka_research_read(operation="resume")`. Record constraints with `ka_record_user_requirement`; the first durable write initializes research state.

## Project-Local Runtime

When commands run from a research project root, Kvasir-agent state is stored in:

```text
<project>/Kvasir-agent/
```

This keeps root-bound research state, artifacts, memory, bash provenance, manual diagnostic records, checkpoints, analysis slices, claim decisions, and paper bundles with the research project rather than in global Codex state. `Kvasir-agent/quests/` is only a legacy migration input, not a new-write target.

## Installation and Updates

`.codex-plugin/plugin.json` declares skills and `.mcp.json`. `scripts/install.sh` delegates to `codex plugin add`; Codex owns cache, enablement and MCP lifecycle. Update the source version before reinstalling, then open a fresh thread. See [installation and migration](docs/INSTALL.md) for old global MCP registrations.

## Research Contracts

Retain baselines, protected-file hashes, experiment lineage, formal logs, feedback reconciliation and research handoffs. Codex owns task continuation, skill discovery, ordinary commands and Git. Novelty contracts preserve unassessed hypotheses without automatic scores. `ka_record_main_experiment` records data; `ka_claim_gate` checks evidence completeness. Scientific validity requires reviewing the evidence.

## Original Kvasir-agent MCP Equivalence

This adapter preserves business-workflow effects rather than MCP protocol shape:

| Original Kvasir-agent surface | Codex-native equivalent |
| --- | --- |
| `memory.write/read/search/list_recent` | `ka_memory_write`, `ka_memory_query` |
| `artifact.record` and research artifact flows | `ka_artifact_record` plus specialized public `ka_*` artifact tools such as `ka_artifact_index` |
| event reads | `ka_research_read(operation="status")`, `ka_research_read(operation="delta")`, and `ka_research_read(operation="resume")` summaries |
| `bash_exec` | `ka_bash_exec`, retaining project-local execution state and logs when formal provenance is required |
| artifact convenience/introspection helpers | `ka_research_read(operation="status")`, `ka_research_read(operation="methods")`; update summaries through Codex file editing. |

## What It Deliberately Does Not Provide

- It does not expose an all-tools/full-runtime MCP surface.
- It does not implement slash commands.
- It does not use terminal compatibility commands for normal research operation.
- It does not expose Web UI, TUI, social connectors, browser connectors, or raw dispatch surfaces.

## Codex-Native Operation Boundary

Use Kvasir-agent for the research semantic layer: root-bound research state, durable requirements, memory, artifacts, baselines, formal experiment records, analysis campaign state, paper/reliability workflows, manual diagnostics, checkpoint/resume, claim gate, and `ka_bash_exec` provenance for formal evidence commands.

Use Codex-native capabilities for routine operation-layer work: file/search/edit, ordinary shell, Git/GitHub mechanics, tests/builds/lint, process monitoring, and local prose editing.

See [public tool migration](docs/TOOL_MIGRATION.md) for the 24-tool API and retired entries.
