from __future__ import annotations

import json

try:
    from .profiles import get_profile
    from .store import PonderForgeStore
except ImportError:
    from profiles import get_profile
    from store import PonderForgeStore

REVIEWER_ROLES = {
    "research": "fact_checker",
    "coding": "causality_reviewer",
    "design": "decision_reviewer",
    "analysis": "repro_reviewer",
    "math": "proof_reviewer",
}
REVIEW_CONTEXT_SCHEMA_VERSION = 2


def reviewer_role_for_profile(profile_id: str) -> str:
    if profile_id not in REVIEWER_ROLES:
        raise ValueError(f"unknown profile: {profile_id}")
    return REVIEWER_ROLES[profile_id]


def verify_run(store: PonderForgeStore, run_id: str, args: dict) -> dict:
    run = store.get_run(run_id)
    if not run:
        raise ValueError(f"unknown run_id: {run_id}")
    mode = str(args.get("mode") or "precheck")
    if mode == "precheck":
        return precheck(store, run_id, args)
    if mode == "independent_review" and args.get("verdict"):
        return record_independent_verdict(store, run_id, args)
    if mode == "independent_review":
        return create_reviewer_tasks(store, run_id, args)
    raise ValueError(f"unknown verify mode: {mode}")


def precheck(store: PonderForgeStore, run_id: str, args: dict) -> dict:
    target_ids = _target_assertion_ids(store, run_id, args)
    return {
        "run_id": run_id,
        "verifier_mode": "precheck",
        "target_ids": target_ids,
        "final_verdict": False,
        "risk_flags": ["precheck_only", "requires_independent_review"] if target_ids else ["no_target_assertions"],
    }


def create_reviewer_tasks(store: PonderForgeStore, run_id: str, args: dict) -> dict:
    run = store.get_run(run_id)
    assert run is not None
    profile = get_profile(str(run["profile"]))
    reviewer_role = reviewer_role_for_profile(profile.profile_id)
    tasks = []
    for assertion in _target_assertions(store, run_id, args):
        producer_task_id = _producer_task_id(store, assertion)
        existing = _accepted_independent_verdicts(store, assertion, producer_task_id)
        if existing:
            continue
        context = _review_context(store, profile.profile_id, assertion, producer_task_id)
        raw = _review_task_raw(assertion, producer_task_id)
        existing_task = _existing_reviewer_task(store, run_id, assertion["assertion_id"])
        if existing_task:
            existing_raw = _raw(existing_task)
            if existing_raw.get("review_context_schema_version") != REVIEW_CONTEXT_SCHEMA_VERSION:
                existing_task = store.update_task_context(existing_task["task_id"], context, raw=raw)
            tasks.append(existing_task)
            continue
        task = store.create_task(
            run_id,
            role=reviewer_role,
            goal=f"Independently review assertion {assertion['assertion_id']}: {assertion['text']}",
            context=context,
            parent_task_id=producer_task_id,
            priority=10,
            raw=raw,
        )
        tasks.append(task)
    return {"run_id": run_id, "verifier_mode": "independent_review", "reviewer_tasks": tasks, "delegate_task_payload_suggestion": _payload(run_id, profile.profile_id, tasks)}


