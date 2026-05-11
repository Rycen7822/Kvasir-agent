<h1 align="center">
  DeepScientist × Codex Native Adapter
</h1>

<p align="center">
  <a href="https://github.com/ResearAI/DeepScientist">Upstream DeepScientist</a> |
  <a href="README.zh-CN.md">中文文档</a> |
  <a href="docs/INSTALL.md">Install Guide</a> |
  <a href="docs/USAGE.md">Usage Guide</a> |
  <a href=".codex-plugin/plugin.json">Codex Manifest</a>
</p>

<p align="center">
  <a href=".codex-plugin/plugin.json"><img alt="Codex Native" src="https://img.shields.io/badge/Codex-Native-4D6A7A?style=for-the-badge"></a>
  <a href="#what-it-deliberately-does-not-provide"><img alt="MCP Free" src="https://img.shields.io/badge/MCP-Free-2E7D32?style=for-the-badge"></a>
  <a href="docs/USAGE.md"><img alt="48 public ds tools" src="https://img.shields.io/badge/Public%20Tools-48%20canonical%20ds__%2A-2563EB?style=for-the-badge"></a>
  <a href="#project-local-runtime"><img alt="Project local runtime" src="https://img.shields.io/badge/Runtime-Project%20Local-7C3AED?style=for-the-badge"></a>
</p>

<p align="center">
  <strong>Native Codex install</strong> ·
  <strong>No MCP transport</strong> ·
  <strong>Project-local research state</strong> ·
  <strong>Auditable DeepScientist provenance</strong>
</p>

<p align="center">
  <strong>Codex does the mechanical work. DeepScientist records the research meaning.</strong>
</p>

---

DeepScientist-codex presents the existing DeepScientist research runtime as a native Codex CLI plugin. It packages the headless runtime, curated `ds_*` schemas, Codex skills, support skills, and the `scripts/dsctl.py` control surface into one installable adapter.

It follows the upstream DeepScientist README style while keeping the adapter boundary explicit: this is a Codex-native functional equivalent of the original Hermes/MCP business surface, not an MCP protocol clone.

## Why This Adapter Exists

DeepScientist is built for long-horizon research work: quests, baselines, experiments, artifacts, memory, analysis, and paper-ready outputs. Codex is already good at file edits, command execution, tests, and Git workflows. This adapter lets those two roles meet cleanly:

| Common pain point | What this adapter keeps durable |
| --- | --- |
| Research state disappears into chat history | Quest state, memory cards, artifacts, and milestones stay in the project runtime. |
| Experiments and logs are scattered | Formal evidence commands can go through `ds_bash_exec` with quest-local logs and session state. |
| Paper/reliability work is hard to audit later | Paper bundles, strict-research ledgers, reliability cards, and analysis slices are recorded as DeepScientist artifacts. |
| Native Codex work gets buried under plugin ceremony | Routine file, shell, Git, test, build, and process work remains Codex-native. |

## At A Glance

| Area | What you get |
| --- | --- |
| Native transport | `scripts/dsctl.py` returns `transport="codex-native-cli"` and `mcp=false`. |
| Public tool surface | A 48-tool public canonical `ds_*` manifest; legacy `deepscientist_*` names are hidden compatibility aliases only. |
| Research state | Project-local quests, memory, artifacts, baselines, experiments, paper bundles, analysis campaigns, and event reads. |
| Codex skills | `deepscientist-codex` plus adapted stage/support skills for experiments, handoffs, writing plans, paper reliability, and review. |
| Safety boundary | No `.mcp.json`, no FastMCP server, no MCP server transport, and no external ds command for normal operation. |

## What Can It Help Codex Get Done?

### 1. Start and maintain real DeepScientist quests

- create or inspect quests with canonical `ds_*` tools
- preserve durable requirements and mode state
- keep runtime data under the research project instead of global agent state

### 2. Turn research operations into auditable artifacts

- write memory cards, milestones, decision records, and artifacts
- record baselines, main experiment runs, analysis slices, and paper bundles
- read quest events through `ds_events`

### 3. Keep Codex fast for normal development work

