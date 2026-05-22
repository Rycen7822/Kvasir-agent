---
name: codexscientist-quest-handoffs
title: Research Quest Handoffs
description: Create durable CodexScientist quest handoff documents, AGENTS.md files, researcher packages, and verified sync artifacts.
version: 1.0.1
metadata:
  hermes:
    category: research
    tags: [handoff, codexscientist, research, agents, synchronization, verification]
skill_role: companion
---

> Codex adapter note: this support skill is bundled for CodexScientist. Prefer the stable curated MCP `cs_*` tools for repeated CodexScientist state/status/context workflows. Load at most one support skill alongside the active stage. Runtime state lives under `<project>/CodexScientist/`.
> When a handoff becomes durable, record it with `cs_artifact_record` as a milestone/report and include the absolute quest path in the payload.

# Research Quest Handoffs

Use this skill when the user asks for onboarding notes, a guide for another agent, an `AGENTS.md`, a quick-start document, or a synced handoff for a research/CodexScientist quest.

## Core rule

Write the handoff into the quest filesystem. Do not leave it only in the final chat reply. Another agent should be able to start from the handoff file plus the referenced quest documents.

## Default output

Create or update a quest-root `AGENTS.md` unless the project already has a clearer convention.

Include these sections when relevant:

1. quest id, title, source root, synced/root copy paths, and handoff timestamp;
2. current quest state: status, active anchor/stage, baseline gate, pending messages/decisions, artifact and memory counts;
3. one-minute research/task summary;
4. authoritative reading order with relative paths;
5. durable literature/resource/artifact state;
6. main experimental or operational design that must be preserved;
7. writing, editing, and checking rules specific to the quest;
8. operational safety rules and local constraints;
9. suggested next action paths for document work, implementation/experiments, and synced-copy work.

## CodexScientist workflow

1. Read quest state with CodexScientist tools when available.
2. Read the active user requirements and the current authoritative quest documents before summarizing.
3. Write the handoff file under the source quest root.
4. If a second quest copy exists, sync the intended file or quest subtree explicitly unless the latest user instruction limits the work to the current quest/root only; in that case, state the no-sync constraint in the handoff and do not touch the secondary copy.
5. Record a milestone or report artifact for a meaningful handoff document.
6. Re-sync after artifact recording if the artifact write created new files or a new quest git commit.
7. Verify source and target before reporting completion.

## Sync verification

For a single handoff file, verify with:

- `sha256sum source target`
- `cmp -s source target`
- `wc -l source target`
- `stat -c '%n %s bytes %y' source target`

For full quest-copy verification, compare recursively by relative path and hash. Ignore `.git/` internals such as `.git/index`, which can differ after status checks even when working content is equivalent.

## Pitfalls

- Do not overwrite target-local project configuration while syncing, such as `CodexScientist/config/codex-native.yaml`, unless the user explicitly asks.
- Do not claim synced git heads match until after the final artifact/milestone write and any follow-up sync.
- Do not omit exact paths; future agents need absolute path anchors and relative reading order.
- Do not fabricate quest metrics from memory; read current state and files.

## Conservative status maintenance

When a long-running quest's `AGENTS.md`, formal command document, or execution plan becomes too long or stale, prefer a single concise current-status entry (for example `experiments/CURRENT_STATUS.md`) plus short pointers from the long documents. Preserve source-of-truth plans and run evidence; do not keep appending chronological handoff blocks. See `references/concise-current-status-maintenance.md`.

## Researcher handoff packages

When the user asks to send a quest to another researcher for analysis, create a compact no-code zip with a root `README_FOR_RESEARCHER.md`, manifest files, active idea docs, experiment plans, result reports, figures/tables, and small source-of-truth evidence artifacts. For external researcher analysis, default to a minimal tier (idea/protocol/status/report/final evidence only) and expand only on request; avoid bundling long command ledgers, full figure directories, or broad provenance if the user says the package is too cluttered. Exclude code, model weights/checkpoints, raw caches, PDFs unless requested, `.cs/`, and secondary workspace copies under current no-sync constraints. See `references/no-code-researcher-handoff-zip.md`.

## Single-file zero-start researcher handoffs

When the user asks for all necessary information in one Markdown file for another researcher to analyze from scratch, write a self-contained quest-root handoff such as `RESEARCHER_ZERO_START_ANALYSIS.md`. Include the project question, method route, current experiment state, key results, safe/unsafe claims, limitations, and suggested analysis order. If the recipient will not receive other files, do **not** lean on evidence paths; embed the judgment-critical method facts directly: key function formulas/calculations, active-vs-normative implementation differences, candidate enumeration, data/batching, trainable/frozen parameters, optimizer/schedule/eval cadence, verification fields, and explicit caveats about what is not implemented or not run. Read source-of-truth docs, implementation specs/code, configs, and final evidence while drafting, then loop back to patch omissions before validating. See `references/single-file-zero-start-researcher-handoff.md`.

## Reference

See `references/codexscientist-quest-handoff-sync.md` for the session-derived checklist and verification pattern.