def record_independent_verdict(store: PonderForgeStore, run_id: str, args: dict) -> dict:
    target_id = str(args.get("target_id") or "")
    if not target_id:
        raise ValueError("target_id is required for independent verdict")
    assertion = _assertion_by_id(store, run_id, target_id)
    if not assertion:
        raise ValueError(f"unknown target assertion: {target_id}")
    producer_task_id = _producer_task_id(store, assertion)
    reviewer_task_id = str(args.get("reviewer_task_id") or "")
    independent_from = str(args.get("independent_from_task_id") or "")
    if reviewer_task_id and reviewer_task_id == producer_task_id:
        raise ValueError("reviewer task is not independent from producer task")
    if producer_task_id and independent_from != producer_task_id:
        raise ValueError("verdict is not independent from the producer task")
    verdict_value = str(args.get("verdict") or "").lower()
    if verdict_value not in {"accept", "reject", "revise"}:
        raise ValueError("verdict must be accept, reject, or revise")
    run = store.get_run(run_id)
    assert run is not None
    verdict = store.create_verdict(
        run_id=run_id,
        profile=str(run["profile"]),
        target_type="assertion",
        target_id=target_id,
        reviewer_role=str(args.get("reviewer_role") or reviewer_role_for_profile(str(run["profile"]))),
        reviewer_task_id=reviewer_task_id or None,
        verifier_mode="independent_review",
        independent_from_task_id=independent_from or None,
        verdict=verdict_value,
        confidence=float(args["confidence"]) if args.get("confidence") is not None else None,
        rationale=args.get("rationale"),
        required_actions=args.get("required_actions") or [],
        raw={"source": "cli_verify"},
    )
    reviewer_task = store.get_task(reviewer_task_id) if reviewer_task_id else None
    if reviewer_task and reviewer_task.get("run_id") == run_id:
        store.update_task_status(reviewer_task_id, "finished")
    if verdict_value == "accept":
        store.update_assertion_status(target_id, "accepted")
    return {"run_id": run_id, "verifier_mode": "independent_review", "recorded_verdict": verdict, "final_verdict": verdict_value == "accept"}


def _target_assertions(store: PonderForgeStore, run_id: str, args: dict) -> list[dict]:
    ids = _target_assertion_ids(store, run_id, args)
    return [row for row in store.list_rows("assertions", run_id) if row["assertion_id"] in ids]


def _target_assertion_ids(store: PonderForgeStore, run_id: str, args: dict) -> list[str]:
    target = args.get("target_id")
    if target:
        return [str(target)]
    run = store.get_run(run_id)
    if not run:
        return []
    profile = get_profile(str(run["profile"]))
    ids = []
    for assertion in store.list_rows("assertions", run_id):
        raw = _raw(assertion)
        critical = bool(raw.get("critical")) or assertion.get("assertion_type") in profile.critical_assertion_types
        if critical:
            ids.append(assertion["assertion_id"])
    return ids


def _raw(row: dict) -> dict:
    try:
        return json.loads(row.get("raw_json") or "{}")
    except json.JSONDecodeError:
        return {}


def _clip(value: object, limit: int = 420) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _review_task_raw(assertion: dict, producer_task_id: str | None) -> dict:
    return {
        "verifier_mode": "independent_review",
        "target_assertion_id": assertion["assertion_id"],
        "independent_from_task_id": producer_task_id,
        "review_context_schema_version": REVIEW_CONTEXT_SCHEMA_VERSION,
    }


