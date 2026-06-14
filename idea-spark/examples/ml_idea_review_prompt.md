# ML idea review prompt

Use this prompt when a parent Hermes agent coordinates child reviewers through Idea-Spark.

Default mode is CLI-first: children use `toolsets=["terminal", "file", "skills"]`, write JSON payload files under a provided `payload_scratch_dir`, and call `hermes idea-spark call <operation> --json-file <payload>`. Use direct `idea_spark` tools only after explicit tool-mode has been enabled with `$HERMES_HOME/idea-spark/config.json` and the Hermes session has been restarted/reset. After every room creation, copy the returned `room_url` to the user immediately.

## Child protocol hard rule block

Every child agent must call `idea_spark_room_join` before any substantive work. In default CLI-first mode this means running `hermes idea-spark call idea_spark_room_join --json-file join.json`. After joining, the child may call `idea_spark_room_status`, `idea_spark_message_read`, `idea_spark_artifact_read`, `idea_spark_artifact_create`, `idea_spark_artifact_link`, `idea_spark_message_post`, `idea_spark_round_wait`, `idea_spark_artifact_status_update`, `idea_spark_need_create`, `idea_spark_need_update`, and `idea_spark_gate_record`.

Child rules:

1. Join first with `idea_spark_room_join` using the provided `room_id`, unique `agent_id`, and assigned role.
2. Read existing state with `idea_spark_room_status`, `idea_spark_message_read`, and `idea_spark_artifact_read`.
3. Convert each substantive scientific point into a typed artifact with `idea_spark_artifact_create`.
4. Link evidence, objections, rebuttals, and revisions with `idea_spark_artifact_link`.
5. Post concise narrative progress with `idea_spark_message_post`; include artifact IDs instead of long transcripts.
6. Wait only with bounded `idea_spark_round_wait`; include both `round_id` and `phase`, make all expected agents in the barrier post with the same `round_id/phase`, and if timeout returns missing agents, continue with partial state and record the gap.
7. Revise, reject, supersede, or retract only through `idea_spark_artifact_status_update` or `idea_spark_gate_record`.
8. Use `idea_spark_need_create` when stronger prior-art evidence, benchmark detail, or reviewer-risk evidence is required; use `idea_spark_need_update` when the need is claimed, resolved, reopened, marked stale, or cancelled.
9. Gatekeeper and MetaReviewer must use `idea_spark_gate_record` before final synthesis. Final conclusions require gate-backed ledger evidence; no consensus without GateDecision; message-only gate is not final.
10. Parent exports the final report with `idea_spark_room_export`.

## Discussion-until-gate phase order

Use `max_rounds=4`. The parent/orchestrator continues until `idea_spark_room_status` returns `has_terminal_gate=true`.

1. `Seed / Framing`: parent records the starting goal, idea, and evaluation rubric.
2. `Novelty Attack`: prior-art reviewers create `PriorArtEvidence` and `NoveltyObjection` artifacts.
3. `Weakness / Feasibility Attack`: feasibility and reviewer-risk roles create `FeasibilityObjection`, `ReviewerRisk`, `BenchmarkRequirement`, `StressTest`, and `ExperimentPlan` artifacts.
4. `Author Rebuttal / Improvement Draft`: response roles create `Rebuttal`, `RevisionPlan`, and `RegimeTransition` artifacts linked to objections.
5. `Re-review / Cross-examination`: reviewers re-read rebuttals, resolve or reopen OpenNeed records, and create remaining risks.
6. `Gate`: Gatekeeper must call `idea_spark_gate_record`; message-only gate is not final.

## Parent setup

1. Call `idea_spark_room_create` with title, topic, created_by, metadata containing expected agent IDs, and `dashboard_base_url` when the dashboard is on a non-default port. Immediately give the returned `room_url` to the user.
2. Seed `ResearchGoal`, `IdeaCard`, and `EvaluationRubric` artifacts.
3. Dispatch child roles with default `toolsets=["terminal", "file", "skills"]` and a per-child `payload_scratch_dir=/tmp/idea_spark_<run_id>/<agent_id>/`; use `toolsets=["idea_spark", "skills"]` only for explicit tool-mode after config enablement and reset.
4. Monitor with room status and message reads.
5. Export the report after gate records exist.

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
