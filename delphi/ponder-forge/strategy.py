"""FrontierAgent strategy with only host tool and filesystem adaptations."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
import shlex

try:
    from .frontier_prompts import (ASYNC_SECTION, ENHANCED_PROMPT, FINAL_VERIFIER,
        LOCAL_VERIFIER, SEARCH_QUERY_LANGUAGE_NOTE, SUBAGENT_RESEARCH,
        TEAM_MANAGEMENT, render_team_effort)
except ImportError:
    from frontier_prompts import (ASYNC_SECTION, ENHANCED_PROMPT, FINAL_VERIFIER,
        LOCAL_VERIFIER, SEARCH_QUERY_LANGUAGE_NOTE, SUBAGENT_RESEARCH,
        TEAM_MANAGEMENT, render_team_effort)


def team_effort(run: dict) -> str:
    value = json.loads(run.get("config_json") or "{}").get("team_effort", "max")
    return value if value in ("high", "max") else "high"


def coordinator_prompt(run: dict) -> str:
    cli = f"python3 {shlex.quote(str(Path(__file__).resolve().parent / 'cli.py'))}"
    rid = shlex.quote(run["run_id"])
    tools = f"""# Available operations on this host
Use the native agent tools available in this session. Ponder stores research state;
it does not run models or supervise processes. Map the strategy's tool names as follows:
- add_task / update_task: {cli} plan --run-id {rid} --file board.json.
  board.json: {{"tasks":[{{"description":"sub-question", "owners":[], "resolution":"open"}}]}}.
  To update, supply the returned task id. Resolutions: open, in_progress, resolved, cancelled.
- create_subagent / assign_task: {cli} delegations --run-id {rid} --file assignments.json.
  assignments.json: {{"tasks":[{{"agent":"name", "system_prompt":"role", "prompt":"work", "task_ids":[]}}]}}.
  Then execute the returned work with actual native tools. Reuse an existing host agent
  for a follow-up assignment; Ponder's agent name is a logical identity, not a process id.
  Record a successful launch with delegations --run-id {rid} --started TASK_ID --host-agent-id HOST_ID.
- collect_reports: wait/collect with native tools, then {cli} submit-report --file report.json.
  report.json: {{"run_id":"{run['run_id']}","task_id":"TASK_ID","content":"full final reply"}}.
  Workers finish with their full final reply; this host does not expose submit_report as a tool.
- stop_subagent: cancel with the native host; record the confirmed cancellation using
  delegations --run-id {rid} --cancelled TASK_ID. Cancel board questions separately only if warranted.
- Prepare a final verifier: {cli} verify --run-id {rid} --mode final --file draft.md.
  Prepare conflict arbitration: verify --run-id {rid} --mode local --file conflict.json;
  conflict.json contains conflict and report_ids (at least two).
- Before returning a final answer, save the complete draft using
  {cli} finalize --run-id {rid} --file draft.md.
  On budget exhaustion or interruption, use --partial --reason REASON to save a partial result.
"""
    # Source prose says 'blocked', but the source task-board code accepts these four states.
    management = re.sub(r"Mark a genuine dead end `blocked` \(reason in\s*notes\)\.",
                        "Mark a genuine dead end `cancelled` and record its reason.", TEAM_MANAGEMENT)
    prompt = ENHANCED_PROMPT.format(date=date.today().isoformat(), tools=tools,
                                   team_management=management + ASYNC_SECTION.replace(
                                       "Sub-agents run **asynchronously**.",
                                       "When supported by the native host, sub-agents run **asynchronously**."))
    config = json.loads(run.get("config_json") or "{}")
    prompt += SEARCH_QUERY_LANGUAGE_NOTE
    prompt += f"\n# Current run\nOriginal question: {run['user_goal']}\nProfile: {run['profile']}\n"
    if config.get("constraints"):
        prompt += f"Constraints: {config['constraints']}\n"
    prompt += """\n# Host contract
Use actual host tool signatures and supplied project paths. Upstream /inputs,
/workspace and /outputs are logical labels; do not create these roots on this host.
The coordinator alone writes Ponder state. Workers return full reports and own
only their assigned files. A report arriving does not resolve its board question.
Keep negative results and uncertainties. If the host runs synchronously, collect
that batch before continuing; prompt text does not create background execution.
Do not implement another agent loop, fabricate execution receipts or treat the
CLI gate as proof that a scientific claim has been verified.
"""
    # Frontier's main-agent decorator appends this after the assembled base prompt.
    return prompt + render_team_effort(team_effort(run))


def worker_prompt(name: str, role: str = "") -> str:
    if "local_verifier" in name.lower():
        prompt = LOCAL_VERIFIER
    elif "verifier" in name.lower():
        prompt = FINAL_VERIFIER
    else:
        prompt = SUBAGENT_RESEARCH
        if role:
            prompt += f"\n# Your Role\n{role}\n"
    prompt = re.sub(r"# Terminal tool.*?(?=# Output Format)",
                    "# Task completion\nReturn the full report as your final reply.\n\n",
                    prompt, flags=re.S)
    prompt = prompt.replace("# Output Format (MANDATORY — pass this as `content` to submit_report)",
                            "# Output Format (MANDATORY — return as your final reply)")
    return prompt + SEARCH_QUERY_LANGUAGE_NOTE + """\n# Host contract
Use the native tools available to this worker. Complete this assignment with the
full report as your final reply; the coordinator records it through Ponder CLI.
Do not call a nonexistent submit_report tool or edit Ponder state. Do not spawn
another team. Use supplied project paths; /inputs, /workspace and /outputs are
logical labels, not permission to create new filesystem roots.
"""
