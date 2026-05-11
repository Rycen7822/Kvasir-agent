from __future__ import annotations

from typing import Any


def _normalize_anchor(value: object | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "baseline"
    if normalized.startswith("analysis"):
        return "analysis-campaign"
    if normalized.startswith("write"):
        return "write"
    if normalized.startswith("final"):
        return "finalize"
    if normalized.startswith("idea"):
        return "idea"
    if normalized.startswith("exper"):
        return "experiment"
    if normalized.startswith("scout") or normalized.startswith("literature"):
        return "scout"
    if normalized.startswith("decision"):
        return "decision"
    if normalized.startswith("baseline"):
        return "baseline"
    return normalized


def _artifact_call(name: str, purpose: str) -> dict[str, str]:
    return {
        "name": name,
        "purpose": purpose,
    }


def _route(action: str, label: str, when: str, tradeoff: str) -> dict[str, str]:
    return {
        "action": action,
        "label": label,
        "when": when,
        "tradeoff": tradeoff,
    }


def _need_research_paper_from_record(record: dict[str, Any]) -> bool:
    delivery_policy = record.get("delivery_policy") if isinstance(record.get("delivery_policy"), dict) else {}
    value = delivery_policy.get("need_research_paper")
    if isinstance(value, bool):
        return value
    startup_contract = record.get("startup_contract") if isinstance(record.get("startup_contract"), dict) else {}
    fallback = startup_contract.get("need_research_paper")
    if isinstance(fallback, bool):
        return fallback
    return True


def _guidance(
    *,
    current_anchor: str,
    recommended_skill: str,
    recommended_action: str,
    summary: str,
    why_now: str,
    complete_when: list[str],
    alternative_routes: list[dict[str, str]] | None = None,
    suggested_artifact_calls: list[dict[str, str]] | None = None,
    requires_user_decision: bool = False,
    pending_interaction_id: str | None = None,
    source_artifact_kind: str | None = None,
    source_artifact_id: str | None = None,
    related_paths: list[str] | None = None,
    stage_status: str | None = None,
) -> dict[str, Any]:
    return {
        "current_anchor": current_anchor,
        "recommended_skill": recommended_skill,
        "recommended_action": recommended_action,
        "summary": summary,
        "why_now": why_now,
        "complete_when": complete_when,
        "alternative_routes": alternative_routes or [],
        "suggested_artifact_calls": suggested_artifact_calls or [],
        "requires_user_decision": requires_user_decision,
        "pending_interaction_id": pending_interaction_id,
        "source_artifact_kind": source_artifact_kind,
        "source_artifact_id": source_artifact_id,
        "related_paths": related_paths or [],
        "stage_status": stage_status or "ready",
    }


def guidance_summary(guidance: dict[str, Any] | None) -> str:
    if not guidance:
        return "Continue from the latest durable quest state."
    summary = str(guidance.get("summary") or "").strip()
    if summary:
        return summary
    skill = str(guidance.get("recommended_skill") or "").strip()
    action = str(guidance.get("recommended_action") or "").strip()
    if skill and action:
        return f"Next: use `{skill}` and record `{action}` durably."
    if skill:
        return f"Next: continue with `{skill}`."
    return "Continue from the latest durable quest state."


def build_guidance_for_record(record: dict[str, Any]) -> dict[str, Any]:
    kind = str(record.get("kind") or "").strip().lower()
    anchor = _normalize_anchor(record.get("run_kind") or record.get("stage") or kind)
    artifact_id = str(record.get("artifact_id") or record.get("id") or "").strip() or None
    related_paths = list((record.get("paths") or {}).values()) if isinstance(record.get("paths"), dict) else []

    if kind == "baseline":
        flow_type = str(record.get("flow_type") or "").strip().lower()
        protocol_step = str(record.get("protocol_step") or "").strip().lower()
        if flow_type == "baseline_gate" and protocol_step == "confirm":
            next_skill = "idea" if _need_research_paper_from_record(record) else "optimize"
            return _guidance(
                current_anchor="baseline",
                recommended_skill=next_skill,
                recommended_action="continue",
                summary="Baseline gate confirmed. Move into the next algorithmic route-selection stage relative to the accepted baseline.",
                why_now="The accepted baseline is now explicitly available as the downstream comparison anchor, so the next leverage point is to choose and promote the strongest next direction.",
                complete_when=[
                    "At least one candidate idea is recorded durably.",
                    "A decision artifact selects, rejects, or branches the current direction.",
                ],
                alternative_routes=[
                    _route("publish_baseline", "Publish baseline", "The confirmed baseline should also be reused by future quests.", "Adds packaging work now, but improves future reuse."),
                    _route("continue", "Stay on baseline verification", "Important comparability questions are still open even after confirmation.", "Keeps caution high, but delays ideation."),
                ],
                suggested_artifact_calls=[
                    _artifact_call(
                        "artifact.submit_idea(mode='create', lineage_intent='continue_line'|'branch_alternative', ...)",
                        "Create the first accepted idea branch as a durable research node.",
                    ),
                    _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Select the next route with explicit reasons."),
                ],
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
            )
        return _guidance(
            current_anchor="baseline",
            recommended_skill="baseline",
            recommended_action="continue",
            summary="Baseline state changed, but the baseline gate may still be closed.",
            why_now="A baseline record alone does not guarantee downstream comparability. The accepted baseline must still be explicitly confirmed or explicitly waived before ideation and experiments.",
            complete_when=[
                "The accepted baseline root, metric contract, and variant are explicit.",
                "The quest calls `artifact.confirm_baseline(...)` or `artifact.waive_baseline(...)` durably.",
            ],
            alternative_routes=[
                _route("publish_baseline", "Publish baseline", "The baseline should be reused by future quests.", "Adds reusable value now, but does not by itself open the stage gate."),
                _route("attach_baseline", "Attach another baseline", "The current reference still looks incomplete or mismatched.", "Improves comparability, but delays ideation."),
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.confirm_baseline(...)", "Open the canonical baseline stage gate after acceptance."),
                _artifact_call("artifact.waive_baseline(...)", "Record an explicit baseline waiver when skipping is justified."),
            ],
            source_artifact_kind=kind,
            source_artifact_id=artifact_id,
            related_paths=[str(path) for path in related_paths],
        )

    if kind == "idea":
        flow_type = str(record.get("flow_type") or "").strip().lower()
        protocol_step = str(record.get("protocol_step") or "").strip().lower()
        if flow_type == "idea_submission" and protocol_step == "candidate":
            return _guidance(
                current_anchor="idea",
                recommended_skill="optimize",
                recommended_action="continue",
                summary="Candidate idea recorded. Compare it against the other candidate briefs before promoting a durable branch.",
                why_now="This candidate is a lightweight optimization brief rather than a committed research line. Rank or refine the candidate pool first, then promote only the strongest directions into durable branches.",
                complete_when=[
                    "The candidate pool is narrowed to the strongest 1 to 3 directions.",
                    "Any promoted direction is resubmitted as a durable line with `submission_mode='line'`.",
                ],
                alternative_routes=[
                    _route("continue", "Refine candidate pool", "Several candidate briefs still overlap or lack a clear winner.", "Improves selection quality, but delays implementation."),
                    _route("launch_experiment", "Promote immediately", "This candidate is already clearly stronger than the alternatives.", "Moves faster, but risks under-explored alternatives."),
                ],
                suggested_artifact_calls=[
                    _artifact_call(
                        "artifact.submit_idea(mode='create', submission_mode='line', source_candidate_id=..., lineage_intent='continue_line'|'branch_alternative', ...)",
                        "Promote the chosen candidate brief into a durable optimization line.",
                    ),
                    _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Record why a candidate was promoted, deferred, or rejected."),
                ],
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
            )
        if flow_type == "idea_submission" and protocol_step in {"create", "revise"}:
            details = dict(record.get("details") or {}) if isinstance(record.get("details"), dict) else {}
            next_target = _normalize_anchor(details.get("next_target") or record.get("next_target") or "experiment")
            recommended_skill = next_target if next_target in {
                "scout",
                "baseline",
                "idea",
                "optimize",
                "experiment",
                "analysis-campaign",
                "write",
                "finalize",
                "decision",
            } else "experiment"
            return _guidance(
                current_anchor="idea",
                recommended_skill=recommended_skill,
                recommended_action="continue" if recommended_skill == "optimize" else "launch_experiment",
                summary="Idea branch is ready. Continue with the next active optimization stage on this durable research node.",
                why_now="The accepted idea already has its durable branch/worktree, so the next leverage point is the configured next stage rather than another route-selection loop.",
                complete_when=[
                    "The next configured stage starts from this branch.",
                    "The resulting evidence or decision is written durably.",
                ],
                alternative_routes=[
                    _route("continue", "Inspect the branch once", "A quick branch sanity check is still needed before running.", "Adds caution, but should stay short."),
                    _route("launch_analysis_campaign", "Analyze first", "The idea package still has unresolved setup ambiguity that needs clarification.", "Can reduce wasted runs, but is unusual before a first main result."),
                ],
                suggested_artifact_calls=[
                    _artifact_call("artifact.record_main_experiment(...)", "Record the first real main result on this branch when the next stage is experiment-oriented."),
                ],
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
            )
        return _guidance(
            current_anchor="idea",
            recommended_skill="decision",
            recommended_action="continue",
            summary="Idea captured. Make a durable decision before spending implementation effort.",
            why_now="The quest already has a candidate direction, but continuation is still non-trivial and needs an explicit evidence-backed route.",
            complete_when=[
                "A decision artifact names the chosen candidate or records rejection/reset.",
                "If accepted, the next active branch is already durable and ready for experiment execution.",
            ],
            alternative_routes=[
                _route("continue", "Continue on this branch", "The submitted idea is already the next durable branch.", "Keeps momentum high, but still requires a route decision."),
                _route("reset", "Reset ideation", "The new idea is still too weak or too vague.", "Avoids wasted implementation, but reopens exploration."),
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Turn the shortlisted idea into an explicit route choice."),
                _artifact_call("artifact.record(payload={'kind': 'decision'}, action='launch_experiment', ...)", "Route the new durable idea branch into the main experiment."),
            ],
            source_artifact_kind=kind,
            source_artifact_id=artifact_id,
            related_paths=[str(path) for path in related_paths],
        )

    if kind == "decision":
        action = str(record.get("action") or "continue").strip().lower()
        reason = str(record.get("reason") or "").strip()
        if action == "launch_experiment":
            return _guidance(
                current_anchor="decision",
                recommended_skill="experiment",
                recommended_action=action,
                summary="Decision accepted: launch the main experiment on the selected route.",
                why_now=reason or "The current evidence already justifies implementation and measurement on the chosen route.",
                complete_when=[
                    "The main run is executed and stored as a run artifact.",
                    "Key metrics versus baseline are written durably.",
                ],
                alternative_routes=[
                    _route("continue", "Use the active branch", "The accepted idea already owns an isolated branch/worktree.", "Keeps the normal path simple, but assumes the idea branch is in good shape."),
                    _route("launch_analysis_campaign", "Analyze first", "The setup still has unresolved confounders.", "Reduces implementation waste, but delays primary evidence."),
                ],
                suggested_artifact_calls=[
                    _artifact_call("artifact.record_main_experiment(...)", "Persist the main experiment outcome on the active idea branch."),
                ],
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
            )
        if action == "launch_analysis_campaign":
            return _guidance(
                current_anchor="decision",
                recommended_skill="analysis-campaign",
                recommended_action=action,
                summary="Decision accepted: launch an analysis campaign from the current main result.",
                why_now=reason or "The current result is informative enough that the best next step is to test robustness, ablations, or failure modes.",
                complete_when=[
                    "Each analysis run is stored as a run artifact.",
                    "A campaign report synthesizes the findings.",
                    "A follow-up decision routes to write, continue, or stop.",
                ],
                alternative_routes=[
                    _route("write", "Write now", "The current evidence is already publication-ready.", "Faster drafting, but weaker robustness story."),
                    _route("branch", "Branch another idea", "The current line no longer has the highest value.", "Expands search space, but delays explanation of the current line."),
                ],
                suggested_artifact_calls=[
                    _artifact_call(
                        "artifact.create_analysis_campaign(...)",
                        "Spawn one or more structured child analysis branches/worktrees from the current result node.",
                    ),
                    _artifact_call("artifact.record(payload={'kind': 'report'}, ...)", "Summarize the campaign before the next route decision."),
                ],
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
            )
        if action == "iterate":
            return _guidance(
                current_anchor="decision",
                recommended_skill="idea",
                recommended_action=action,
                summary="Decision accepted: use the latest measured result to start the next optimization round.",
                why_now=reason or "The current result is strong enough to inform another idea-selection pass without switching into paper work.",
                complete_when=[
                    "The latest main result is summarized durably against baseline.",
                    "A new idea branch is recorded with explicit reasons grounded in the measured result.",
                ],
                alternative_routes=[
                    _route("branch", "Branch an alternative", "The current result is informative, but a sibling direction may now be stronger.", "Improves search breadth, but adds another durable branch."),
                    _route("launch_analysis_campaign", "Analyze first", "The result is promising but still ambiguous.", "Improves understanding, but delays the next optimization round."),
                ],
                suggested_artifact_calls=[
                    _artifact_call("artifact.record(payload={'kind': 'report'}, ...)", "Summarize why this result should shape the next optimization round."),
                    _artifact_call(
                        "artifact.submit_idea(mode='create', lineage_intent='continue_line'|'branch_alternative', ...)",
                        "Create the next durable idea branch from the measured result.",
                    ),
                ],
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
            )
        if action == "write":
            return _guidance(
                current_anchor="decision",
                recommended_skill="write",
                recommended_action=action,
                summary="Decision accepted: shift from experiments into evidence-backed writing.",
                why_now=reason or "The current evidence looks strong enough that the highest-value work is now drafting and package assembly.",
                complete_when=[
                    "A writing report or draft artifact exists.",
                    "Major claims are tied to baseline and run artifacts.",
                    "Any remaining evidence gap is converted into a new durable decision.",
                ],
                alternative_routes=[
                    _route("launch_analysis_campaign", "Do more analysis", "Important robustness questions remain open.", "Strengthens confidence, but delays drafting."),
                    _route("finalize", "Finalize early", "You only need a concise report rather than a full paper package.", "Faster closure, but less complete writing output."),
                ],
                suggested_artifact_calls=[
                    _artifact_call("artifact.record(payload={'kind': 'report'}, ...)", "Persist outline, draft readiness, or review summaries."),
                    _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Route back if writing reveals missing evidence."),
                ],
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
            )
        if action == "finalize":
            return _guidance(
                current_anchor="decision",
                recommended_skill="finalize",
                recommended_action=action,
                summary="Decision accepted: consolidate the quest and record the final stopping state.",
                why_now=reason or "The quest appears mature enough to close, archive, or hand off cleanly.",
                complete_when=[
                    "A final report is written.",
                    "A final decision records stop/archive/continue-later with reasons.",
                    "The Git graph is refreshed for handoff.",
                ],
                alternative_routes=[
                    _route("write", "Refine writing first", "The paper bundle still needs drafting or proofing.", "Improves packaging, but delays closure."),
                    _route("launch_analysis_campaign", "Run one last analysis", "A decisive robustness gap remains.", "Improves confidence, but expands scope."),
                ],
                suggested_artifact_calls=[
                    _artifact_call("artifact.record(payload={'kind': 'report'}, ...)", "Write the final quest report."),
                    _artifact_call("Hermes/plugin graph inspection()", "Refresh the durable graph export."),
                ],
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
            )
        if action == "request_user_decision":
            return _guidance(
                current_anchor="decision",
                recommended_skill="decision",
                recommended_action=action,
                summary="A blocking user decision is open. Wait for the reply or resolve after the declared timeout.",
                why_now=reason or "The next route depends on user preference, scope, or ambiguity that local evidence cannot safely resolve alone.",
                complete_when=[
                    "The blocking interaction is answered or timed out.",
                    "A follow-up decision artifact records the chosen option and reason.",
                ],
                alternative_routes=[
                    _route("continue", "Self-resolve after timeout", "The user does not reply within the stated window.", "Maintains flow, but uses agent judgment."),
                ],
                suggested_artifact_calls=[
                    _artifact_call("artifact.record(payload={'kind': 'decision_request'}, ...)", "Ask the user with explicit options and tradeoffs."),
                    _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Record the resolved route after the reply or timeout."),
                ],
                requires_user_decision=True,
                pending_interaction_id=str(record.get("interaction_id") or artifact_id or ""),
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
                stage_status="waiting",
            )
        if action in {"reset", "stop"}:
            return _guidance(
                current_anchor="decision",
                recommended_skill="finalize" if action == "stop" else "scout",
                recommended_action=action,
                summary="The current line should not continue unchanged.",
                why_now=reason or "The latest evidence does not justify staying on the current route.",
                complete_when=[
                    "The stopping or reset reason is preserved durably.",
                    "The next route is either archived cleanly or reopened through scouting.",
                ],
                alternative_routes=[
                    _route("branch", "Preserve as branch", "The failed line may still be valuable for later forensic analysis.", "Keeps history, but adds branch clutter."),
                    _route("reuse_baseline", "Reuse the baseline elsewhere", "The baseline remains strong even though this idea failed.", "Saves setup effort for the next line."),
                ],
                suggested_artifact_calls=[
                    _artifact_call("artifact.record(payload={'kind': 'report'}, ...)", "Summarize the failed route and learned constraints."),
                    _artifact_call("Hermes/plugin graph inspection()", "Refresh the branch history before stopping or resetting."),
                ],
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
            )
        if action in {"reuse_baseline", "attach_baseline", "publish_baseline"}:
            return _guidance(
                current_anchor="decision",
                recommended_skill="baseline",
                recommended_action=action,
                summary="The baseline layer is the current bottleneck. Resolve it before continuing downstream work.",
                why_now=reason or "The quest needs a cleaner baseline foundation or a reusable baseline handoff before deeper work continues.",
                complete_when=[
                    "The target baseline is attached, published, or confirmed reusable.",
                    "The canonical gate is opened through `artifact.confirm_baseline(...)` or `artifact.waive_baseline(...)`.",
                    "The next idea or experiment route is recorded with that baseline in mind.",
                ],
                alternative_routes=[
                    _route("continue", "Continue on current baseline", "The mismatch turns out to be minor.", "Saves time, but may weaken comparability."),
                ],
                suggested_artifact_calls=[
                    _artifact_call("artifact.attach_baseline(...)", "Attach the accepted global baseline package."),
                    _artifact_call("a Hermes-controlled baseline publish/admin action(...)", "Publish a quest-local baseline for reuse."),
                    _artifact_call("artifact.confirm_baseline(...)", "Open the downstream gate after the accepted baseline is clear."),
                ],
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
            )
        return _guidance(
            current_anchor="decision",
            recommended_skill="decision",
            recommended_action=action or "continue",
            summary="A decision was recorded. Follow the chosen route and keep the next outcome durable.",
            why_now=reason or "The route is already chosen, so the next priority is executing it cleanly and audibly.",
            complete_when=[
                "The next stage starts and writes its first durable output.",
                "Any new ambiguity is converted into another explicit decision.",
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.record(...)", "Persist the first durable output of the chosen route."),
            ],
            source_artifact_kind=kind,
            source_artifact_id=artifact_id,
            related_paths=[str(path) for path in related_paths],
        )

    if kind == "run":
        run_kind = _normalize_anchor(record.get("run_kind") or record.get("stage"))
        if run_kind == "analysis-campaign":
            return _guidance(
                current_anchor="analysis-campaign",
                recommended_skill="decision",
                recommended_action="continue",
                summary="Analysis output is durable. Decide whether the campaign is complete enough to write, continue, or stop.",
                why_now="Analysis runs are only valuable once they are synthesized into a route change or closure decision.",
                complete_when=[
                    "A campaign report summarizes the analysis evidence.",
                    "A decision artifact records continue, write, finalize, or stop.",
                ],
                alternative_routes=[
                    _route("launch_analysis_campaign", "Continue campaign", "Important ablations or failure checks are still missing.", "Improves robustness, but adds more runs."),
                    _route("write", "Move to writing", "The current analysis already closes the main evidence gap.", "Accelerates drafting, but limits extra robustness coverage."),
                ],
                suggested_artifact_calls=[
                    _artifact_call("artifact.record(payload={'kind': 'report'}, ...)", "Write the campaign synthesis."),
                    _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Record the post-campaign route."),
                ],
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
            )
        if not _need_research_paper_from_record(record):
            return _guidance(
                current_anchor="experiment",
                recommended_skill="decision",
                recommended_action="continue",
                summary="Main run recorded. Paper mode is disabled, so the next route should stay focused on optimization rather than writing by default.",
                why_now="The measured main result should now decide whether to continue the line with a new child branch, branch an alternative, or stop. Paper packaging is not the default goal in this quest mode.",
                complete_when=[
                    "A report or decision explains the result versus baseline.",
                    "The next route is chosen: continue_line, branch_alternative, analysis, continue, or stop.",
                ],
                alternative_routes=[
                    _route("iterate", "Iterate next idea", "The result is promising and should drive the next optimization round.", "Maintains research momentum, but delays any narrative packaging."),
                    _route("branch", "Branch an alternative", "The current route is informative, but a sibling route may now be stronger.", "Expands search space, but adds another branch."),
                ],
                suggested_artifact_calls=[
                    _artifact_call("artifact.record(payload={'kind': 'report'}, ...)", "Summarize the main run and explain how it changes the optimization strategy."),
                    _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Choose the next optimization route based on the result."),
                ],
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
            )
        return _guidance(
            current_anchor="experiment",
            recommended_skill="decision",
            recommended_action="continue",
            summary="Main run recorded. Interpret it against baseline before spending more compute.",
            why_now="A run result only changes the quest once its metrics, caveats, and branch value are turned into a durable decision.",
            complete_when=[
                "A report or decision explains the result versus baseline.",
                "The next route is chosen: analysis, write, branch, or stop.",
            ],
            alternative_routes=[
                _route("launch_analysis_campaign", "Launch analysis", "The result is promising but still under-explained.", "Strengthens understanding, but adds additional runs."),
                _route("write", "Move to writing", "The result is already strong and well-explained enough.", "Faster paper progress, but less stress-testing."),
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.record(payload={'kind': 'report'}, ...)", "Summarize the main run and metric deltas."),
                _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Choose the next route based on the result."),
                _artifact_call(
                    "artifact.create_analysis_campaign(...)",
                    "When extra experiments are needed, create them as one-slice or multi-slice child branches from the current result node.",
                ),
            ],
            source_artifact_kind=kind,
            source_artifact_id=artifact_id,
            related_paths=[str(path) for path in related_paths],
        )

    if kind == "report":
        stage = _normalize_anchor(record.get("stage") or record.get("source_stage"))
        if stage in {"write", "finalize"}:
            return _guidance(
                current_anchor=stage,
                recommended_skill="finalize" if stage == "write" else "finalize",
                recommended_action="finalize",
                summary="Report recorded. Consolidate the quest or route back through a decision if evidence is still incomplete.",
                why_now="Reports should either close the current stage or explicitly reopen the missing evidence gap.",
                complete_when=[
                    "The final route is clear: finalize, continue, or reopen another stage.",
                    "Any closure claim is tied to the recorded report paths.",
                ],
                alternative_routes=[
                    _route("decision", "Reopen via decision", "The report reveals an unresolved evidence gap.", "Keeps the quest honest, but may reopen work."),
                ],
                suggested_artifact_calls=[
                    _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Route the quest honestly after reading the report."),
                ],
                source_artifact_kind=kind,
                source_artifact_id=artifact_id,
                related_paths=[str(path) for path in related_paths],
            )
        return _guidance(
            current_anchor=stage or "report",
            recommended_skill="decision",
            recommended_action="continue",
            summary="Report saved. Turn it into the next explicit route instead of leaving it as passive context.",
            why_now="A report is most useful when it directly drives the next durable decision.",
            complete_when=[
                "The report informs a route choice or stage transition.",
                "The next active anchor is clear and durable.",
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Convert the report into a route decision."),
            ],
            source_artifact_kind=kind,
            source_artifact_id=artifact_id,
            related_paths=[str(path) for path in related_paths],
        )

    if kind == "milestone":
        return _guidance(
            current_anchor=anchor,
            recommended_skill=anchor if anchor in {"scout", "baseline", "idea", "experiment", "analysis-campaign", "write", "finalize"} else "decision",
            recommended_action="continue",
            summary="Milestone recorded. Continue from the current anchor and keep the next checkpoint durable.",
            why_now="Milestones should mark meaningful progress, not end the route prematurely.",
            complete_when=[
                "The next substantive output is written durably.",
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.record(payload={'kind': 'progress'}, ...)", "Send the next checkpoint update across active surfaces."),
            ],
            source_artifact_kind=kind,
            source_artifact_id=artifact_id,
            related_paths=[str(path) for path in related_paths],
        )

    if kind == "approval":
        return _guidance(
            current_anchor="decision",
            recommended_skill="decision",
            recommended_action="continue",
            summary="Approval captured. Continue the approved route and keep the next result durable.",
            why_now="The user gate is cleared, so the quest should resume concrete work instead of asking again.",
            complete_when=[
                "The approved step starts and writes its next durable output.",
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.record(...)", "Persist the first output after approval."),
            ],
            source_artifact_kind=kind,
            source_artifact_id=artifact_id,
            related_paths=[str(path) for path in related_paths],
        )

    if kind == "graph":
        return _guidance(
            current_anchor="decision",
            recommended_skill="decision",
            recommended_action="continue",
            summary="Graph export refreshed. Use it to explain the current branch story and choose the next route.",
            why_now="The graph is a visibility aid; it should support a real route choice or handoff rather than stand alone.",
            complete_when=[
                "The graph is referenced in a progress update, report, or decision.",
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.record(payload={'kind': 'milestone'}, ...)", "Share the refreshed graph with the active surface."),
            ],
            source_artifact_kind=kind,
            source_artifact_id=artifact_id,
            related_paths=[str(path) for path in related_paths],
        )

    return _guidance(
        current_anchor=anchor,
        recommended_skill=anchor if anchor in {"scout", "baseline", "idea", "experiment", "analysis-campaign", "write", "finalize"} else "decision",
        recommended_action="continue",
        summary="Artifact recorded. Continue from the latest durable quest state.",
        why_now="The new durable state should immediately inform the next small, auditable step.",
        complete_when=["The next substantive result is written durably."],
        source_artifact_kind=kind or None,
        source_artifact_id=artifact_id,
        related_paths=[str(path) for path in related_paths],
    )


def build_guidance_for_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    pending_decisions = [str(item).strip() for item in snapshot.get("pending_decisions") or [] if str(item).strip()]
    waiting_interaction_id = str(snapshot.get("waiting_interaction_id") or "").strip() or None
    if pending_decisions:
        return _guidance(
            current_anchor="decision",
            recommended_skill="decision",
            recommended_action="request_user_decision",
            summary="A blocking decision is still open. Resolve it before continuing the quest route.",
            why_now="The runtime already marked at least one waiting interaction, so downstream work would be speculative until the choice is resolved.",
            complete_when=[
                "The waiting decision receives a reply or times out.",
                "A follow-up decision artifact records the chosen option and reason.",
            ],
            alternative_routes=[
                _route("continue", "Self-resolve after timeout", "The user does not reply within the stated window.", "Maintains flow, but uses agent judgment instead of explicit user preference."),
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.record(payload={'kind': 'decision_request'}, ...)", "Ask or remind the user with concrete options."),
                _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Persist the resolved route after reply or timeout."),
            ],
            requires_user_decision=True,
            pending_interaction_id=waiting_interaction_id or pending_decisions[0],
            stage_status="waiting",
        )

    recent_artifacts = list(snapshot.get("recent_artifacts") or [])
    if recent_artifacts:
        latest = sorted(
            recent_artifacts,
            key=lambda item: str(
                ((item.get("payload") or {}).get("updated_at"))
                or ((item.get("payload") or {}).get("created_at"))
                or ""
            ),
        )[-1]
        payload = dict(latest.get("payload") or {})
        payload.setdefault("kind", latest.get("kind"))
        return build_guidance_for_record(payload)

    anchor = _normalize_anchor(snapshot.get("active_anchor"))
    baseline_gate = str(snapshot.get("baseline_gate") or "pending").strip().lower() or "pending"
    if baseline_gate == "pending":
        return _guidance(
            current_anchor="baseline",
            recommended_skill="baseline",
            recommended_action="continue",
            summary="Baseline gate is still pending. Prepare or verify the baseline, then confirm or waive it before ideation.",
            why_now="The quest cannot safely proceed into idea, experiment, or analysis until the accepted baseline is explicitly confirmed or explicitly waived.",
            complete_when=[
                "The accepted baseline root, variant, and metric contract are explicit.",
                "`artifact.confirm_baseline(...)` or `artifact.waive_baseline(...)` is recorded durably.",
            ],
            alternative_routes=[
                _route("attach_baseline", "Attach reusable baseline", "A strong baseline already exists in the registry.", "Fastest route, but still requires explicit confirmation."),
                _route("publish_baseline", "Publish after reproduction", "You are reconstructing a reusable local baseline.", "Improves future reuse, but still does not replace confirmation."),
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.attach_baseline(...)", "Attach an existing baseline package."),
                _artifact_call("artifact.confirm_baseline(...)", "Open the canonical baseline gate."),
                _artifact_call("artifact.waive_baseline(...)", "Record an explicit waiver when skipping is justified."),
            ],
        )
    if baseline_gate == "waived" and anchor == "baseline":
        anchor = "idea"
    if anchor == "baseline":
        return _guidance(
            current_anchor="baseline",
            recommended_skill="baseline",
            recommended_action="continue",
            summary="Quest is in baseline stage. Keep the baseline contract explicit until the gate is confirmed or waived.",
            why_now="The baseline stage is only complete when the accepted baseline is explicitly confirmed or explicitly waived for downstream work.",
            complete_when=[
                "A baseline artifact exists.",
                "The evaluation contract and baseline identity are explicit enough for idea selection.",
                "`artifact.confirm_baseline(...)` or `artifact.waive_baseline(...)` is recorded.",
            ],
            alternative_routes=[
                _route("attach_baseline", "Attach reusable baseline", "A strong baseline already exists in the registry.", "Fastest route, but depends on compatibility."),
                _route("publish_baseline", "Publish after reproduction", "You are reconstructing a reusable local baseline.", "More work now, but improves future reuse."),
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.attach_baseline(...)", "Attach an existing baseline package."),
                _artifact_call("artifact.confirm_baseline(...)", "Open the canonical baseline stage gate."),
            ],
        )
    if anchor == "scout":
        return _guidance(
            current_anchor="scout",
            recommended_skill="scout",
            recommended_action="continue",
            summary="Scout the problem frame and identify the most credible baseline route.",
            why_now="The quest still needs a stable evaluation contract and baseline shortlist before deeper work.",
            complete_when=[
                "The task frame and metric contract are written durably.",
                "At least one baseline route is clearly justified.",
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.record(payload={'kind': 'report'}, ...)", "Write a concise scouting report."),
                _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Record the recommended next anchor once baseline direction is clear."),
            ],
        )
    if anchor == "idea":
        return _guidance(
            current_anchor="idea",
            recommended_skill="idea",
            recommended_action="continue",
            summary="Generate or refine candidate ideas relative to the active baseline, then select one durably.",
            why_now="The baseline exists, so the next real leverage comes from choosing the best research direction instead of exploring indefinitely.",
            complete_when=[
                "At least one candidate idea is durable.",
                "A decision selects or rejects the current idea set.",
            ],
            suggested_artifact_calls=[
                _artifact_call(
                    "artifact.submit_idea(mode='create', lineage_intent='continue_line'|'branch_alternative', ...)",
                    "Capture the accepted next idea as a new durable research node.",
                ),
                _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Choose the winner or route back."),
            ],
        )
    if anchor == "experiment":
        return _guidance(
            current_anchor="experiment",
            recommended_skill="experiment",
            recommended_action="continue",
            summary="Run the selected main experiment and keep metrics, diffs, and result summaries durable.",
            why_now="The quest already passed the route-choice stage, so the main job is now evidence production rather than more planning.",
            complete_when=[
                "A run artifact exists for the main implementation pass.",
                "Metric deltas versus baseline are durable.",
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.record_main_experiment(...)", "Persist the main experiment result on the active idea branch."),
            ],
        )
    if anchor == "analysis-campaign":
        return _guidance(
            current_anchor="analysis-campaign",
            recommended_skill="analysis-campaign",
            recommended_action="continue",
            summary="Run the necessary analysis branches and synthesize them before the next route decision.",
            why_now="The main experiment already exists, so the value now comes from explanation, robustness, and failure analysis.",
            complete_when=[
                "The main analysis runs are durable.",
                "A report synthesizes what the campaign changed.",
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.record_analysis_slice(...)", "Persist each completed analysis slice and advance the campaign."),
                _artifact_call("artifact.record(payload={'kind': 'report'}, ...)", "Write the campaign synthesis."),
            ],
        )
    if anchor == "write":
        return _guidance(
            current_anchor="write",
            recommended_skill="write",
            recommended_action="continue",
            summary="Draft from durable evidence only, and route back through decision if writing reveals a missing proof point.",
            why_now="The quest has enough evidence to draft, but the draft must stay synchronized with real artifacts and claim limits.",
            complete_when=[
                "A durable writing report or draft exists.",
                "Any missing evidence gap is converted into a new decision rather than hidden.",
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.record(payload={'kind': 'report'}, ...)", "Persist outline, draft readiness, or review state."),
                _artifact_call("artifact.record(payload={'kind': 'decision'}, ...)", "Route back if the draft uncovers missing evidence."),
            ],
        )
    if anchor == "finalize":
        return _guidance(
            current_anchor="finalize",
            recommended_skill="finalize",
            recommended_action="continue",
            summary="Consolidate the final evidence, closure recommendation, and graph export.",
            why_now="The quest is already near closure, so the highest-value step is an honest final package rather than more scattered changes.",
            complete_when=[
                "A final report exists.",
                "A final decision records stop, archive, or continue-later.",
                "The graph export is refreshed.",
            ],
            suggested_artifact_calls=[
                _artifact_call("artifact.record(payload={'kind': 'report'}, ...)", "Write the final state summary."),
                _artifact_call("Hermes/plugin graph inspection()", "Refresh the Git graph export."),
            ],
        )
    return _guidance(
        current_anchor=anchor,
        recommended_skill="decision",
        recommended_action="continue",
        summary="Continue from the latest durable state and make the next route explicit.",
        why_now="The quest should always keep the next step small, auditable, and evidence-backed.",
        complete_when=["The next durable output is written."],
        suggested_artifact_calls=[
            _artifact_call("artifact.record(...)", "Persist the next meaningful output."),
        ],
    )
