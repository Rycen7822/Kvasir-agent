# Execution-Grounded Research Boundary

Execution-grounded research turns research execution into auditable project-local state. It is not a default autonomous mode and it is not a replacement for Codex-native file, shell, Git, test, build, or process capabilities.

## Default rule

The default `copilot` path records research meaning and recovery anchors. It does not automatically invent ideas, implement variants, schedule jobs, or execute experiments. Execution-grounded actions require an explicit user request or a project manifest that enables the specific action.

## Subsystems

- `ResearchEnvironment`: the trusted evaluation contract. It records immutable baseline paths, protected files, dataset hashes, allowed mutable paths, command contracts, metric parser contracts, and budget limits.
- `FeedbackIngest`: bounded ingestion for logs, metrics, artifacts, and external run summaries. It copies or references evidence into quest-local artifacts and records hashes.
- `TrajectoryStore`: complete lineage for idea, variant, patch, job, feedback, metric, failure class, cost, protected audit, and claimability.
- `EvolutionaryRoundPlan`: plan-only exploit/explore selection over trusted trajectories. It proposes next candidates and diversity controls but does not submit jobs by itself.

## Forbidden AAR patterns

- Do not treat W&B or output.log as primary metric truth. Primary metric truth must come from `ResearchEnvironment` evaluator/parser contracts or clean-room revalidation.
- Do not expose executor tools in the default MCP surface.
- Do not treat directory existence, wrapper success messages, or timeout fallbacks as successful execution.
- Do not mutate protected evaluator, dataset, or baseline files in a variant.
- Do not schedule automatic next experiments from `EvolutionaryRoundPlan` without explicit authorization, budget, and environment validation.

## MCP/profile boundary

`execution_planning` is plan-first and may expose environment summaries, feedback ingestion, trajectory lookup, and evolutionary planning after those tools exist. `executor_local` is gated local execution and remains unregistered by default unless the user or manifest explicitly authorizes executor work and the environment/budget gates pass.
