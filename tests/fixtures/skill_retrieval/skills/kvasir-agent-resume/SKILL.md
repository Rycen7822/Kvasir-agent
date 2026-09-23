---
name: kvasir-agent-resume
description: Resume long-running Kvasir-agent tasks with checkpoint, resume brief, and delta packs.
---

# Kvasir-agent Resume

Use when: a long-running task must continue after context compaction or restart.
Do not use when: the user asks for paper venue review.
Required context: project root, latest checkpoint, event range.

## Runtime Steps

1. Call ka_status.
2. Call ka_resume_brief with a non-aggressive context budget.
3. Call ka_pack_delta when a checkpoint id or event sequence is available.

## Pitfalls

- Do not read full logs by default.
- Do not drop goal or next_action anchors.

## Verification

Run resume/checkpoint/delta tests.
