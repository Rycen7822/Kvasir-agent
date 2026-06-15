# Standalone Handoff Report Reference

Use this reference after a terminal gate when the result will be shared with a researcher or stakeholder who cannot inspect the Idea-Spark room.

## Standalone handoff report contract

The parent writes this report only after the terminal gate. It is the human-readable deliverable, not a dump of the room ledger.

## Ledger export vs handoff report

`idea_spark_room_export` produces a deterministic ledger export for auditability. It may contain room IDs, artifact IDs, need IDs, gate IDs, local paths, raw transcript order, or operational details. That export is not automatically suitable as a human handoff report.

A standalone handoff report is a separate Markdown document written from the ledger and gate summary. It must be understandable as a single file.

## Required contents

A researcher-ready handoff report should include:

1. Title, generation date, and final gate decision.
2. Executive summary that states the decision and the core reason.
3. One-paragraph explanation of the idea being reviewed.
4. Brief review process summary, including r1/r2/r3/r4 purpose without internal transcript noise.
5. Final scorecard or decision table.
6. Claim triage: delete/concede, downgrade, and defensible narrow claim.
7. Prior-art pressure by threat family.
8. Method assessment: what is defensible and what is risky.
9. Experiment and baseline requirements.
10. Limitations and positioning changes required.
11. Open blockers stated in human terms, not ledger IDs.
12. Concrete next actions.
13. Evidence-corpus list with readable paper/project names when available.

## Forbidden content by default

Do not include local machine paths, temp directories, dashboard URLs, room URLs, artifact IDs, need IDs, gate IDs, raw SQLite paths, or instructions like “see the ledger export” unless the user explicitly asks for an internal audit appendix.

Do not assume the recipient can access the repository, PDFs, room, dashboard, or prior chat. If a fact is needed for understanding, summarize it in the report.

## Self-containment scan

Before reporting completion, scan the handoff report for:

```text
/home/
/mnt/
http://
https://
artifact_
need_
gate_
room_id
room/
see file
see path
见文件
见路径
```

If any hit appears, decide whether it is intentionally part of a public citation or an internal reference. Patch internal references into human-readable prose before handing off.

## Suggested structure

```markdown
# <Idea name> Novelty Gate Report

Final decision: **needs_more_evidence** / **accepted** / **rejected**

## Executive summary
## Idea under review
## Review process
## Final scorecard
## Claim triage
## Prior-art pressure
## Method assessment
## Experiment and baseline requirements
## Limitations and positioning
## Open blockers
## Next actions
## Evidence corpus
```

## Completion rule

Tell the user which file is the standalone handoff report. If you also saved a raw ledger export, label it as internal/audit-only so the user does not accidentally hand it to an outside reader.
