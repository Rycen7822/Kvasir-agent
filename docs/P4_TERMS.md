# P4 Terms: MCP-only Default and Codex Goal Context

P4 fixes the default research control plane for CodexScientist. These terms are normative for tests, docs, skills, and implementation.

## agent-facing surface

Content that Codex may see by default when operating the CodexScientist plugin: plugin metadata, defaultPrompt, the operator skill, runtime skill views loaded through MCP, MCP tool descriptions, MCP error payloads, and MCP suggested actions.

The agent-facing surface must present MCP-only default as the normal research path and must not advertise terminal compatibility commands as the default research path. Bare compatibility-command wording, including naked `csctl` references in MCP-loaded runtime skill content, is treated as agent-facing CLI guidance risk even when it is not an automatic fallback.

## hidden admin/debug CLI

The existing terminal compatibility entrypoints remain available for humans, admin/debug tasks, CI, migration, and recovery. They are compatibility tools, not the default Codex research path.

## MCP-only default

The default research control plane is MCP `cs_*` tools plus Codex-native file/search/edit/shell/Git/test/build/process capabilities. Research semantics are recorded through MCP/service calls.

## fail closed

When MCP is unavailable or a tool is missing, the default agent-facing response tells the operator to fix MCP/doctor/config or implement the MCP tool. It must not suggest switching the default research flow to terminal compatibility commands.

## Codex-goal-driven research loop adapter

`/goal` is Codex-native. CodexScientist does not implement slash commands. After Codex has entered goal context, CodexScientist provides MCP tools, bounded prompt/skill routing, state files, progress watchdog, checkpoint, and resume contracts for research progress.

## quest root

A quest root is the project-local directory that stores a single long-running research quest under `<project>/CodexScientist/quests/<quest_id>/`.

## method improvement gate

A required decision point after experiment or analysis evidence. It records negative memory, updates method scoreboard/frontier, checks novelty and claim evidence, and returns the next safe research action.
