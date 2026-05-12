<h1 align="center">
  CodexScientist × Codex MCP Control Plane
</h1>

<p align="center">
  <a href="https://github.com/ResearAI/CodexScientist">Upstream CodexScientist</a> |
  <a href="README.zh-CN.md">中文文档</a> |
  <a href="docs/INSTALL.md">Install Guide</a> |
  <a href="docs/USAGE.md">Usage Guide</a> |
  <a href=".codex-plugin/plugin.json">Codex Manifest</a>
</p>

<p align="center">
  <a href=".codex-plugin/plugin.json"><img alt="Codex Native" src="https://img.shields.io/badge/Codex-Native-4D6A7A?style=for-the-badge"></a>
  <a href="#what-it-deliberately-does-not-provide"><img alt="Stable curated MCP" src="https://img.shields.io/badge/MCP-Stable%20Curated-2E7D32?style=for-the-badge"></a>
  <a href="docs/USAGE.md"><img alt="48 public cs tools" src="https://img.shields.io/badge/Public%20Tools-48%20canonical%20cs__%2A-2563EB?style=for-the-badge"></a>
  <a href="#project-local-runtime"><img alt="Project local runtime" src="https://img.shields.io/badge/Runtime-Project%20Local-7C3AED?style=for-the-badge"></a>
</p>

<p align="center">
  <strong>Stable curated MCP</strong> ·
  <strong>CLI fallback</strong> ·
  <strong>Project-local research state</strong> ·
  <strong>Auditable CodexScientist provenance</strong>
</p>

<p align="center">
  <strong>Codex does the mechanical work. CodexScientist records the research meaning.</strong>
</p>

---

CodexScientist-codex presents the existing CodexScientist research runtime as a Codex CLI plugin with a stable curated MCP control plane. It packages the headless runtime, curated `cs_*` schemas, Codex skills, support skills, `scripts/cs_mcp.py`, and the `scripts/csctl.py` CLI fallback into one installable adapter.

It follows the upstream CodexScientist README style while keeping the adapter boundary explicit: MCP is the small stable control plane for repeated research workflows, while Codex-native tools still handle routine file, shell, Git, test, build, and process work.

## Why This Adapter Exists

CodexScientist is built for long-horizon research work: quests, baselines, experiments, artifacts, memory, analysis, and paper-ready outputs. Codex is already good at file edits, command execution, tests, and Git workflows. This adapter lets those two roles meet cleanly:

| Common pain point | What this adapter keeps durable |
| --- | --- |
| Research state disappears into chat history | Quest state, memory cards, artifacts, and milestones stay in the project runtime. |
| Experiments and logs are scattered | Formal evidence commands can go through `cs_bash_exec` with quest-local logs and session state. |
| Paper/reliability work is hard to audit later | Paper bundles, strict-research ledgers, reliability cards, and analysis slices are recorded as CodexScientist artifacts. |
| Native Codex work gets buried under plugin ceremony | Routine file, shell, Git, test, build, and process work remains Codex-native. |

## At A Glance

| Area | What you get |
| --- | --- |
| Control plane | `scripts/cs_mcp.py` exposes stable curated MCP; `scripts/csctl.py` remains CLI fallback. |
| Public tool surface | A 48-tool public canonical `cs_*` manifest; legacy `codexscientist_*` names are hidden compatibility aliases only. |
| Research state | Project-local quests, memory, artifacts, baselines, experiments, paper bundles, analysis campaigns, and event reads. |
| Codex skills | `codexscientist-codex` plus adapted stage/support skills for experiments, handoffs, writing plans, paper reliability, and review. |
| Safety boundary | Stable curated MCP only; no all-tools/full-runtime MCP; no external cs command for normal operation. |

## What Can It Help Codex Get Done?

### 1. Start and maintain real CodexScientist quests

- create or inspect quests with canonical `cs_*` tools
- preserve durable requirements and mode state
- keep runtime data under the research project instead of global agent state

### 2. Turn research operations into auditable artifacts

- write memory cards, milestones, decision records, and artifacts
- record baselines, main experiment runs, analysis slices, and paper bundles
- read quest events through `cs_events`

### 3. Keep Codex fast for normal development work

