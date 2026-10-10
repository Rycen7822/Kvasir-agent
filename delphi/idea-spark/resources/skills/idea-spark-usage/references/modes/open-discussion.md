# Open Discussion

Use only for rooms with `workflow_mode=open_discussion`. Review an existing idea through independent criticism, reply and re-review. The parent collects complete files and records decisions.

## Workflow

1. `r0/seed`: save ResearchGoal, IdeaCard and EvaluationRubric.
2. `r1/review`: independent PriorArtBreaker, FeasibilityBreaker, SkepticalAC or ExperimentPlanner inspect the idea. Choose roles relevant to the question; collect their full reports.
3. `r2/rebuttal`: AuthorAdvocate and any necessary repair role respond to specific objections. Deliver Rebuttal, RevisionPlan, ExperimentPlan or baseline repairs with input references.
4. `r3/re-review`: reviewers read the revised files, state resolved and unresolved issues, and deliver MetaReview or ScoreCard. Persist important outstanding needs when useful.
5. `r4/gate`: Gatekeeper delivers the proposed decision; the parent reviews and calls `idea_spark_gate_record` with `close_room=true`. Verify `has_terminal_gate=true`.
6. `final/handoff`: export the ledger and write a standalone handoff when requested.

r1, r2 and r3 are progress checkpoints. Save the verified phase and next action, then continue while the authorized review is active. A message, child summary or parent synthesis alone does not establish the final gate.

Use finite waits and the parent's file recovery policy. If the planned review budget is exhausted, record a truthful `needs_more_evidence` gate rather than looping until every need is resolved. Users can stop work; report that interruption as observed. Refresh instructions when uncertain and resume from the room checkpoint.

The parent owns the gate and its rationale. Independently delivered reviewer reports remain distinct even when they agree.
