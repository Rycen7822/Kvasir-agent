# Deep Exploration

Use only for rooms with `workflow_mode=deep_exploration`. Develop a methodological research proposal from problem_definition, challenge and practical constraints. Work depth-first on one active candidate.

The role division and research loop are informed by [IdeaScientist](https://github.com/jiarui-liu/IdeaScientist) and [arXiv 2610.04074](https://arxiv.org/abs/2610.04074). These instructions adapt the workflow to Kvasir's native-host and file-delivery contract. Upstream code/prompt material is distributed under CC BY-NC 4.0; direct reuse must preserve its license and attribution conditions.

## Parent decisions

1. **Frame:** save a ResearchGoal. Choose a central challenge axis and a finite task budget; record assumptions and resource limits.
2. **Find gaps:** assign [Gap Finder](../roles/gap-finder.md) one axis. Collect GapAnalysis; select one concrete gap. Additional axes are explored when they can change the decision.
3. **Form a candidate:** assign [Innovator](../roles/innovator.md) that gap, the next C<n> label and relevant files. Collect one IdeaCard.
4. **Review:** assign [Reviewer](../roles/reviewer.md) the full candidate and gap files. It independently searches close work and checks the mechanism transfer.
5. **Act on its recommendation:**
   - `survive`: move to [Proposal Writer](../roles/proposal-writer.md).
   - `revise`: name one weak dimension and request a new candidate file/label. Link it with `evolves_from` and review the revision.
   - `reject`: leave that candidate intact, record why it is abandoned, then choose another gap or stop.
6. **Write:** collect a complete ResearchProposal. If writing exposes a critical mapping/mechanism failure, return to Innovator; if it exposes an important prior-art omission, return to Gap Finder.
7. **Deliver:** account for outstanding native assignments by waiting or cancelling through the host, then collect usable output and record missing work. Save `status=completed` with final_artifact_id, then export/handoff. If time or viable directions run out, collect an available stage summary as MetaReview and save `status=stopped` with stop_reason. Bookkeeping can be supplemented after stopping without reopening research.

This loop permits repeat and backward moves. A candidate may reach writing with an explicit parent decision to retain uncertainty; pass the reviewer objections into the writer and accurately state review status. No score automatically dispatches or accepts a candidate.

## Reader requests

Research roles can search with available host tools. For long full-text, figures or independent source verification, the role delivers current progress plus a **Reading requests** section: exact source/path/URL and a few focused questions.

The parent dispatches [Reader](../roles/reader.md), collects PriorArtEvidence files and returns the paths to the requesting role in a follow-up assignment with a fresh output receipt. A progress file with outstanding reading requests is not a completed candidate. Readers do not launch more agents.

Independent readings may run in parallel. Reuse earlier digests, adding a new file only for new questions. Short focused source reads can use the research role's native tools; do not add a mandatory reader round trip for every citation.

## Budget, uncertainty and stopping

Record a time or assignment budget and finite revision allowance appropriate to the task. Two or three revisions can be a useful stop-loss guideline, not a fixed requirement. Concentrate effort on the single weakest dimension. Stop a direction when revisions add no substance or the mechanism is fundamentally broken.

Read enough to resolve load-bearing issues: source mechanism, closest prior method, mapping and transfer condition. Keep remaining uncertainties explicit. Do not require every claim to have a ledger edge, every cited paper to be reread, or every proposal section to contain an observed result.

Predictions and future experiments stay labeled as such. A complete proposal may have unverified hypotheses. Budget exhaustion produces a stage report, not an invented acceptance gate or a fabricated successful experiment.

## Artifacts and checkpoint

- ResearchGoal → GapAnalysis → IdeaCard → MetaReview → ResearchProposal.
- Reader uses PriorArtEvidence. Optional cites/critiques/evolves_from relations capture important provenance.
- Parent saves phase, active_gap_artifact_id, active_candidate_artifact_id, candidate_label, next_action, next_inputs, revision_count and pending_receipts as needed.
- Use round_id=C<n> for candidate-related deliveries; real identity remains the artifact/delivery ID.
- Parent-written phase is authoritative even if a reader finishes later. Native completion proves delivery only.
