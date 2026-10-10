import json
from typing import Any

try:
    from .workflow import DEEP_EXPLORATION, workflow_summary
except ImportError:
    from workflow import DEEP_EXPLORATION, workflow_summary

REPORT_HEADINGS = [
    "Executive verdict",
    "Idea card",
    "Claim-level novelty table",
    "Accepted / rejected / gate / claim summary",
    "Feasibility and experiment plan",
    "Reviewer risks",
    "Artifact lifecycle",
    "Schema transitions",
    "Open needs",
    "Full transcript appendix",
]

DEEP_REPORT_HEADINGS = [
    "Workflow outcome",
    "Research goal and challenge",
    "Methodological gaps",
    "Candidate history",
    "Literature and mechanism sources",
    "Adversarial reviews",
    "Research proposal",
    "Unverified questions and next steps",
    "Artifact index",
    "Full transcript appendix",
]


def _content_text(content: Any) -> str:
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False, sort_keys=True)
    return str(content)


def _artifacts_of(artifacts: list[dict[str, Any]], *types: str) -> list[dict[str, Any]]:
    wanted = set(types)
    return [artifact for artifact in artifacts if artifact.get("artifact_type") in wanted]


def _empty() -> str:
    return "No ledger-backed entries recorded."


def _render_artifact_lines(artifacts: list[dict[str, Any]]) -> list[str]:
    if not artifacts:
        return [_empty()]
    lines = []
    for artifact in artifacts:
        title = artifact.get("title") or artifact["artifact_id"]
        lines.append(
            f"- `{artifact['artifact_id']}` {artifact['artifact_type']} status={artifact['status']} "
            f"title={title} content={_content_text(artifact.get('content', {}))}"
        )
        if artifact.get("file_path"):
            lines.append(f"  File: `{artifact['file_path']}`")
    return lines


def _render_gate_lines(gates: list[dict[str, Any]]) -> list[str]:
    if not gates:
        return ["No gate-backed verdict recorded."]
    return [
        f"- `{gate['gate_id']}` {gate['gate_type']} decision={gate['decision']} rationale={gate['rationale']}"
        for gate in gates
    ]


def _render_need_lines(open_needs: list[dict[str, Any]]) -> list[str]:
    if not open_needs:
        return [_empty()]
    return [
        f"- `{need['need_id']}` target={need['target_artifact_type']} status={need['status']} "
        f"pressure={need['pressure_score']}: {need['query']} — {need['rationale']}"
        for need in open_needs
    ]


def _titles(artifacts: list[dict[str, Any]]) -> str:
    if not artifacts:
        return _empty()
    return "; ".join(artifact.get("title") or artifact["artifact_id"] for artifact in artifacts)


def _render_discussion_trajectory(artifacts: list[dict[str, Any]], gates: list[dict[str, Any]], open_needs: list[dict[str, Any]]) -> list[str]:
    latest_gate = gates[-1] if gates else None
    unresolved = [need for need in open_needs if need.get("status") in {"open", "claimed"}]
    resolved = [need for need in open_needs if need.get("status") == "resolved"]
    lines = ["### Discussion trajectory"]
    lines.append(f"- Novelty attack: {_titles(_artifacts_of(artifacts, 'NoveltyObjection', 'PriorArtEvidence'))}")
    lines.append(f"- Rebuttal: {_titles(_artifacts_of(artifacts, 'Rebuttal'))}")
    lines.append(f"- Improvement plan: {_titles(_artifacts_of(artifacts, 'RevisionPlan', 'ExperimentPlan'))}")
    lines.append(f"- Score cards: {_titles(_artifacts_of(artifacts, 'ScoreCard', 'MetaReview'))}")
    if latest_gate:
        lines.append(f"- Latest gate: decision={latest_gate['decision']} rationale={latest_gate['rationale']}")
    else:
        lines.append("- Latest gate: No gate-backed verdict recorded.")
    lines.append(f"- Unresolved needs: {len(unresolved)}; resolved needs: {len(resolved)}")
    return lines


