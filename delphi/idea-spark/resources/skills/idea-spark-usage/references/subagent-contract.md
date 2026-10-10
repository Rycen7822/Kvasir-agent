# Subagent Contract Reference

Use this reference only inside a bounded native child role. Parent/orchestrator behavior belongs in `references/parent-controller.md`.

## Subagent scope

A subagent performs one assigned role in one phase. It does not own the room lifecycle. Use the host's native file and terminal tools. The parent supplies the room mode, stable agent ID, role, phase, input artifact paths, scratch directory and preallocated absolute `file_path`.

1. Read the supplied inputs, including complete files referenced by prior artifacts. Use `idea_spark_room_status`, `idea_spark_message_read` and `idea_spark_artifact_read` only when more room context is needed.
2. Keep interim notes and working material in the assigned `.work` scratch directory.
3. Consolidate all substantive results into the assigned UTF-8 Markdown file: reasoning, sources, findings, objections, counterexamples, failed attempts, limitations, unresolved needs and proposed next actions. Clearly cite input artifact IDs or file paths.
4. Finish writing and check that the complete final file is readable. Return its absolute path, completion state and a brief index through the native final reply, then stop. The file carries the full result; a short summary alone is not a delivery.
5. If the file cannot be written, return the complete substantive body in the native final reply, with the write failure. The parent can save that body to the preallocated path without rerunning the research.

The parent collects the file and registers the artifact. Default workers do not have to join, submit artifacts, post messages, update needs, verify ledger writes or record gates. A Gatekeeper proposes a decision with rationale in its file; the parent records the actual gate after reviewing it.

In deep exploration, a role that needs a long source read delivers current progress plus a Reading requests section with exact sources and focused questions. The parent dispatches Reader and supplies the resulting paths in a follow-up with a fresh output file. Clearly distinguish completed work, needs_reading and blocked progress in the final reply. Delivery of a progress file does not finish the research stage.

Do not call `skill_manage`, spawn agents, manage the room or export the final handoff unless explicitly assigned orchestration duties. Do not change a previously delivered file for a new assignment: the parent allocates a fresh path and delivery ID for each revision.

## Native tools

Codex/Pi workers use their actual native terminal/file tools and the absolute CLI prefix supplied by the parent. Hermes CLI-first workers use `toolsets=["terminal", "file", "skills"]`. Add outside research capabilities only when the role needs them. Optional Hermes explicit tool-mode remains available after configuration and a session reset; it does not change the default file delivery contract.

## Artifact expectations by common role

The parent chooses a primary artifact type before launch; one complete report can contain several kinds of findings. The parent may subsequently register additional typed claims or relations when useful.

- `PriorArtBreaker`: `PriorArtEvidence` or `NoveltyObjection`.
- `FeasibilityBreaker`: `FeasibilityObjection`, `ReviewerRisk` or `StressTest`.
- `ExperimentPlanner`: `ExperimentPlan` or `BenchmarkRequirement`.
- `AuthorAdvocate`: `Rebuttal` or `RevisionPlan`.
- `SchemaSurgeon`: `RevisionPlan` or `RegimeTransition`.
- `BaselineRepair`: `BenchmarkRequirement` or `ReviewerRisk`.
- `MetaReviewer` / `SkepticalAC`: `MetaReview` or `ScoreCard`.
- `Gatekeeper`: `MetaReview` containing the proposed final decision and scores; the parent records `idea_spark_gate_record`.
- Deep mode: `GapFinder` uses `GapAnalysis`, `Innovator` uses `IdeaCard`, `Reviewer` uses `MetaReview`, `Reader` uses `PriorArtEvidence`, and `ProposalWriter` uses `ResearchProposal`. Follow only the assigned role reference under `roles/`.

## Child prompt checklist

Include room ID, stable agent ID, role, phase, primary artifact type, exact input artifact IDs and file paths, permitted research tools, `.work` scratch directory, preallocated absolute output path, complete-file delivery and full-reply fallback. The parent retains the receipt; the worker only needs the output path.