def _review_context(store: PonderForgeStore, profile_id: str, assertion: dict, producer_task_id: str | None) -> str:
    report_id = str(assertion.get("report_id") or "")
    report = store.get_report(report_id) if report_id else None
    evidence_rows = [
        row
        for row in store.list_rows("evidence_items", assertion["run_id"])
        if row.get("assertion_id") == assertion["assertion_id"]
    ]
    artifact_rows = [
        row for row in store.list_rows("artifacts", assertion["run_id"]) if report_id and row.get("report_id") == report_id
    ]
    lines = [
        f"target_assertion_id={assertion['assertion_id']}",
        f"independent_from_task_id={producer_task_id or ''}",
        f"review_profile={profile_id}",
        "",
        "Assertion under review:",
        f"- assertion_id: {assertion['assertion_id']}",
        f"- assertion_type: {assertion.get('assertion_type')}",
        f"- text: {_clip(assertion.get('text'), 900)}",
        f"- importance: {assertion.get('importance')}",
        f"- confidence: {assertion.get('confidence')}",
        f"- status: {assertion.get('status')}",
        "",
        "Producer report:",
        f"- report_id: {report_id or 'none'}",
        f"- producer_task_id: {producer_task_id or 'none'}",
        f"- role: {report.get('role') if report else 'none'}",
        f"- summary: {_clip(report.get('summary') if report else '', 700) or 'none'}",
        "",
        "Evidence visible to reviewer:",
    ]
    if evidence_rows:
        for index, evidence in enumerate(evidence_rows[:8], start=1):
            metric = _clip(evidence.get("metric_json"), 180)
            metric_suffix = f"; metric={metric}" if metric and metric != "{}" else ""
            lines.append(
                "- "
                f"[{index}] evidence_id={evidence.get('evidence_id')}; "
                f"type={evidence.get('evidence_type')}; "
                f"source={_clip(evidence.get('source_ref'), 260)}; "
                f"command={_clip(evidence.get('command'), 260)}; "
                f"exit_code={evidence.get('exit_code')}; "
                f"observation={_clip(evidence.get('quote_or_observation'), 700)}"
                f"{metric_suffix}"
            )
        if len(evidence_rows) > 8:
            lines.append(f"- {len(evidence_rows) - 8} additional evidence rows omitted from reviewer context.")
    else:
        lines.append("- none recorded for this assertion")

    lines.extend(["", "Artifacts visible to reviewer:"])
    if artifact_rows:
        for index, artifact in enumerate(artifact_rows[:6], start=1):
            lines.append(
                "- "
                f"[{index}] artifact_id={artifact.get('artifact_id')}; "
                f"type={artifact.get('artifact_type')}; "
                f"path={_clip(artifact.get('path'), 300)}; "
                f"summary={_clip(artifact.get('summary'), 500)}"
            )
        if len(artifact_rows) > 6:
            lines.append(f"- {len(artifact_rows) - 6} additional artifact rows omitted from reviewer context.")
    else:
        lines.append("- none recorded for the producer report")

    lines.extend(
        [
            "",
            "Reviewer instructions:",
            "- Review only the assertion, producer report, evidence, and artifacts in this context.",
            "- Do not continue the producer's reasoning or inspect private producer scratch state.",
            "- Return JSON with verdict=accept|reject|revise, confidence, rationale, and optional required_actions.",
            "- The parent/controller records the verdict with the Ponder-Forge CLI verify command.",
        ]
    )
    return "\n".join(lines)


def _existing_reviewer_task(store: PonderForgeStore, run_id: str, assertion_id: str) -> dict | None:
    for task in store.list_rows("agent_tasks", run_id):
        raw = _raw(task)
        if raw.get("verifier_mode") == "independent_review" and raw.get("target_assertion_id") == assertion_id:
            return task
    return None


def _assertion_by_id(store: PonderForgeStore, run_id: str, assertion_id: str) -> dict | None:
    for assertion in store.list_rows("assertions", run_id):
        if assertion["assertion_id"] == assertion_id:
            return assertion
    return None


def _producer_task_id(store: PonderForgeStore, assertion: dict) -> str | None:
    report_id = assertion.get("report_id")
    if not report_id:
        return None
    report = store.get_report(str(report_id))
    return str(report.get("task_id")) if report and report.get("task_id") else None


def _accepted_independent_verdicts(store: PonderForgeStore, assertion: dict, producer_task_id: str | None) -> list[dict]:
    verdicts = []
    for verdict in store.list_rows("verification_verdicts", assertion["run_id"]):
        if verdict.get("target_type") != "assertion" or verdict.get("target_id") != assertion["assertion_id"]:
            continue
        if verdict.get("verifier_mode") != "independent_review" or verdict.get("verdict") != "accept":
            continue
        if producer_task_id and verdict.get("independent_from_task_id") != producer_task_id:
            continue
        if verdict.get("reviewer_task_id") and verdict.get("reviewer_task_id") == producer_task_id:
            continue
        verdicts.append(verdict)
    return verdicts


def _payload(run_id: str, profile_id: str, tasks: list[dict]) -> dict:
    payload_tasks = []
    for task in tasks:
        marker = f"[PONDER_FORGE_RUN_ID={run_id}] [PONDER_FORGE_TASK_ID={task['task_id']}] [PONDER_FORGE_ROLE={task['role']}]"
        payload_tasks.append({"goal": f"{marker} {task['goal']}", "context": f"[PONDER_FORGE_PROFILE={profile_id}]\n{task['context']}", "role": "leaf"})
    return {"tasks": payload_tasks}