- use Codex-native file/search/edit, shell, tests, Git/GitHub, process monitoring, and local prose edits
- reserve `cs_bash_exec` for formal experiment, baseline, analysis, or paper-facing evidence commands

### 4. Package the CodexScientist support workflow for Codex

- ship `codexscientist-experiment-execution`
- ship `codexscientist-quest-handoffs`
- ship `codexscientist-writing-plans`
- ship `codexscientist-paper-reliability-verification`
- ship `codexscientist-review`

## Quick Start

From this `CodexScientist-codex` directory:

```bash
python scripts/cs_mcp.py --stdio-smoke initialize
python scripts/cs_mcp.py --stdio-smoke tools/list
python scripts/csctl.py doctor --format json
```

Install into your normal Codex home:

```bash
bash scripts/install.sh
```

After install, initialize a research project and verify the project-local runtime:

```bash
bash ~/.codex/plugins/codexscientist-codex/scripts/init_project.sh /path/to/project
python ~/.codex/plugins/codexscientist-codex/scripts/csctl.py --project-root /path/to/project doctor --format json
```

Create a quest from a research project root:

```bash
python ~/.codex/plugins/codexscientist-codex/scripts/csctl.py call cs_new_quest \
  --json '{"goal":"my research goal","title":"My Quest","workspace_mode":"copilot"}' \
  --format json
```

Then use:

```bash
python ~/.codex/plugins/codexscientist-codex/scripts/csctl.py call <cs_tool_name> \
  --json '<object>' \
  --format json
```

for durable quest, memory, artifact, baseline, experiment, analysis, strict-research, paper-fetch, and paper-bundle operations.

## Project-Local Runtime

When commands run from a research project root, CodexScientist state is stored in:

```text
<project>/CodexScientist/
```

This keeps quests, artifacts, memory, bash provenance, and paper bundles with the research project rather than in global Codex or Hermes state.

## Install Details

`scripts/install.sh` performs a local-personal Codex plugin install:

1. Copies this directory to `~/.codex/plugins/codexscientist-codex`.
2. If an installed copy already exists, moves it to `~/.codex/plugins/codexscientist-codex.backup-<timestamp>`.
3. Registers the local marketplace entry in `~/.agents/plugins/marketplace.json`.
4. Enables `[plugins."codexscientist-codex@local-personal"]` in `~/.codex/config.toml`.
5. Runs `scripts/doctor.py`.

For normal Codex use, leave `CODEX_HOME` and `AGENTS_HOME` unset. They are honored for isolated smoke tests or deliberate non-default installs.

See [docs/INSTALL.md](docs/INSTALL.md), [docs/USAGE.md](docs/USAGE.md), and [docs/REPOSITORY_LAYOUT.md](docs/REPOSITORY_LAYOUT.md) for install, usage, and repository organization details.

## Original Hermes MCP Equivalence

This adapter preserves business-workflow effects rather than MCP protocol shape:

| Original CodexScientist/Hermes surface | Codex-native equivalent |
| --- | --- |
| `memory.write/read/search/list_recent` | `cs_memory_write`, `cs_memory_read`, `cs_memory_search`, `cs_memory_list_recent` |
| `artifact.record` and quest artifact flows | `cs_artifact_record` plus specialized `cs_*` artifact tools |
| event reads | `cs_events` |
| `bash_exec` | `cs_bash_exec`, retaining quest-local execution state and logs |
| artifact convenience/introspection helpers | Matching `cs_*` wrappers such as `cs_get_global_status`, `cs_get_method_scoreboard`, `cs_refresh_summary`, and `cs_arxiv` |

The stable MCP tools and CLI fallback preserve the same business-workflow effects while sharing the service layer.

## What It Deliberately Does Not Provide

- It does not expose an all-tools/full-runtime MCP surface.
- It does not call the external cs command for normal operation.
- It does not expose Web UI, TUI, social connectors, browser connectors, or raw dispatch surfaces.

## Codex-Native Operation Boundary

Use CodexScientist-codex for the research semantic layer: quest state, durable requirements, memory, artifacts, baselines, formal experiment records, analysis campaign state, paper/reliability workflows, and `cs_bash_exec` provenance for formal evidence commands.

Use Codex-native capabilities for routine operation-layer work: file/search/edit, ordinary shell, Git/GitHub mechanics, tests/builds/lint, process monitoring, and local prose editing.
