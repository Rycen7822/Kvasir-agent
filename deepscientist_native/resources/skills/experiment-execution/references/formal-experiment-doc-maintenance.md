# Conservative formal-experiment documentation maintenance

Use this note when a DeepScientist quest's experiment docs have become long or fragmented and the user asks for conservative cleanup/maintenance while experiments are still active.

## Pattern

1. Stay inside the quest scope. Reconfirm the active quest root and any explicit no-touch paths before editing. For Quest001-style work, do not touch unrelated dev checkouts such as `/home/xu/project/ds_dev/` unless the user explicitly asks.
2. Read current source-of-truth docs before editing: `AGENTS.md`, `status.md`, `SUMMARY.md`, `experiments/CURRENT_STATUS.md`, `experiments/EXPERIMENT_EXECUTION_PLAN.md`, and the active formal command document (for example `experiments/正式实验命令.md`).
3. Prefer navigation over deletion:
   - add/update a concise current-status entry;
   - add pointers from long command/plan docs to the short status entry;
   - preserve historical run sections and source-of-truth evidence;
   - move or label stale prose only when clearly superseded, and avoid deleting experimental basis.
4. When a new run changes the methodological boundary, update both status and command/plan docs with the exact caveat. Do not let a new artifact path imply that the whole stage is complete.
5. Verify from disk that all paths referenced in the edited docs exist, and search for stale phrases that would mislead the next agent.
6. Record the documentation maintenance in a milestone/summary if it affects future execution, but keep the prose compact.
7. During long iterative experiment execution, separate two documentation layers:
   - the short status entry carries the latest exact run id, cursor/token counters, and next safe command boundary;
   - long command/plan docs receive only compact deltas or a small historical bullet so they remain traceable without becoming the active handoff.
   If the user asks to avoid overlong/chaotic docs, do not delete evidence; roll forward the current-status summary and keep older run details in their run directories and durable artifacts.

## Conservative wording rules

- Distinguish `partial`, `smoke`, `preflight`, `provenance`, `capacity`, `planned`, and `formal` outputs.
- Never rebrand a partial/provenance run as a final paper-scale result.
- For 100M-token protocols, require tokenizer-counted per-job budget completion plus finite eval/checkpoint artifacts before writing or claiming formal candidate-level `Y_recover`.
- Gate transitions remain explicit: if G2 is unsatisfied, say that the quest remains in the current E-step and do not advance to later E-steps just because documentation was cleaned.

## Corpus-source documentation caveat

If a manifest-backed corpus run still consumes bounded local sample texts with repetition, document it as `manifest-backed bounded corpus consumption`, not as complete streamed-shard training. A `phase2_streaming_corpus_manifest.json` can prove provenance/capacity and may drive audited sample selection, but it is not equivalent to full streamed training-source consumption unless the runner actually consumes the materialized/streamed shards or an explicit equivalence verification exists.

Recommended language:

- Valid: "manifest-backed bounded corpus consumption validated; still not formal Y_recover/G2."
- Invalid: "paper-scale streamed corpus training completed" when only local samples or a small token chunk were consumed.

## Completion report checklist

When the user asks whether the formal experiment plan is complete, answer explicitly:

- which E-step remains active;
- which runs/artifacts were updated;
- whether formal `Y_recover` exists;
- whether G2 is satisfied;
- whether later E-steps were entered;
- whether the plan's GAAS Loop Layer Selection contents are fully complete.

If incomplete, state the next methodological blocker instead of offering an optimistic completion narrative.