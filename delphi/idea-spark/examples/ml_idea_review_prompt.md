# ML idea review prompt

Use this prompt when a parent Hermes agent coordinates child reviewers through Idea-Spark.

Default mode is native workers plus file delivery. Use the absolute shared CLI/state prefix from `HOSTS.md`; Hermes also supports `hermes idea-spark`. The parent prepares a receipt/output path per assignment with `files prepare`, launches native workers, then uses `files collect` after native completion. Give every worker a separate `.work/delphi/<artifact_id>/` scratch directory. Present the returned `room_url` only after a dashboard health check succeeds.

## Worker delivery

1. Read relevant inputs and complete files referenced by prior artifacts. If needed, query `idea_spark_room_status`, `idea_spark_message_read` or `idea_spark_artifact_read`.
2. Keep intermediate notes in the assigned scratch directory and consolidate all substantive findings, sources, counterexamples, limitations and unresolved needs into the assigned final Markdown file.
3. Return the absolute file path and completion state. If file writing fails, return the full substantive body for parent recovery. A summary alone cannot replace the deliverable.
4. Stop after the bounded assignment. The parent owns ledger registration, relationships and gate decisions.

## Parent ledger operations

The parent can use `idea_spark_room_join` for manually registered participants; file collection registers its producer automatically. Use `idea_spark_artifact_create` for extra structured claims, `idea_spark_artifact_link` for relationships, `idea_spark_message_post` for optional narrative updates and `idea_spark_artifact_status_update` for research status. Evidence gaps use `idea_spark_need_create` / `idea_spark_need_update`.

Wait for workers with native host tools. `idea_spark_round_wait` only checks ledger arrivals and does not wait for worker execution. Pass `phase`, `phase="*"` or `phases=[...]` when using that ledger query.

After reading the Gatekeeper file, the parent records `idea_spark_gate_record` before final synthesis: no consensus without GateDecision; a message-only gate is not final. `idea_spark_room_export` supplies the audit ledger; a researcher-facing handoff is a separate detailed Markdown report after the terminal gate.

## Discussion-until-gate phase order

Use the fixed Idea-Spark workflow phases. The parent/orchestrator continues until `idea_spark_room_status` returns `has_terminal_gate=true` and then completes `final/handoff`.

1. `r0/seed` (`Seed / Framing`): parent records the starting goal, idea, and evaluation rubric.
2. `r1/review` (`Novelty Attack`): prior-art, feasibility, benchmark, and skeptical reviewers create `PriorArtEvidence`, `NoveltyObjection`, `FeasibilityObjection`, `ReviewerRisk`, `BenchmarkRequirement`, `StressTest`, or `ExperimentPlan` artifacts.
3. `r2/rebuttal` (`Author Rebuttal / Improvement Draft`): response roles create `Rebuttal`, `RevisionPlan`, `ExperimentPlan`, and `RegimeTransition` artifacts linked to r1 objections.
4. `r3/re-review` (`Re-review / Cross-examination`): reviewers re-read rebuttals, resolve or reopen OpenNeed records, and create remaining risks.
5. `r4/gate` (`Gate`): Gatekeeper proposes the decision in its file; the parent calls `idea_spark_gate_record`; message-only gate is not final.
6. `final/handoff`: parent exports the audit ledger and writes the standalone handoff report.

## Parent setup

1. Call `idea_spark_room_create` with title, topic, created_by, metadata containing expected agent IDs, `dashboard_base_url` when the dashboard is on a non-default port, and `check_dashboard=true` when the link should be presented as openable. Give the returned `room_url` to the user only after `dashboard_reachable=true` or another health check passes.
2. Seed `ResearchGoal`, `IdeaCard`, and `EvaluationRubric` artifacts.
3. Dispatch child roles with default `toolsets=["terminal", "file", "skills"]` and a per-child `payload_scratch_dir=.work/delphi/<artifact_id>/` and prepared durable output path; use `toolsets=["idea_spark", "skills"]` only for explicit tool-mode after config enablement and reset.
4. Maintain `.work/idea_spark_phase_ledger.md` in the project; after each phase, record the stage checkpoint marker, verification counts, latest skill re-read checkpoint, blockers, and next phase.
5. Monitor with room status and message reads, re-read `idea-spark:idea-spark-usage` after each phase, and continue through r2/r3/r4 while `has_terminal_gate=false`.
6. After gate records exist, export the audit ledger and write the standalone handoff report into the current working directory, not only under `/tmp`.

## Roles

- PriorArtBreaker: find closest prior work and create `PriorArtEvidence` plus `NoveltyObjection` artifacts.
- FeasibilityBreaker: create `FeasibilityObjection`, `BenchmarkRequirement`, and `StressTest` artifacts.
- SkepticalAC: create `ReviewerRisk` and `ScoreCard` artifacts.
- AuthorAdvocate: create `Rebuttal` and `RevisionPlan` artifacts.
- ExperimentPlanner: create `ExperimentPlan` artifacts.
- Gatekeeper: apply novelty, feasibility, complexity, and reviewer gates.
- SchemaSurgeon: create `RegimeTransition` artifacts when the idea changes representation.
- MetaReviewer: ensure final synthesis uses only gate-backed state.

## Barrier policy

Strict barriers require `expected_agents <= delegation.max_concurrent_children`. If that condition is not true, use timeout-only soft barriers and preserve the missing agent list in messages or open needs.
