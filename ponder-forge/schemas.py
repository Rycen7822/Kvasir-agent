from __future__ import annotations

TOOLSET = "ponder_forge"
TOOL_NAMES = [
    "ponder_forge_start",
    "ponder_forge_plan",
    "ponder_forge_prepare_delegations",
    "ponder_forge_report_submit",
    "ponder_forge_pool_status",
    "ponder_forge_verify",
    "ponder_forge_gate_status",
    "ponder_forge_finalize",
    "ponder_forge_reconcile",
]
HOOK_NAMES = [
    "subagent_start",
    "subagent_stop",
    "post_tool_call",
    "pre_tool_call",
    "pre_llm_call",
    "on_session_end",
]

_DESCRIPTIONS = {
    "ponder_forge_start": "Create a Ponder-Forge run for a complex problem and select a verifier profile.",
    "ponder_forge_plan": "Create workflow nodes and queued child-agent tasks for a Ponder-Forge run.",
    "ponder_forge_prepare_delegations": "Return native delegate_task payload for queued Ponder-Forge tasks.",
    "ponder_forge_report_submit": "Persist a structured child-agent report with assertions, evidence, artifacts, and gaps.",
    "ponder_forge_pool_status": "Return compact report-pool and gate status for a Ponder-Forge run.",
    "ponder_forge_verify": "Run precheck or create independent reviewer tasks for critical Ponder-Forge assertions.",
    "ponder_forge_gate_status": "Evaluate whether the active Ponder-Forge run satisfies its verifier profile gate.",
    "ponder_forge_finalize": "Render the final graph-backed Ponder-Forge report when gates allow it.",
    "ponder_forge_reconcile": "Recover orphan, running, or missing-submit Ponder-Forge tasks from durable state.",
}


def schema_for(name: str) -> dict:
    if name not in TOOL_NAMES:
        raise KeyError(f"unknown Ponder-Forge tool: {name}")
    return {
        "name": name,
        "description": _DESCRIPTIONS[name],
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
        },
    }