def render_markdown(
    room: dict[str, Any],
    messages: list[dict[str, Any]],
    artifacts: list[dict[str, Any]] | None = None,
    gates: list[dict[str, Any]] | None = None,
    open_needs: list[dict[str, Any]] | None = None,
    links: list[dict[str, Any]] | None = None,
) -> str:
    artifacts = artifacts or []
    gates = gates or []
    open_needs = open_needs or []
    metadata = room.get("metadata")
    if metadata is None:
        metadata = json.loads(room.get("metadata_json") or "{}")
    workflow = workflow_summary(metadata, room.get("status", "open"))
    lines = ["# Idea-Spark Room Report", ""]
    lines.append(f"Room: `{room['room_id']}`")
    if room.get("title"):
        lines.append(f"Title: {room['title']}")
    if room.get("topic"):
        lines.append(f"Topic: {room['topic']}")
    lines.append(f"Workflow mode: `{workflow['workflow_mode']}`")
    lines.append("")

    sections = {
        "Executive verdict": _render_gate_lines(gates),
        "Idea card": _render_artifact_lines(_artifacts_of(artifacts, "IdeaCard")),
        "Claim-level novelty table": _render_artifact_lines(_artifacts_of(artifacts, "AtomicClaim", "PriorArtEvidence", "NoveltyObjection")),
        "Accepted / rejected / gate / claim summary": _render_gate_lines(gates)
        + _render_artifact_lines(_artifacts_of(artifacts, "AtomicClaim", "GateDecision"))
        + _render_discussion_trajectory(artifacts, gates, open_needs),
        "Feasibility and experiment plan": _render_artifact_lines(
            _artifacts_of(artifacts, "FeasibilityObjection", "ExperimentPlan", "BenchmarkRequirement", "StressTest")
        ),
        "Reviewer risks": _render_artifact_lines(_artifacts_of(artifacts, "ReviewerRisk")),
        "Artifact lifecycle": _render_artifact_lines(artifacts),
        "Schema transitions": _render_artifact_lines(_artifacts_of(artifacts, "RegimeTransition")),
        "Open needs": _render_need_lines(open_needs),
    }

    headings = REPORT_HEADINGS
    if workflow["workflow_mode"] == DEEP_EXPLORATION:
        state = workflow["workflow_state"]
        candidate_lines = _render_artifact_lines(_artifacts_of(artifacts, "IdeaCard"))
        for link in links or []:
            if link["relation"] == "evolves_from":
                candidate_lines.append(
                    f"- `{link['source_artifact_id']}` evolves_from `{link['target_artifact_id']}`"
                )
        outcome = [
            f"- Status: {room.get('status', 'open')}; terminal={workflow['is_terminal']}",
            f"- Phase: {state.get('phase') or '-'}; active candidate: {state.get('candidate_label') or '-'}",
            f"- Final artifact: {workflow['final_artifact_id'] or '-'}",
            "- Workflow completion records proposal delivery, not experimental validation.",
        ]
        if state.get("stop_reason"):
            outcome.append(f"- Stop reason: {state['stop_reason']}")
        sections = {
            "Workflow outcome": outcome,
            "Research goal and challenge": _render_artifact_lines(_artifacts_of(artifacts, "ResearchGoal")),
            "Methodological gaps": _render_artifact_lines(_artifacts_of(artifacts, "GapAnalysis")),
            "Candidate history": candidate_lines,
            "Literature and mechanism sources": _render_artifact_lines(_artifacts_of(artifacts, "PriorArtEvidence", "EvidenceLink")),
            "Adversarial reviews": _render_artifact_lines(_artifacts_of(artifacts, "MetaReview", "ScoreCard")),
            "Research proposal": _render_artifact_lines(_artifacts_of(artifacts, "ResearchProposal")),
            "Unverified questions and next steps": [
                f"- Next action: {state.get('next_action') or '-'}",
                "- Read the full proposal and review files for retained assumptions, predictions and limitations.",
            ] + _render_need_lines(open_needs),
            "Artifact index": _render_artifact_lines(artifacts),
        }
        headings = DEEP_REPORT_HEADINGS

    for heading in headings:
        lines.append(f"## {heading}")
        if heading == "Full transcript appendix":
            if messages:
                for message in messages:
                    lines.append(
                        f"- [{message.get('round_id') or '-'} / {message.get('phase') or '-'}] "
                        f"{message['agent_id']}: {message['content']}"
                    )
            else:
                lines.append("No transcript messages recorded.")
        else:
            lines.extend(sections[heading])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
