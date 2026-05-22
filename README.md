<h1 align="center">
  CodexScientist × Codex MCP Control Plane
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
  <strong>Auditable CodexScientist provenance</strong>
</p>

---

CodexScientist-codex presents a DeepScientist-derived research runtime as a Codex CLI plugin. The default research control plane is MCP-only: Codex uses compact `cs_*` MCP tools for research semantics, while Codex-native file/search/edit/shell/Git/test/build/process capabilities handle ordinary mechanical work.

`/goal` is Codex-native. CodexScientist does not implement, register, intercept, or simulate slash commands. After Codex has entered goal context, CodexScientist provides curated MCP tools for root-bound research state, durable requirements, memory, artifacts, baselines, experiments, analysis, paper/reliability work, checkpoint/resume anchors, manual diagnostics, novelty support, and claim gates.

Administrative terminal commands are documented only in [docs/ADMIN_CLI.md](docs/ADMIN_CLI.md). They are for human/admin/debug/CI/recovery compatibility, not the default Codex research path.

## Foundation and References

This project is primarily a secondary development and Codex-oriented adaptation based on [DeepScientist](https://github.com/ResearAI/DeepScientist). The `CodexScientist` naming in this repository refers to this Codex plugin/runtime adaptation layer rather than a claim of an independent upstream origin.

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
| Experiments and logs are scattered | Formal evidence commands can go through `cs_bash_exec` with project-local logs and session state. |
| Paper/reliability work is hard to audit later | Paper bundles, strict-research ledgers, reliability cards, claim gate decisions, and analysis slices are recorded as CodexScientist artifacts. |
| Native Codex work gets buried under plugin ceremony | Routine file, shell, Git, test, build, and process work remains Codex-native. |

## At A Glance

| Area | What you get |
| --- | --- |
| Control plane | MCP-only default through `scripts/cs_mcp.py`; admin terminal commands are isolated in `docs/ADMIN_CLI.md`. |
| Public tool surface | Curated canonical `cs_*` tools; legacy `codexscientist_*` names are hidden compatibility aliases only. |
| MCP profiles | Default core profile exposes 11 tools. Wider explicit profiles are `evidence`, `formal_run`, `literature`, and `paper_write`; `stage` is a label, not a tool-list filter. |
| Long-run recovery | `cs_status`, `cs_resume_brief`, `cs_pack_delta`, and `cs_checkpoint` provide passive recovery anchors; watchdog-style diagnostics remain hidden/admin-only in the default Codex MCP surface. |
| Method improvement | Public tools such as `cs_update_method_scoreboard`, `cs_get_optimization_frontier`, and `cs_claim_gate` close the experiment -> novelty -> evidence loop; autonomous idea selection remains hidden from default MCP. |
| Research state | A project-local `CodexScientist/` research root with memory, artifacts, baselines, experiments, paper bundles, analysis campaigns, and bounded event/delta summaries. |
| Codex skills | `codexscientist-codex` plus adapted support skills for experiments, handoffs, writing plans, paper reliability, and review. |

## Quick Start

From this `CodexScientist-codex` directory:

```bash
python scripts/cs_mcp.py --stdio-smoke initialize
python scripts/cs_mcp.py --stdio-smoke tools/list
python scripts/p4_acceptance.py
```

Install into your normal Codex home:

```bash
bash scripts/install.sh
```

The installer copies the plugin, enables `[plugins."codexscientist-codex@local-personal"]`, and registers the MCP server in Codex config. If you need to register manually, use the same stdio entrypoint:

```bash
codex mcp add codexscientist-codex -- python -B ~/.codex/plugins/codexscientist-codex/scripts/cs_mcp.py
```

Initialize a research project with the project helper:

```bash
bash ~/.codex/plugins/codexscientist-codex/scripts/init_project.sh /path/to/project
```

Then operate through MCP `cs_*` tools such as `cs_status`, `cs_record_user_requirement`, `cs_create_local_baseline`, `cs_confirm_baseline`, `cs_submit_idea`, `cs_record_main_experiment`, `cs_create_analysis_campaign`, `cs_record_analysis_slice`, `cs_resume_brief`, and `cs_checkpoint`. The first durable write lazily creates `<project>/CodexScientist/research.yaml`; no separate lifecycle initialization step is required.

## Project-Local Runtime

When commands run from a research project root, CodexScientist state is stored in:

```text
<project>/CodexScientist/
```

This keeps root-bound research state, artifacts, memory, bash provenance, manual diagnostic records, checkpoints, analysis slices, claim decisions, and paper bundles with the research project rather than in global Codex state. `CodexScientist/quests/` is only a legacy migration input, not a new-write target.

## Install Details

`scripts/install.sh` performs a local-personal Codex plugin install:

1. Copies this directory to `~/.codex/plugins/codexscientist-codex`.
2. If an installed copy already exists, moves it to `~/.codex/plugins/codexscientist-codex.backup-<timestamp>`.
3. Registers the local marketplace entry in `~/.agents/plugins/marketplace.json`.
4. Enables `[plugins."codexscientist-codex@local-personal"]` in `~/.codex/config.toml`.
5. Registers `[mcp_servers.codexscientist-codex]` in `~/.codex/config.toml`.
6. Runs `scripts/doctor.py` without leaving Python bytecode in the installed copy.

For normal Codex use, leave `CODEX_HOME` and `AGENTS_HOME` unset. They are honored for isolated smoke tests or deliberate non-default installs.

See [docs/INSTALL.md](docs/INSTALL.md), [docs/USAGE.md](docs/USAGE.md), [docs/MCP.md](docs/MCP.md), and [docs/REPOSITORY_LAYOUT.md](docs/REPOSITORY_LAYOUT.md) for install, usage, MCP, and repository organization details.

## Original CodexScientist MCP Equivalence

This adapter preserves business-workflow effects rather than MCP protocol shape:

| Original CodexScientist surface | Codex-native equivalent |
| --- | --- |
| `memory.write/read/search/list_recent` | `cs_memory_write`, `cs_memory_read`, `cs_memory_search`, `cs_memory_list_recent` |
| `artifact.record` and research artifact flows | `cs_artifact_record` plus specialized public `cs_*` artifact tools such as `cs_artifact_index` |
| event reads | `cs_status`, `cs_pack_delta`, and compact `cs_get_quest_state` summaries |
| `bash_exec` | `cs_bash_exec`, retaining project-local execution state and logs when formal provenance is required |
| artifact convenience/introspection helpers | Public `cs_*` wrappers such as `cs_status`, `cs_get_method_scoreboard`, `cs_refresh_summary`, and `cs_arxiv` |

## What It Deliberately Does Not Provide

- It does not expose an all-tools/full-runtime MCP surface.
- It does not implement slash commands.
- It does not use terminal compatibility commands for normal research operation.
- It does not expose Web UI, TUI, social connectors, browser connectors, or raw dispatch surfaces.

## Codex-Native Operation Boundary

Use CodexScientist-codex for the research semantic layer: root-bound research state, durable requirements, memory, artifacts, baselines, formal experiment records, analysis campaign state, paper/reliability workflows, manual diagnostics, checkpoint/resume, claim gate, and `cs_bash_exec` provenance for formal evidence commands.

Use Codex-native capabilities for routine operation-layer work: file/search/edit, ordinary shell, Git/GitHub mechanics, tests/builds/lint, process monitoring, and local prose editing.
