from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codex_scientist.mcp.tool_registry import call_tool


FORBIDDEN_KEYS = {
    "next_required_action",
    "allowed_tools_for_stage",
    "next_required_mcp_tool",
    "current_gate",
    "checkpoint_due",
    "next_checkpoint_tool",
}
FORBIDDEN_STRING_FRAGMENTS = (
    "route_reason=keyword:",
    "keyword:",
    "progress_watchdog",
    "required_tool",
)


def _ok(payload: dict[str, Any]) -> dict[str, Any]:
    assert payload.get("ok") is True, payload
    return payload


def _forbidden_hits(value: Any, path: str = "$", hits: list[str] | None = None) -> list[str]:
    hits = hits if hits is not None else []
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}"
            if key in FORBIDDEN_KEYS:
                hits.append(key_path)
            if key == "next_action" and isinstance(item, dict) and item.get("required_tool"):
                hits.append(f"{key_path}.required_tool")
            _forbidden_hits(item, key_path, hits)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _forbidden_hits(item, f"{path}[{index}]", hits)
    elif isinstance(value, str):
        for fragment in FORBIDDEN_STRING_FRAGMENTS:
            if fragment in value:
                hits.append(f"{path} contains {fragment}")
    return hits


def _new_quest(tmp_path: Path) -> str:
    payload = _ok(call_tool("cs_new_quest", {"project": str(tmp_path), "goal": "upgrade6", "title": "Upgrade 6"}))
    return str(payload["quest"]["quest_id"])


def _confirm_baseline(tmp_path: Path, quest_id: str) -> None:
    baseline = _ok(
        call_tool(
            "cs_create_local_baseline",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "baseline_id": "upgrade6_baseline",
                "summary": "Upgrade 6 baseline gate.",
                "overwrite": True,
            },
        )
    )
    _ok(call_tool("cs_confirm_baseline", {"project": str(tmp_path), **baseline["confirm_args"]}))


def test_representative_payloads_have_no_planner_keys(tmp_path: Path):
    quest_id = _new_quest(tmp_path)
    _confirm_baseline(tmp_path, quest_id)
    payloads = [
        call_tool("cs_get_quest_state", {"project": str(tmp_path), "quest_id": quest_id}),
        call_tool("cs_context_pack", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 1600}),
        call_tool("cs_resume_brief", {"project": str(tmp_path), "quest_id": quest_id, "max_chars": 1600}),
        call_tool("cs_record_user_requirement", {"project": str(tmp_path), "quest_id": quest_id, "message": "keep plugin thin"}),
        call_tool("cs_record_main_experiment", {"project": str(tmp_path), "quest_id": quest_id, "run_id": "R-UP6", "title": "thin plugin"}),
        call_tool(
            "cs_update_method_scoreboard",
            {
                "project": str(tmp_path),
                "quest_id": quest_id,
                "idea_id": "thin-plugin",
                "outcome": "positive",
                "metric_delta": 0.1,
                "mechanism": "remove duplicate planner",
            },
        ),
    ]

    for payload in payloads:
        _ok(payload)
        assert _forbidden_hits(payload) == [], json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_state_changing_tools_do_not_auto_write_watchdog_or_goal_gate(tmp_path: Path):
    quest_id = _new_quest(tmp_path)
    _confirm_baseline(tmp_path, quest_id)

    requirement = _ok(call_tool("cs_record_user_requirement", {"project": str(tmp_path), "quest_id": quest_id, "message": "no auto gates"}))
    experiment = _ok(call_tool("cs_record_main_experiment", {"project": str(tmp_path), "quest_id": quest_id, "run_id": "R-GATE", "title": "gate check"}))

    for payload in (requirement, experiment):
        assert "checkpoint_due" not in payload
        assert "next_checkpoint_tool" not in payload
        assert "progress_watchdog" not in payload

    quest_root = tmp_path / "CodexScientist" / "quests" / quest_id
    assert not (quest_root / "runtime" / "progress_watchdog.json").exists()

    goal_state = quest_root / "runtime" / "goal_state.json"
    if goal_state.exists():
        state = json.loads(goal_state.read_text(encoding="utf-8"))
        assert not state.get("current_gate")
        next_action = state.get("next_action") if isinstance(state.get("next_action"), dict) else {}
        assert not next_action.get("required_tool")
