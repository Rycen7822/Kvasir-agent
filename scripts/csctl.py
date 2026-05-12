#!/usr/bin/env python3
"""Codex-Scientist CLI compatibility entrypoint."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PLUGIN_ROOT / "scripts"
for path in (PLUGIN_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import cs_native_cli  # type: ignore  # noqa: E402
from codex_scientist.adapters.cli import normalize_envelope  # noqa: E402
from codex_scientist.services.artifacts import ArtifactIndexService  # noqa: E402
from codex_scientist.services.checkpoint import CheckpointService  # noqa: E402
from codex_scientist.services.claims import ClaimEvidenceService  # noqa: E402
from codex_scientist.services.context_pack import ContextPackService  # noqa: E402
from codex_scientist.services.costs import CostApprovalService  # noqa: E402
from codex_scientist.services.frontier import FrontierService  # noqa: E402
from codex_scientist.services.journal import JournalService  # noqa: E402
from codex_scientist.services.manifest import ManifestService  # noqa: E402
from codex_scientist.services.migrations import MigrationService  # noqa: E402
from codex_scientist.services.project_state import ProjectLayout  # noqa: E402
from codex_scientist.services.queue import QueueService  # noqa: E402
from codex_scientist.services.research_wiki import ResearchWikiService  # noqa: E402
from codex_scientist.services.review import ReviewService  # noqa: E402
from codex_scientist.services.resume import ResumeService  # noqa: E402
from codex_scientist.services.runner import RunnerService  # noqa: E402
from codex_scientist.services.soak import SoakService  # noqa: E402
from codex_scientist.services.trial import TrialService  # noqa: E402


def _set_project_root(project_root: str | None) -> Path:
    root = Path(project_root).expanduser().resolve() if project_root else Path.cwd().resolve()
    os.environ["CODEXSCIENTIST_PROJECT_ROOT"] = str(root)
    os.chdir(root)
    return root


def _layout(args: argparse.Namespace) -> ProjectLayout:
    return ProjectLayout.from_project_root(_set_project_root(args.project_root))


def _manifest_payload(args: argparse.Namespace) -> dict:
    service = ManifestService(_layout(args))
    if args.manifest_command == "init":
        return service.init(name=args.name, goal=args.goal, overwrite=bool(args.overwrite))
    if args.manifest_command == "validate":
        return service.validate()
    if args.manifest_command == "show":
        manifest = service.read()
        return {"ok": bool(manifest), "path": str(service.path), "manifest": manifest}
    return {"ok": False, "error": "Unknown manifest command", "error_type": "usage", "recoverable": True}


def _baseline_payload(args: argparse.Namespace) -> dict:
    service = ManifestService(_layout(args))
    if args.baseline_command == "confirm":
        return service.record_baseline(baseline_id=args.id, status="confirmed", metric_contract=args.metric_contract)
    if args.baseline_command == "waive":
        return service.record_baseline(baseline_id=args.id, status="waived", waiver_reason=args.reason)
    if args.baseline_command == "show":
        validation = service.validate()
        manifest = validation.get("manifest") or {}
        baselines = manifest.get("baselines") if isinstance(manifest.get("baselines"), dict) else {}
        return {"ok": validation.get("ok", False), "path": str(service.path), "baseline_ready": validation.get("baseline_ready", False), "baselines": baselines.get("entries", [])}
    return {"ok": False, "error": "Unknown baseline command", "error_type": "usage", "recoverable": True}


def _trial_payload(args: argparse.Namespace) -> dict:
    service = TrialService(_layout(args))
    if args.trial_command == "propose":
        trial = service.propose(quest_id=args.quest_id, idea_id=args.idea_id, hypothesis=args.hypothesis, mechanism=args.mechanism)
        return {"ok": True, "trial": trial}
    if args.trial_command == "plan":
        return service.plan(args.trial_id, metric_contract_id=args.metric_contract, novelty_decision=args.novelty)
    if args.trial_command == "ready":
        return service.ready(args.trial_id)
    if args.trial_command == "evaluate":
        return service.evaluate(args.trial_id, metric_values=_parse_metric_pairs(args.metric or []), artifacts=args.artifact or [])
    if args.trial_command == "decide":
        return service.decide(args.trial_id, decision=args.decision, reviewer_verdict=args.reviewer_verdict)
    if args.trial_command == "show":
        return {"ok": True, "trial": service.get(args.trial_id)}
    return {"ok": False, "error": "Unknown trial command", "error_type": "usage", "recoverable": True}


def _runner_payload(args: argparse.Namespace) -> dict:
    service = RunnerService(_layout(args))
    if args.runner_command == "start":
        return service.start(command=args.command_text, job_id=args.job_id, dry_run=bool(args.dry_run))
    if args.runner_command == "collect":
        return service.collect(args.run_id, exit_code=args.exit_code)
    if args.runner_command == "tail":
        return service.tail(args.run_id, limit=args.limit)
    if args.runner_command == "log-digest":
        return service.log_digest(args.run_id, max_tail_lines=args.max_tail_lines)
    if args.runner_command == "status":
        if args.run_id:
            return {"ok": True, "run": service.get(args.run_id)}
        return {"ok": True, "runs": service.list_runs()}
    return {"ok": False, "error": "Unknown runner command", "error_type": "usage", "recoverable": True}


def _queue_payload(args: argparse.Namespace) -> dict:
    service = QueueService(_layout(args))
    if args.queue_command == "submit":
        return service.submit(job_id=args.job_id, command=args.command_text)
    if args.queue_command == "lease-next":
        return service.lease_next(worker_id=args.worker_id, ttl_seconds=args.ttl_seconds)
    if args.queue_command == "reconcile":
        return service.reconcile_expired_leases()
    if args.queue_command == "update":
        return service.update_job(args.job_id, args.status)
    if args.queue_command == "status":
        return service.status()
    return {"ok": False, "error": "Unknown queue command", "error_type": "usage", "recoverable": True}


def _wiki_payload(args: argparse.Namespace) -> dict:
    service = ResearchWikiService(_layout(args))
    if args.wiki_command == "add-paper":
        return {"ok": True, "record": service.add_paper(args.paper_id, title=args.title, summary=args.summary)}
    if args.wiki_command == "add-idea":
        return {"ok": True, "record": service.add_idea(args.idea_id, title=args.title, mechanism=args.mechanism)}
    if args.wiki_command == "add-edge":
        return {"ok": True, "record": service.add_edge(args.source_id, args.target_id, args.relation)}
    if args.wiki_command == "query-pack":
        return service.query_pack(max_chars=args.max_chars or args.limit or 12000)
    return {"ok": False, "error": "Unknown wiki command", "error_type": "usage", "recoverable": True}


def _frontier_payload(args: argparse.Namespace) -> dict:
    service = FrontierService(_layout(args))
    if args.frontier_command == "add":
        return {"ok": True, "candidate": service.add_candidate(args.idea_id, score=args.score, source=args.source, title=args.title)}
    if args.frontier_command == "select":
        return {"ok": True, "candidates": service.select(limit=args.limit)}
    if args.frontier_command == "promote":
        return service.promote(args.idea_id, evidence_level=args.evidence_level)
    if args.frontier_command == "propose-generated":
        return service.propose_generated_candidate(source=args.source, title=args.title)
    if args.frontier_command == "check-novelty":
        return service.check_novelty(idea_id=args.idea_id, mechanism=args.mechanism)
    return {"ok": False, "error": "Unknown frontier command", "error_type": "usage", "recoverable": True}


def _journal_payload(args: argparse.Namespace) -> dict:
    service = JournalService(_layout(args))
    if args.journal_command == "negative":
        return {
            "ok": True,
            "record": service.record_negative_result(
                trial_id=args.trial_id,
                idea_id=args.idea_id,
                failure_reason=args.failure_reason,
                lesson=args.lesson,
            ),
        }
    if args.journal_command == "stage-reflection":
        return service.record_stage_reflection(
            trigger=args.trigger,
            gaps=args.gap or [],
            next_sources=args.next_source or [],
        )
    return {"ok": False, "error": "Unknown journal command", "error_type": "usage", "recoverable": True}


def _summary_payload(args: argparse.Namespace) -> dict:
    layout = _layout(args)
    if args.summary_command == "context-pack":
        return ContextPackService(layout).write_context_pack(max_chars=args.max_chars)
    if args.summary_command == "checkpoint":
        return CheckpointService(layout).create_checkpoint(
            phase=args.phase,
            completed=args.completed or [],
            decisions=args.decision or [],
            validation=args.validation or [],
            next_action=args.next_action,
            artifact_refs=args.artifact_ref or [],
            risk_flags=args.risk_flag or [],
        )
    if args.summary_command == "resume-brief":
        return ResumeService(layout).resume_brief(
            max_chars=args.max_chars,
            include_recent_events=args.include_recent_events,
            include_risks=not args.no_risks,
        )
    if args.summary_command == "pack-delta":
        return ResumeService(layout).pack_delta(
            since_event_seq=args.since_event_seq,
            since_checkpoint_id=args.since_checkpoint_id,
            max_chars=args.max_chars,
        )
    if args.summary_command == "artifact-index":
        return ArtifactIndexService(layout).index(max_items=args.max_items)
    return {"ok": False, "error": "Unknown summary command", "error_type": "usage", "recoverable": True}


def _parse_metric_pairs(pairs: list[str]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise ValueError(f"Metric must use key=value format: {pair}")
        metrics[key] = float(value)
    return metrics


def _review_payload(args: argparse.Namespace) -> dict:
    service = ReviewService(_layout(args))
    if args.review_command == "create":
        return service.create_review(
            claim_text=args.claim_text,
            trial_ids=args.trial_id or [],
            artifact_paths=args.artifact_path or [],
            verdict=args.verdict,
            notes=args.notes,
        )
    if args.review_command == "status":
        return service.status()
    return {"ok": False, "error": "Unknown review command", "error_type": "usage", "recoverable": True}


def _claim_payload(args: argparse.Namespace) -> dict:
    service = ClaimEvidenceService(_layout(args))
    if args.claim_command == "upsert":
        return service.upsert_claim(
            claim_id=args.claim_id,
            text=args.text,
            supporting_trial_ids=args.supporting_trial_id or [],
            metric_values=_parse_metric_pairs(args.metric or []),
            artifact_paths=args.artifact_path or [],
            limitations=args.limitation or [],
            contradictory_trial_ids=args.contradictory_trial_id or [],
            reviewer_verdict=args.reviewer_verdict,
        )
    return {"ok": False, "error": "Unknown claim command", "error_type": "usage", "recoverable": True}


def _cost_payload(args: argparse.Namespace) -> dict:
    service = CostApprovalService(_layout(args), daily_cap_usd=getattr(args, "daily_cap_usd", 0.0) or 0.0)
    if args.cost_command == "check":
        return service.evaluate_action(action_class=args.action_class, estimated_cost_usd=args.estimated_cost_usd, approved=args.approved)
    if args.cost_command == "status":
        return service.status()
    return {"ok": False, "error": "Unknown cost command", "error_type": "usage", "recoverable": True}


def _migration_payload(args: argparse.Namespace) -> dict:
    service = MigrationService(_layout(args))
    if args.migrate_command == "legacy-quests":
        return service.migrate_legacy_quests()
    return {"ok": False, "error": "Unknown migrate command", "error_type": "usage", "recoverable": True}


def _soak_payload(args: argparse.Namespace) -> dict:
    service = SoakService(_layout(args))
    if args.soak_command == "accelerated":
        return service.run_accelerated(days=args.days, inject_failures=bool(args.inject_failures))
    if args.soak_command == "crash-resume":
        return service.crash_resume_smoke(restart_label=args.restart_label)
    return {"ok": False, "error": "Unknown soak command", "error_type": "usage", "recoverable": True}


def _add_format(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["json", "pretty"], default=None)


def build_cs_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex-Scientist native csctl. MCP is available through cs_mcp.py; this remains the CLI fallback.")
    parser.add_argument("--project-root", help="Project root whose ./CodexScientist runtime should be used. Defaults to cwd.")
    parser.add_argument("--format", choices=["json", "pretty"], default="pretty")
    sub = parser.add_subparsers(dest="command")

    manifest = sub.add_parser("manifest", help="Manage project-local CodexScientist/research.yaml")
    manifest_sub = manifest.add_subparsers(dest="manifest_command", required=True)
    init = manifest_sub.add_parser("init", help="Create CodexScientist/research.yaml")
    init.add_argument("--name", required=True)
    init.add_argument("--goal", required=True)
    init.add_argument("--overwrite", action="store_true")
    _add_format(init)
    init.set_defaults(func=_manifest_payload)
    validate = manifest_sub.add_parser("validate", help="Validate CodexScientist/research.yaml")
    _add_format(validate)
    validate.set_defaults(func=_manifest_payload)
    show = manifest_sub.add_parser("show", help="Show CodexScientist/research.yaml")
    _add_format(show)
    show.set_defaults(func=_manifest_payload)

    baseline = sub.add_parser("baseline", help="Manage baseline gate records in research.yaml")
    baseline_sub = baseline.add_subparsers(dest="baseline_command", required=True)
    confirm = baseline_sub.add_parser("confirm", help="Record a confirmed baseline")
    confirm.add_argument("--id", required=True)
    confirm.add_argument("--metric-contract", default="primary")
    _add_format(confirm)
    confirm.set_defaults(func=_baseline_payload)
    waive = baseline_sub.add_parser("waive", help="Record an explicit baseline waiver")
    waive.add_argument("--id", required=True)
    waive.add_argument("--reason", required=True)
    _add_format(waive)
    waive.set_defaults(func=_baseline_payload)
    baseline_show = baseline_sub.add_parser("show", help="Show baseline gate records")
    _add_format(baseline_show)
    baseline_show.set_defaults(func=_baseline_payload)

    trial = sub.add_parser("trial", help="Manage local trial FSM records")
    trial_sub = trial.add_subparsers(dest="trial_command", required=True)
    propose = trial_sub.add_parser("propose", help="Create a proposed trial")
    propose.add_argument("--quest-id", required=True)
    propose.add_argument("--idea-id", required=True)
    propose.add_argument("--hypothesis", required=True)
    propose.add_argument("--mechanism", required=True)
    _add_format(propose)
    propose.set_defaults(func=_trial_payload)
    plan = trial_sub.add_parser("plan", help="Move proposed trial to planned")
    plan.add_argument("trial_id")
    plan.add_argument("--metric-contract", default="primary")
    plan.add_argument("--novelty", required=True)
    _add_format(plan)
    plan.set_defaults(func=_trial_payload)
    ready = trial_sub.add_parser("ready", help="Move planned trial to ready after gates")
    ready.add_argument("trial_id")
    _add_format(ready)
    ready.set_defaults(func=_trial_payload)
    evaluate = trial_sub.add_parser("evaluate", help="Evaluate a ready trial against metric/artifact gates")
    evaluate.add_argument("trial_id")
    evaluate.add_argument("--metric", action="append")
    evaluate.add_argument("--artifact", action="append")
    _add_format(evaluate)
    evaluate.set_defaults(func=_trial_payload)
    decide = trial_sub.add_parser("decide", help="Keep or revert an evaluated trial after review")
    decide.add_argument("trial_id")
    decide.add_argument("--decision", choices=["keep", "revert"], required=True)
    decide.add_argument("--reviewer-verdict")
    _add_format(decide)
    decide.set_defaults(func=_trial_payload)
    trial_show = trial_sub.add_parser("show", help="Show one trial record")
    trial_show.add_argument("trial_id")
    _add_format(trial_show)
    trial_show.set_defaults(func=_trial_payload)

    runner = sub.add_parser("runner", help="Manage local runner records")
    runner_sub = runner.add_subparsers(dest="runner_command", required=True)
    runner_start = runner_sub.add_parser("start", help="Record a runner start without blocking")
    runner_start.add_argument("--command", dest="command_text", default="dry-run")
    runner_start.add_argument("--job-id")
    runner_start.add_argument("--dry-run", action="store_true")
    _add_format(runner_start)
    runner_start.set_defaults(func=_runner_payload)
    runner_collect = runner_sub.add_parser("collect", help="Collect a runner exit code")
    runner_collect.add_argument("run_id")
    runner_collect.add_argument("--exit-code", type=int, required=True)
    _add_format(runner_collect)
    runner_collect.set_defaults(func=_runner_payload)
    runner_tail = runner_sub.add_parser("tail", help="Read bounded redacted runner log tail")
    runner_tail.add_argument("run_id")
    runner_tail.add_argument("--limit", type=int, default=80)
    _add_format(runner_tail)
    runner_tail.set_defaults(func=_runner_payload)
    runner_log_digest = runner_sub.add_parser("log-digest", help="Read bounded redacted runner log digest")
    runner_log_digest.add_argument("run_id")
    runner_log_digest.add_argument("--max-tail-lines", type=int, default=40)
    _add_format(runner_log_digest)
    runner_log_digest.set_defaults(func=_runner_payload)
    runner_status = runner_sub.add_parser("status", help="Show one or all runner records")
    runner_status.add_argument("run_id", nargs="?")
    _add_format(runner_status)
    runner_status.set_defaults(func=_runner_payload)

    queue = sub.add_parser("queue", help="Manage local queue state")
    queue_sub = queue.add_subparsers(dest="queue_command", required=True)
    queue_submit = queue_sub.add_parser("submit", help="Submit a local queue job")
    queue_submit.add_argument("--job-id", required=True)
    queue_submit.add_argument("--command", dest="command_text", required=True)
    _add_format(queue_submit)
    queue_submit.set_defaults(func=_queue_payload)
    queue_lease = queue_sub.add_parser("lease-next", help="Lease the next pending job without implicit retry")
    queue_lease.add_argument("--worker-id", required=True)
    queue_lease.add_argument("--ttl-seconds", type=int, required=True)
    _add_format(queue_lease)
    queue_lease.set_defaults(func=_queue_payload)
    queue_reconcile = queue_sub.add_parser("reconcile", help="Mark expired leases reconcile_required")
    _add_format(queue_reconcile)
    queue_reconcile.set_defaults(func=_queue_payload)
    queue_update = queue_sub.add_parser("update", help="Update a local queue job status")
    queue_update.add_argument("job_id")
    queue_update.add_argument("--status", required=True)
    _add_format(queue_update)
    queue_update.set_defaults(func=_queue_payload)
    queue_status = queue_sub.add_parser("status", help="Show local queue status")
    _add_format(queue_status)
    queue_status.set_defaults(func=_queue_payload)

    wiki = sub.add_parser("wiki", help="Manage research wiki records")
    wiki_sub = wiki.add_subparsers(dest="wiki_command", required=True)
    wiki_paper = wiki_sub.add_parser("add-paper", help="Add compact paper record")
    wiki_paper.add_argument("--paper-id", required=True)
    wiki_paper.add_argument("--title", required=True)
    wiki_paper.add_argument("--summary", required=True)
    _add_format(wiki_paper)
    wiki_paper.set_defaults(func=_wiki_payload)
    wiki_idea = wiki_sub.add_parser("add-idea", help="Add compact idea record")
    wiki_idea.add_argument("--idea-id", required=True)
    wiki_idea.add_argument("--title", required=True)
    wiki_idea.add_argument("--mechanism", required=True)
    _add_format(wiki_idea)
    wiki_idea.set_defaults(func=_wiki_payload)
    wiki_edge = wiki_sub.add_parser("add-edge", help="Add typed wiki edge")
    wiki_edge.add_argument("--source-id", required=True)
    wiki_edge.add_argument("--target-id", required=True)
    wiki_edge.add_argument("--relation", required=True)
    _add_format(wiki_edge)
    wiki_edge.set_defaults(func=_wiki_payload)
    wiki_pack = wiki_sub.add_parser("query-pack", help="Build bounded query pack")
    wiki_pack.add_argument("--max-chars", type=int)
    wiki_pack.add_argument("--limit", type=int, help="Legacy alias for --max-chars")
    _add_format(wiki_pack)
    wiki_pack.set_defaults(func=_wiki_payload)

    frontier = sub.add_parser("frontier", help="Manage deterministic frontier candidates")
    frontier_sub = frontier.add_subparsers(dest="frontier_command", required=True)
    frontier_add = frontier_sub.add_parser("add", help="Add a scored frontier candidate")
    frontier_add.add_argument("--idea-id", required=True)
    frontier_add.add_argument("--score", type=float, required=True)
    frontier_add.add_argument("--source", required=True)
    frontier_add.add_argument("--title")
    _add_format(frontier_add)
    frontier_add.set_defaults(func=_frontier_payload)
    frontier_select = frontier_sub.add_parser("select", help="Select top deterministic candidates")
    frontier_select.add_argument("--limit", type=int, default=5)
    _add_format(frontier_select)
    frontier_select.set_defaults(func=_frontier_payload)
    frontier_promote = frontier_sub.add_parser("promote", help="Promote candidate according to evidence level")
    frontier_promote.add_argument("idea_id")
    frontier_promote.add_argument("--evidence-level", required=True)
    _add_format(frontier_promote)
    frontier_promote.set_defaults(func=_frontier_payload)
    frontier_generated = frontier_sub.add_parser("propose-generated", help="Propose generated candidate; default copilot returns needs_user_decision")
    frontier_generated.add_argument("--source", required=True)
    frontier_generated.add_argument("--title", required=True)
    _add_format(frontier_generated)
    frontier_generated.set_defaults(func=_frontier_payload)
    frontier_check = frontier_sub.add_parser("check-novelty", help="Block duplicates against negative memory")
    frontier_check.add_argument("--idea-id", required=True)
    frontier_check.add_argument("--mechanism", required=True)
    _add_format(frontier_check)
    frontier_check.set_defaults(func=_frontier_payload)

    journal = sub.add_parser("journal", help="Manage compact journal records")
    journal_sub = journal.add_subparsers(dest="journal_command", required=True)
    journal_negative = journal_sub.add_parser("negative", help="Record negative memory for a failed/reverted trial")
    journal_negative.add_argument("--trial-id", required=True)
    journal_negative.add_argument("--idea-id", required=True)
    journal_negative.add_argument("--failure-reason", required=True)
    journal_negative.add_argument("--lesson", required=True)
    _add_format(journal_negative)
    journal_negative.set_defaults(func=_journal_payload)
    journal_reflect = journal_sub.add_parser("stage-reflection", help="Record bounded stage reflection without autonomous trial creation")
    journal_reflect.add_argument("--trigger", required=True)
    journal_reflect.add_argument("--gap", action="append")
    journal_reflect.add_argument("--next-source", action="append")
    _add_format(journal_reflect)
    journal_reflect.set_defaults(func=_journal_payload)

    summary = sub.add_parser("summary", help="Build compact summaries for Codex /goal")
    summary_sub = summary.add_subparsers(dest="summary_command", required=True)
    context_pack = summary_sub.add_parser("context-pack", help="Write bounded CodexScientist/summaries/context_pack.md")
    context_pack.add_argument("--max-chars", type=int, required=True)
    _add_format(context_pack)
    context_pack.set_defaults(func=_summary_payload)
    checkpoint = summary_sub.add_parser("checkpoint", help="Write a compact recovery checkpoint")
    checkpoint.add_argument("--phase", required=True)
    checkpoint.add_argument("--completed", action="append")
    checkpoint.add_argument("--decision", action="append")
    checkpoint.add_argument("--validation", action="append")
    checkpoint.add_argument("--next-action", required=True)
    checkpoint.add_argument("--artifact-ref", action="append")
    checkpoint.add_argument("--risk-flag", action="append")
    _add_format(checkpoint)
    checkpoint.set_defaults(func=_summary_payload)
    resume_brief = summary_sub.add_parser("resume-brief", help="Return stable compact recovery anchors")
    resume_brief.add_argument("--max-chars", type=int, default=8000)
    resume_brief.add_argument("--include-recent-events", type=int, default=5)
    resume_brief.add_argument("--no-risks", action="store_true")
    _add_format(resume_brief)
    resume_brief.set_defaults(func=_summary_payload)
    pack_delta = summary_sub.add_parser("pack-delta", help="Return event deltas since a checkpoint or event sequence")
    pack_delta.add_argument("--since-event-seq", type=int)
    pack_delta.add_argument("--since-checkpoint-id")
    pack_delta.add_argument("--max-chars", type=int, default=6000)
    _add_format(pack_delta)
    pack_delta.set_defaults(func=_summary_payload)
    artifact_index = summary_sub.add_parser("artifact-index", help="Return artifact refs, hashes, sizes, and types")
    artifact_index.add_argument("--max-items", type=int, default=50)
    _add_format(artifact_index)
    artifact_index.set_defaults(func=_summary_payload)

    review = sub.add_parser("review", help="Create read-only review artifacts")
    review_sub = review.add_subparsers(dest="review_command", required=True)
    review_create = review_sub.add_parser("create", help="Create a structured read-only review")
    review_create.add_argument("--claim-text", required=True)
    review_create.add_argument("--trial-id", action="append")
    review_create.add_argument("--artifact-path", action="append")
    review_create.add_argument("--verdict", required=True)
    review_create.add_argument("--notes", default="")
    _add_format(review_create)
    review_create.set_defaults(func=_review_payload)
    review_status = review_sub.add_parser("status", help="Show read-only review artifact status")
    _add_format(review_status)
    review_status.set_defaults(func=_review_payload)

    claim = sub.add_parser("claim", help="Manage claim/evidence matrix")
    claim_sub = claim.add_subparsers(dest="claim_command", required=True)
    claim_upsert = claim_sub.add_parser("upsert", help="Upsert one claim with optional evidence")
    claim_upsert.add_argument("--claim-id", required=True)
    claim_upsert.add_argument("--text", required=True)
    claim_upsert.add_argument("--supporting-trial-id", action="append")
    claim_upsert.add_argument("--metric", action="append")
    claim_upsert.add_argument("--artifact-path", action="append")
    claim_upsert.add_argument("--limitation", action="append")
    claim_upsert.add_argument("--contradictory-trial-id", action="append")
    claim_upsert.add_argument("--reviewer-verdict")
    _add_format(claim_upsert)
    claim_upsert.set_defaults(func=_claim_payload)

    cost = sub.add_parser("cost", help="Check budget and approval gates")
    cost_sub = cost.add_subparsers(dest="cost_command", required=True)
    cost_check = cost_sub.add_parser("check", help="Evaluate one action class against budget/approval policy")
    cost_check.add_argument("--action-class", required=True)
    cost_check.add_argument("--estimated-cost-usd", type=float, required=True)
    cost_check.add_argument("--daily-cap-usd", type=float, required=True)
    cost_check.add_argument("--approved", action="store_true")
    _add_format(cost_check)
    cost_check.set_defaults(func=_cost_payload)
    cost_status = cost_sub.add_parser("status", help="Show latest cost/approval gate status")
    _add_format(cost_status)
    cost_status.set_defaults(func=_cost_payload)

    migrate = sub.add_parser("migrate", help="Migrate legacy CodexScientist state into the project-local control plane")
    migrate_sub = migrate.add_subparsers(dest="migrate_command", required=True)
    legacy_quests = migrate_sub.add_parser("legacy-quests", help="Migrate legacy CodexScientist/quests metadata without deleting sources")
    _add_format(legacy_quests)
    legacy_quests.set_defaults(func=_migration_payload)

    soak = sub.add_parser("soak", help="Run validation soaks and crash-resume smoke checks")
    soak_sub = soak.add_subparsers(dest="soak_command", required=True)
    accelerated = soak_sub.add_parser("accelerated", help="Run accelerated fake-clock long-run validation")
    accelerated.add_argument("--days", type=int, required=True)
    accelerated.add_argument("--inject-failures", action="store_true")
    _add_format(accelerated)
    accelerated.set_defaults(func=_soak_payload)
    crash_resume = soak_sub.add_parser("crash-resume", help="Record a restart and reconcile expired leases")
    crash_resume.add_argument("--restart-label", default="plugin-restart")
    _add_format(crash_resume)
    crash_resume.set_defaults(func=_soak_payload)
    return parser


def _looks_like_cs_command(argv: list[str]) -> bool:
    return any(command in argv for command in {"manifest", "baseline", "trial", "runner", "queue", "wiki", "frontier", "journal", "summary", "review", "claim", "cost", "migrate", "soak"})


def main(argv: list[str] | None = None) -> int:
    raw_argv = cs_native_cli._normalize_legacy_cli_args(list(sys.argv[1:] if argv is None else argv))
    if _looks_like_cs_command(raw_argv):
        parser = build_cs_parser()
        args = parser.parse_args(raw_argv)
        if not hasattr(args, "func"):
            parser.print_help(sys.stderr)
            return 2
        fmt = getattr(args, "format", None) or "pretty"
        payload = normalize_envelope(args.func(args))
        cs_native_cli.emit(payload, fmt)
        return 0 if payload.get("ok", False) else 1

    parser = cs_native_cli.build_parser()
    args = parser.parse_args(raw_argv)
    if args.project_root:
        _set_project_root(args.project_root)
    if not hasattr(args, "func"):
        parser.print_help(sys.stderr)
        return 2
    fmt = getattr(args, "format", None) or "pretty"
    payload = normalize_envelope(args.func(args))
    cs_native_cli.emit(payload, fmt)
    return 0 if payload.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
