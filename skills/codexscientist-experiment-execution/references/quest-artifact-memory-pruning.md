# Quest artifact and memory pruning

Use when a CodexScientist quest has accumulated too many local `artifacts/milestones` or `memory/knowledge` cards and the user asks for conservative cleanup.

## Scope guard

- Operate only inside the active quest root unless the user explicitly widens scope.
- Do not touch development workspaces such as `cs_dev`, caches, models, code repositories outside the quest, or external artifacts.
- Do not rerun experiments or rewrite scientific results during cleanup.
- Prefer pruning navigation/progress noise over deleting evidence. Keep source-of-truth experiment outputs, current status/report entry points, final results, and the latest handoff/verification milestones.

## Good deletion candidates

- chunk-by-chunk resume/progress memory cards once a final completion memory/result exists;
- superseded one-off packaging/handoff milestones when a newer self-contained handoff exists;
- planned-not-executed, blocked, template-only, preflight-only, or smoke-only milestones that are now represented in a later formal status/result document;
- old idea-revision memory cards when the current idea/report file and one latest boundary card remain;
- memory index entries that point to deleted cards.

## Keep by default

- `memory/knowledge/active-user-requirements.md`, but compact it to durable current constraints rather than a long task diary;
- final completion cards and final/current status summaries;
- baseline-gate decisions or waiver rationale;
- resource-resolution cards that would be expensive to rediscover;
- key experiment implementation and command-document records;
- current researcher handoff milestone and current documentation-compression milestone;
- all run/evidence directories unless the user explicitly asks for evidence pruning and the manifest says they are redundant.

## Workflow

1. Record the cleanup request in quest state with `cs_add_user_message`.
2. Inventory milestones and memory cards from disk; summarize title/status/date/path before deleting.
3. Build deletion candidates by rule, not by age alone. Use keep-rules first, then noise-rules.
4. Delete only the conservative candidates.
5. Rewrite `memory/knowledge/_index.jsonl` so it has no stale paths.
6. Compact `active-user-requirements.md` to current durable constraints and a short superseded-history note.
7. Commit the cleanup if the quest is git-backed.
8. Verify counts, key files, stale index count, and targeted git status.
9. Report deleted counts, remaining counts, keep principles, commit hash, and completion time.

## Verification checklist

- `artifacts/milestones` count decreased but the latest key milestone still exists.
- `memory/knowledge` count decreased and `memory_cards` in `cs_get_quest_state` is lower.
- `_index.jsonl` has zero stale entries.
- Key files still exist: current status/report, final handoff, active requirements, final completion memory, latest milestone.
- `git status --short artifacts/milestones memory/knowledge` is clean after commit.
