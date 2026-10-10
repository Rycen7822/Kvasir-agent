# Parent Controller Reference

Use this reference for the parent that orchestrates a room. The parent must keep the phase loop moving according to the selected mode and explicit checkpoint.

## Mode and task ownership

Create the room with `workflow_mode=open_discussion` or `deep_exploration`; default and legacy rooms use open discussion. Read the selected [open](modes/open-discussion.md) or [deep](modes/deep-exploration.md) workflow. The host owns native launches, follow-ups, waits and cancellation. The parent owns scientific decisions, room metadata and collection.

Record current phase, relevant artifact IDs, candidate label, next action, input artifact IDs and pending receipt paths with `workflow checkpoint`. Record the task's actual budget in that checkpoint when useful; numeric counters are explicit values, not automatically incremented by delivery retries.

## Prepare, wait, collect, decide

1. Prepare a fresh delivery for each assignment. Select the primary type and pass an exact phase and round_id; deep mode can use C1/C2 candidate labels as round_id.
2. Save the returned receipt path in `pending_receipts` before native launch. Give the worker its complete role instructions, exact inputs, separate `.work/delphi/<artifact_id>/` scratch directory and absolute output path.
3. Launch through the actual native interface. Record observed launch failures and use finite waits. File presence alone does not prove worker completion.
4. After native completion or cancellation, collect and inspect complete files. Recover a failed write from the full native final reply before considering another research assignment.
5. Interpret the content, save useful links/needs and update phase/next action. Only substantive new research or revision receives a new delivery.
6. Continue or finish according to the selected mode. Read the checkpoint on resumption; load additional instructions only for the next task.

`idea-spark` below abbreviates the complete absolute prefix from HOSTS.md.

```sh
idea-spark files prepare --room-id ROOM --agent-id prior-art-r1 --role PriorArtBreaker --round-id r1 --phase review --type PriorArtEvidence --title "Prior art review"
idea-spark files collect /absolute/receipt-a.json /absolute/receipt-b.json
idea-spark workflow checkpoint --room-id ROOM --json-file .work/checkpoint.json
```

Receipts and result files live beside the selected database under `deliveries/<artifact_id>/`. They are durable project state. Collection registers the producer and artifact together; a failed receipt does not discard another worker's successful result.

## Recovery and independent contributions

Retry `files collect` with the same receipt when registration fails. It preserves delivery identity and existing review status. If checkpoint writing fails after collection, read the registered artifact and retry the explicit checkpoint; do not repeat research or increment the revision count. A retry payload can be merged repeatedly without creating a new task.

A new revision gets a fresh file and artifact, optionally linked with `evolves_from`; do not overwrite delivered work. Identical prose from independent reviewers remains independent. The parent may add `idea_spark_artifact_link`, `idea_spark_message_post`, `idea_spark_need_create` or `idea_spark_need_update` when useful. Avoid splitting every sentence into a claim/edge.

When both the file and full native reply are unusable, retry a critical role once with a sharper brief if budget remains, or record the missing work and choose a bounded next action. Native wait and ledger `idea_spark_round_wait` serve different purposes: the latter observes ledger arrivals, not running processes.

## Completion

Open discussion records `idea_spark_gate_record(close_room=true)`; confirm `has_terminal_gate=true`.

Deep exploration saves `status=completed` with an already registered ResearchProposal file, or `status=stopped` with a nonempty stop_reason and any available stage report. Confirm `is_terminal=true`. Neither outcome asserts that experiments succeeded. Stop/cancel outstanding native workers through the host and record actual outcomes.

The deterministic export is not automatically suitable as a human handoff report. Use [handoff-report](handoff-report.md) when needed.
