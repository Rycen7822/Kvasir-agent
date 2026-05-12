---
name: codexscientist-review
description: Review claims, evidence matrices, and paper-facing artifacts.
---

# CodexScientist Review

Use when: a claim or artifact needs read-only review.
Do not use when: resuming a checkpoint after context compaction.
Required context: claim text and evidence refs.

## Runtime Steps

1. Inspect claim evidence.
2. Produce read-only verdict.

## Risks

- Never mutate experiment outputs during review.