- use Codex-native file/search/edit, shell, tests, Git/GitHub, process monitoring, and local prose edits
- reserve `ds_bash_exec` for formal experiment, baseline, analysis, or paper-facing evidence commands

### 4. Package the DeepScientist support workflow for Codex

- ship `deepscientist-experiment-execution`
- ship `deepscientist-quest-handoffs`
- ship `deepscientist-writing-plans`
- ship `deepscientist-paper-reliability-verification`
- ship `deepscientist-review`

## Quick Start

From this `DeepScientist-codex` directory:

```bash
python scripts/dsctl.py doctor --format json
python scripts/dsctl.py list-tools --format json
```

Install into your normal Codex home:

```bash
bash scripts/install.sh
```

After install, initialize a research project and verify the project-local runtime:

```bash
bash ~/.codex/plugins/deepscientist-codex/scripts/init_project.sh /path/to/project
python ~/.codex/plugins/deepscientist-codex/scripts/dsctl.py --project-root /path/to/project doctor --format json
```

Create a quest from a research project root:

```bash
python ~/.codex/plugins/deepscientist-codex/scripts/dsctl.py call ds_new_quest \
  --json '{"goal":"my research goal","title":"My Quest","workspace_mode":"copilot"}' \
  --format json
```

Then use:

```bash
python ~/.codex/plugins/deepscientist-codex/scripts/dsctl.py call <ds_tool_name> \
  --json '<object>' \
  --format json
```

for durable quest, memory, artifact, baseline, experiment, analysis, strict-research, paper-fetch, and paper-bundle operations.

## Project-Local Runtime

When commands run from a research project root, DeepScientist state is stored in:

```text
<project>/DeepScientist/
```

This keeps quests, artifacts, memory, bash provenance, and paper bundles with the research project rather than in global Codex or Hermes state.

## Install Details

`scripts/install.sh` performs a local-personal Codex plugin install:

1. Copies this directory to `~/.codex/plugins/deepscientist-codex`.
2. If an installed copy already exists, moves it to `~/.codex/plugins/deepscientist-codex.backup-<timestamp>`.
3. Registers the local marketplace entry in `~/.agents/plugins/marketplace.json`.
4. Enables `[plugins."deepscientist-codex@local-personal"]` in `~/.codex/config.toml`.
5. Runs `scripts/doctor.py`.

For normal Codex use, leave `CODEX_HOME` and `AGENTS_HOME` unset. They are honored for isolated smoke tests or deliberate non-default installs.

See [docs/INSTALL.md](docs/INSTALL.md) and [docs/USAGE.md](docs/USAGE.md) for full details.

## Original Hermes MCP Equivalence

This adapter preserves business-workflow effects rather than MCP protocol shape:

| Original DeepScientist/Hermes surface | Codex-native equivalent |
| --- | --- |
| `memory.write/read/search/list_recent` | `ds_memory_write`, `ds_memory_read`, `ds_memory_search`, `ds_memory_list_recent` |
| `artifact.record` and quest artifact flows | `ds_artifact_record` plus specialized `ds_*` artifact tools |
| event reads | `ds_events` |
| `bash_exec` | `ds_bash_exec`, retaining quest-local execution state and logs |
| artifact convenience/introspection helpers | Matching `ds_*` wrappers such as `ds_get_global_status`, `ds_get_method_scoreboard`, `ds_refresh_summary`, and `ds_arxiv` |

The names, CLI entry point, and transport are Codex-native by design. There is no FastMCP server, no `.mcp.json`, and no MCP server transport.

## What It Deliberately Does Not Provide

- This is not MCP. There is no `.mcp.json` and `plugin.json` has no server-transport registry field.
- It does not call the external ds command for normal operation.
- It does not expose Web UI, TUI, social connectors, browser connectors, or raw dispatch surfaces.

## Codex-Native Operation Boundary

Use DeepScientist-codex for the research semantic layer: quest state, durable requirements, memory, artifacts, baselines, formal experiment records, analysis campaign state, paper/reliability workflows, and `ds_bash_exec` provenance for formal evidence commands.

Use Codex-native capabilities for routine operation-layer work: file/search/edit, ordinary shell, Git/GitHub mechanics, tests/builds/lint, process monitoring, and local prose editing.
