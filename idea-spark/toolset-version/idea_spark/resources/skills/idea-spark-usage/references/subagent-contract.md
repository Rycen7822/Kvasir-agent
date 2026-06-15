# Subagent Contract Reference

Use this reference only inside a bounded `delegate_task` child role. Parent/orchestrator behavior belongs in `references/parent-controller.md`.

## Subagent scope

If `skill_view(name="idea-spark:idea-spark-usage", file_path="references/subagent-contract.md")` returns the main SKILL rather than this reference, use `read_file` on `idea_spark/resources/skills/idea-spark-usage/references/subagent-contract.md` in the Idea-Spark plugin source tree.

A subagent performs one assigned role in one phase. It does not own the room lifecycle.

A subagent should:

1. Load `skill_view(name="idea-spark:idea-spark-usage")` and this reference.
2. Join the assigned room with `idea_spark_room_join` using its stable `agent_id` and `role`.
3. Read room status plus the seed and prior-phase artifacts needed for its role.
4. Write at least one concise narrative message.
5. Write at least one typed artifact when it has substantive content.
6. Link or clearly cite the artifacts it answers, critiques, or requires.
7. Create or update open needs for missing evidence that blocks its judgment.
8. Verify its own message/artifact writes by reading room state back.
9. Return a short summary to the parent and stop.

A subagent should not:

- Call `skill_manage`. Do not call `skill_manage` from child prompts.
- Decide the whole room is complete unless it is the assigned Gatekeeper and explicitly records a gate.
- Assume it will remain alive to continue the conversation later.
- Spawn other agents unless it was explicitly launched as an orchestrator role.
- Export the final report or manage phase transitions unless explicitly assigned by the parent.

## Default toolsets

Toolset-version subagents use direct Idea-Spark tools by default:

```text
toolsets=["idea_spark", "skills"]
```

Use `idea_spark` for ledger operations and `skills` to load this protocol. Add `web`, `browser`, `file`, `terminal`, or other external toolsets only when the assigned role needs outside evidence, local papers, shell checks, or file artifacts.

## Direct-tool child workflow

1. Call `idea_spark_room_join` first.
2. Read current state with `idea_spark_room_status`, `idea_spark_message_read`, and `idea_spark_artifact_read`.
3. Create artifacts with `idea_spark_artifact_create`.
4. Link provenance with `idea_spark_artifact_link` when available and useful.
5. Post a message with `idea_spark_message_post` and include artifact IDs.
6. Create/update needs with `idea_spark_need_create` / `idea_spark_need_update` for unresolved blockers.
7. Verify the created message and artifact IDs by reading the room back.

## Artifact expectations by common role

- `PriorArtBreaker`: `PriorArtEvidence`, `NoveltyObjection`, optionally `BenchmarkRequirement`.
- `FeasibilityBreaker`: `FeasibilityObjection`, `ReviewerRisk`, `StressTest`, optionally `ExperimentPlan`.
- `ExperimentPlanner`: `ExperimentPlan`, `BenchmarkRequirement`, optionally `OpenNeed`.
- `AuthorAdvocate`: `Rebuttal`, `RevisionPlan`, optionally `RegimeTransition`.
- `SchemaSurgeon`: `RevisionPlan`, `RegimeTransition`.
- `BaselineRepair`: `BenchmarkRequirement`, `ReviewerRisk`.
- `MetaReviewer` / `SkepticalAC`: `MetaReview`, `ScoreCard`, optionally `OpenNeed`.
- `Gatekeeper`: final `ScoreCard`, final `MetaReview`, and a real `idea_spark_gate_record(close_room=true)` when assigned to close the room.

## Subagent prompt checklist

A good child prompt includes: room id, stable agent id, role name, phase name, required first operation `idea_spark_room_join`, required toolsets `toolsets=["idea_spark", "skills"]`, exact artifact types to write, whether external evidence tools are allowed, requirement to create open needs for blockers, requirement to verify writes, and a reminder not to call `skill_manage`.
