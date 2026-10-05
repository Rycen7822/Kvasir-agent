# Subagent Contract Reference

Use this reference only inside a bounded native child role. Parent/orchestrator behavior belongs in `references/parent-controller.md`.

## Subagent scope

Read this reference from the installed component's skill directory with native file tools. On Hermes, if its skill_view returns the main SKILL, read this actual file instead.

A subagent performs one assigned role in one phase. It does not own the room lifecycle.

A subagent should:

1. Read the installed Idea-Spark SKILL.md and this reference.
2. Join the assigned room with its stable `agent_id` and `role`.
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
- Put transient payload JSON in the repository root; use the parent-provided scratch directory.

## Default toolsets

Codex/Pi workers use their actual native terminal/file tools and the absolute CLI prefix supplied by the parent. Do not pass Hermes toolset parameters to Codex tools.

Hermes CLI-first subagents use:

```text
toolsets=["terminal", "file", "skills"]
```

Use file tools to write JSON payloads, terminal tools to call the selected CLI prefix, and file/skill tools to read this protocol. Add external capabilities only when the role needs outside evidence.

Explicit tool-mode subagents use:

```text
toolsets=["idea_spark", "skills"]
```

Only use explicit tool-mode after the plugin config enables tools and the Hermes session has been reset.

## CLI-first child workflow

1. Write payload JSON under the assigned scratch directory.
2. Call `idea-spark call idea_spark_room_join --json-file join.json` using the parent's complete prefix.
3. Read current state with `idea_spark_room_status`, `idea_spark_message_read`, and `idea_spark_artifact_read`.
4. Create artifacts with `idea_spark_artifact_create`.
5. Link provenance with `idea_spark_artifact_link` when available and useful.
6. Post a message with `idea_spark_message_post` and include artifact IDs.
7. Create/update needs with `idea_spark_need_create` / `idea_spark_need_update` for unresolved blockers.
8. Verify the created message and artifact IDs by reading the room back.

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

A good child prompt includes: room id, stable agent id, role name, phase name, scratch directory, required first operation `idea_spark_room_join`, exact artifact types to write, whether external evidence tools are allowed, requirement to create open needs for blockers, requirement to verify writes, and a reminder not to call `skill_manage`.
