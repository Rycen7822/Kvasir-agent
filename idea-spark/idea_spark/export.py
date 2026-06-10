import json
from typing import Any

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


def render_markdown(
    room: dict[str, Any],
    messages: list[dict[str, Any]],
    artifacts: list[dict[str, Any]] | None = None,
    gates: list[dict[str, Any]] | None = None,
    open_needs: list[dict[str, Any]] | None = None,
) -> str:
    artifacts = artifacts or []
    gates = gates or []
    open_needs = open_needs or []
    lines = ["# Idea-Spark Room Report", ""]
    lines.append(f"Room: `{room['room_id']}`")
    if room.get("title"):
        lines.append(f"Title: {room['title']}")
    if room.get("topic"):
        lines.append(f"Topic: {room['topic']}")
    lines.append("")

    sections = {
        "Executive verdict": _render_gate_lines(gates),
        "Idea card": _render_artifact_lines(_artifacts_of(artifacts, "IdeaCard")),
        "Claim-level novelty table": _render_artifact_lines(_artifacts_of(artifacts, "AtomicClaim", "PriorArtEvidence", "NoveltyObjection")),
        "Accepted / rejected / gate / claim summary": _render_gate_lines(gates)
        + _render_artifact_lines(_artifacts_of(artifacts, "AtomicClaim", "GateDecision")),
        "Feasibility and experiment plan": _render_artifact_lines(
            _artifacts_of(artifacts, "FeasibilityObjection", "ExperimentPlan", "BenchmarkRequirement", "StressTest")
        ),
        "Reviewer risks": _render_artifact_lines(_artifacts_of(artifacts, "ReviewerRisk")),
        "Artifact lifecycle": _render_artifact_lines(artifacts),
        "Schema transitions": _render_artifact_lines(_artifacts_of(artifacts, "RegimeTransition")),
        "Open needs": _render_need_lines(open_needs),
    }

    for heading in REPORT_HEADINGS:
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
