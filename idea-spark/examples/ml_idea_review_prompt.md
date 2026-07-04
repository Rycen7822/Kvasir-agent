# ML idea review prompt

Use this prompt when a parent Hermes agent coordinates child reviewers through Idea-Spark.

Default mode is CLI-first: children use `toolsets=["terminal", "file", "skills"]`, write JSON payload files under a provided `payload_scratch_dir`, and call `hermes idea-spark call <operation> --json-file <payload>`. Use direct `idea_spark` tools only after explicit tool-mode has been enabled with `$HERMES_HOME/idea-spark/config.json` and the Hermes session has been restarted/reset. After every room creation, report the returned `room_url` only after the dashboard is started and `check_dashboard=true` or another health check proves it reachable.

## Child protocol hard rule block

Every child agent must call `idea_spark_room_join` before any substantive work. In default CLI-first mode this means running `hermes idea-spark call idea_spark_room_join --json-file join.json`. After joining, the child may call `idea_spark_room_status`, `idea_spark_message_read`, `idea_spark_artifact_read`, `idea_spark_artifact_create`, `idea_spark_artifact_link`, `idea_spark_message_post`, `idea_spark_round_wait`, `idea_spark_artifact_status_update`, `idea_spark_need_create`, `idea_spark_need_update`, and `idea_spark_gate_record`.

Child rules:

1. Join first with `idea_spark_room_join` using the provided `room_id`, unique `agent_id`, and assigned role.
2. Read existing state with `idea_spark_room_status`, `idea_spark_message_read`, and `idea_spark_artifact_read`.
3. Convert each substantive scientific point into a typed artifact with `idea_spark_artifact_create`.
4. Link evidence, objections, rebuttals, and revisions with `idea_spark_artifact_link`.
5. Post concise narrative progress with `idea_spark_message_post`; include artifact IDs instead of long transcripts.
6. Wait only with bounded `idea_spark_round_wait`; pass `phase` for exact phase barriers, omit `phase` or use `phase="*"` for whole-round parent barriers, or pass `phases=[...]` when reviewers use role-specific phase labels. If timeout returns missing agents, continue with partial state and record the gap.
7. Revise, reject, supersede, or retract only through `idea_spark_artifact_status_update` or `idea_spark_gate_record`.
8. Use `idea_spark_need_create` when stronger prior-art evidence, benchmark detail, or reviewer-risk evidence is required; use `idea_spark_need_update` when the need is claimed, resolved, reopened, marked stale, or cancelled.
9. Gatekeeper and MetaReviewer must use `idea_spark_gate_record` before final synthesis. Final conclusions require gate-backed ledger evidence; no consensus without GateDecision; message-only gate is not final.
10. Parent uses `idea_spark_room_export` for the audit ledger only; the researcher-facing handoff is a separate detailed Markdown report saved in the current working directory after the terminal gate.

## Discussion-until-gate phase order

Use the fixed Idea-Spark workflow phases. The parent/orchestrator continues until `idea_spark_room_status` returns `has_terminal_gate=true` and then completes `final/handoff`.

1. `r0/seed` (`Seed / Framing`): parent records the starting goal, idea, and evaluation rubric.
2. `r1/review` (`Novelty Attack`): prior-art, feasibility, benchmark, and skeptical reviewers create `PriorArtEvidence`, `NoveltyObjection`, `FeasibilityObjection`, `ReviewerRisk`, `BenchmarkRequirement`, `StressTest`, or `ExperimentPlan` artifacts.
3. `r2/rebuttal` (`Author Rebuttal / Improvement Draft`): response roles create `Rebuttal`, `RevisionPlan`, `ExperimentPlan`, and `RegimeTransition` artifacts linked to r1 objections.
4. `r3/re-review` (`Re-review / Cross-examination`): reviewers re-read rebuttals, resolve or reopen OpenNeed records, and create remaining risks.
5. `r4/gate` (`Gate`): Gatekeeper must call `idea_spark_gate_record`; message-only gate is not final.
6. `final/handoff`: parent exports the audit ledger and writes the standalone handoff report.

## Parent setup

1. Call `idea_spark_room_create` with title, topic, created_by, metadata containing expected agent IDs, `dashboard_base_url` when the dashboard is on a non-default port, and `check_dashboard=true` when the link should be presented as openable. Give the returned `room_url` to the user only after `dashboard_reachable=true` or another health check passes.
2. Seed `ResearchGoal`, `IdeaCard`, and `EvaluationRubric` artifacts.
3. Dispatch child roles with default `toolsets=["terminal", "file", "skills"]` and a per-child `payload_scratch_dir=/tmp/idea_spark_<run_id>/<agent_id>/`; use `toolsets=["idea_spark", "skills"]` only for explicit tool-mode after config enablement and reset.
4. Maintain `idea_spark_phase_ledger.md` in the current working directory; after each phase, record the stage checkpoint marker, verification counts, latest skill re-read checkpoint, blockers, and next phase.
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
