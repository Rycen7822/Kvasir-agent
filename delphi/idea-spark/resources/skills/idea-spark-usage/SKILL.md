---
name: idea-spark-usage
description: Run open research discussions or IdeaScientist-inspired deep exploration using native agents and durable file delivery.
version: 0.3.0
license: MIT
metadata:
  hosts: [codex, pi, hermes-agent]
  hermes:
    tags: [idea-spark, multi-agent, research-review, research-proposal]
---

# Idea-Spark Usage

Idea-Spark provides a shared SQLite ledger and complete-file delivery. The host owns models, tools and native agent lifetimes. The parent interprets research outputs and decides the next action.

Default delivery uses **skill + CLI**. Resolve the absolute prefix from the [host contract](../../../../HOSTS.md): `python3 <plugin-root>/delphi/cli.py --state-dir <project>/.kvasir/delphi idea-spark`. Below, `idea-spark` abbreviates that prefix. Hermes also supplies its registered component CLI and explicitly enabled tool-mode.

## Role routing — choose exactly one lane first

- **[PARENT-ONLY] Parent/main agent:** read [parent-controller](references/parent-controller.md), select the mode, then load only its workflow.
- **[SUBAGENT-ONLY] Subagent/child agent:** follow [subagent-contract](references/subagent-contract.md) and the one role supplied in your assignment. The parent supplies complete task instructions and input/output paths.
- **[PARENT-ONLY] Human handoff:** load [handoff-report](references/handoff-report.md) when preparing a researcher-facing deliverable.
- **Mechanics lookup:** load [cli-dashboard](references/cli-dashboard.md) only for exact operations, dashboard or configuration details.

## [PARENT-ONLY] Select the room workflow

| Mode | Input and purpose | Read |
| --- | --- | --- |
| `open_discussion` | Review an existing idea through independent review, rebuttal, re-review and a recorded gate | [Open discussion](references/modes/open-discussion.md) |
| `deep_exploration` | Find a methodological gap, develop one sourced mechanism candidate, review/revise it and write a proposal | [Deep exploration](references/modes/deep-exploration.md) |

Use an explicit user choice. With no choice, create an open_discussion room; old rooms without mode metadata also resolve to this mode. `idea_spark_room_create` accepts `workflow_mode` and stores it in room metadata. Read an existing room's mode from `idea_spark_room_status`. To change modes after starting, create another room and pass relevant files with origin room/artifact references.

## [PARENT-ONLY] Resume from the checkpoint

Do not follow this section from a subagent prompt unless explicitly assigned to orchestrate the room.

Read room status, `workflow_state`, pending receipts and the input files for `next_action`. Save phase, active candidate and next action through `workflow checkpoint` before launching more work. Temporary notes stay in the project's `.work`; room metadata is the shared checkpoint used by the dashboard and resumed parent.

Refresh the relevant role or mode instruction only when needed. Open discussion follows its r1–r4 contract. Deep exploration follows its current research decision and budget; it can finish as completed or stopped without a terminal gate.

## Hard boundary: [PARENT-ONLY] vs [SUBAGENT-ONLY]

- **[PARENT-ONLY]** Create rooms, allocate deliveries, launch/wait/cancel native workers, collect files, interpret findings, update the checkpoint and finish the room.
- **[SUBAGENT-ONLY]** Read assigned inputs, research one task, keep scratch notes, write the full assigned file and return its absolute path. If writing fails, return the full body.
- **[SUBAGENT-ONLY]** The parent manages ledger writes, links, needs and gates. Readers and reviewers do not change the active candidate or close the room.
- A completed worker or registered file establishes delivery, not scientific validity. Material revisions and independent reviewers receive new files and identities; collecting the same receipt again does not repeat research.
