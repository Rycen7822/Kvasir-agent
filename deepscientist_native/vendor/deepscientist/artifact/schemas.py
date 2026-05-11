from __future__ import annotations

ARTIFACT_DIRS = {
    "baseline": "baselines",
    "idea": "ideas",
    "decision": "decisions",
    "progress": "progress",
    "answer": "answers",
    "milestone": "milestones",
    "run": "runs",
    "report": "reports",
    "approval": "approvals",
    "graph": "graphs",
}

DECISION_ACTIONS = {
    "continue",
    "launch_experiment",
    "launch_analysis_campaign",
    "branch",
    "prepare_branch",
    "activate_branch",
    "reuse_baseline",
    "attach_baseline",
    "publish_baseline",
    "waive_baseline",
    "iterate",
    "reset",
    "stop",
    "write",
    "finalize",
    "request_user_decision",
}


def validate_artifact_payload(payload: dict) -> list[str]:
    errors: list[str] = []
    kind = payload.get("kind")
    if kind not in ARTIFACT_DIRS:
        errors.append(f"Unknown artifact kind: {kind}")
        return errors
    if kind == "decision":
        for field in ("verdict", "action", "reason"):
            if not payload.get(field):
                errors.append(f"Decision artifact requires `{field}`.")
        action = payload.get("action")
        if action and action not in DECISION_ACTIONS:
            errors.append(f"Unknown decision action: {action}")
    if kind == "run" and not payload.get("run_kind"):
        errors.append("Run artifact requires `run_kind`.")
    return errors


def guidance_for_kind(kind: str) -> str:
    if kind == "baseline":
        return "Baseline recorded. You can now reuse it or start idea selection."
    if kind == "idea":
        return "Idea captured. Evaluate whether it merits a decision and an experiment branch."
    if kind == "decision":
        return "Decision recorded. Follow the chosen action and notify the user with the reason."
    if kind == "run":
        return "Run recorded. Compare metrics, then decide whether to continue, branch, or stop."
    if kind == "milestone":
        return "Milestone recorded. Send a concise progress update to the active surface."
    if kind == "answer":
        return "Answer stored. This was a direct user-facing reply, not a long-running progress checkpoint."
    if kind == "report":
        return "Report saved. Use it to update SUMMARY.md and the next planning step."
    if kind == "approval":
        return "Approval captured. The quest may proceed with the approved step."
    if kind == "graph":
        return "Graph exported. Share the preview or attach it to a status response."
    return "Artifact stored. Refresh quest status and continue from the latest durable state."
