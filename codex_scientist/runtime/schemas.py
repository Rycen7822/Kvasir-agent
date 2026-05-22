
"""JSON schemas for native CodexScientist Hermes tools."""
from __future__ import annotations

from typing import Any


def _schema(name: str, description: str, properties: dict[str, Any] | None = None, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties or {},
            "required": required or [],
            "additionalProperties": True,
        },
    }

MEMORY_KIND_VALUES = [
    "papers", "ideas", "decisions", "episodes", "knowledge", "templates",
    "paper", "idea", "decision", "episode", "template",
    "constraint", "constraints", "context", "observation", "observations", "hypothesis", "hypotheses", "result", "results", "plan", "plans",
]
MEMORY_KIND_FIELD = {
    "type": "string",
    "enum": MEMORY_KIND_VALUES,
    "description": "CodexScientist memory kind. Canonical kinds are papers, ideas, decisions, episodes, knowledge, templates. Singular and semantic aliases such as constraint/context/observation/hypothesis/result/plan are accepted and normalized by the MCP wrapper.",
}
PAPER_OUTLINE_MODE_FIELD = {
    "type": "string",
    "enum": ["candidate", "select", "revise", "selected"],
    "description": "Paper outline operation. Use candidate, then select, or revise. selected is accepted as a friendly alias for select.",
}
ARTIFACT_KIND_VALUES = ["baseline", "idea", "decision", "progress", "answer", "milestone", "run", "report", "approval", "graph"]
ARTIFACT_KIND_FIELD = {
    "type": "string",
    "enum": ARTIFACT_KIND_VALUES,
    "description": "Canonical artifact kind. For semantic subtypes such as dataset_inspection or metric_report use kind=report and put the subtype in payload.report_type.",
}

S = {
    "quest_id": {"type": "string", "description": "Root-bound provenance id. Omit in normal Codex plugin use. When provided, it must match CodexScientist/research.yaml and never changes storage root."},
    "goal": {"type": "string", "description": "Research goal or request."},
    "title": {"type": "string"},
    "stage": {"type": "string"},
    "message": {"type": "string"},
    "limit": {"type": "integer", "default": 20},
    "query": {"type": "string"},
    "scope": {"type": "string", "enum": ["global", "quest", "both"]},
    "kind": {"type": "string"},
    "content": {"type": "string"},
    "body": {"type": "string"},
    "path": {"type": "string"},
    "payload": {"type": "object"},
    "manifest": {"type": "object"},
    "env_id": {"type": "string"},
    "trajectory_id": {"type": "string"},
    "variant_id": {"type": "string"},
    "idea_id": {"type": "string"},
    "run_id": {"type": "string"},
    "source_kind": {"type": "string"},
    "idea": {"type": "object"},
    "command": {"type": "string"},
    "epoch": {"type": "integer", "default": 0},
    "batch_size": {"type": "integer", "default": 4},
    "job_id": {"type": "string"},
    "worker_id": {"type": "string"},
    "backend": {"type": "string", "default": "local"},
    "round_id": {"type": "string"},
    "submissions": {"type": "array", "items": {"type": "object"}},
    "approval": {"type": "object"},
    "expected_outputs": {"type": "array", "items": {"type": "string"}},
    "max_attempts": {"type": "integer", "default": 1},
}

CS_DOCTOR = _schema("cs_doctor", "Run native CodexScientist plugin diagnostics without invoking external cs.")
CS_LIST_QUESTS = _schema("cs_list_quests", "List CodexScientist quests from the native runtime home.", {"limit": S["limit"]})
CS_GET_QUEST_STATE = _schema("cs_get_quest_state", "Read compact or full state for a CodexScientist quest.", {"quest_id": S["quest_id"], "full": {"type": "boolean", "default": False}})
CS_SET_ACTIVE_QUEST = _schema("cs_set_active_quest", "Set the active quest for this CodexScientist MCP session.", {"quest_id": S["quest_id"], "session_id": {"type": "string"}, "stage": S["stage"]}, ["quest_id"])
CS_NEW_QUEST = _schema(
    "cs_new_quest",
    "Create a new CodexScientist quest natively. This tool is Codex-agent managed: default to copilot unless the agent explicitly chooses autonomous and supplies the final-goal contract.",
    {
        "goal": S["goal"],
        "quest_id": S["quest_id"],
        "title": S["title"],
        "session_id": {"type": "string"},
        "workspace_mode": {"type": "string", "enum": ["copilot", "autonomous"], "default": "copilot", "description": "Agent-chosen mode. Omit for safe default copilot; pass autonomous only when the user or manifest explicitly asks Codex-Scientist to own multi-step progress."},
        "decision_policy": {"type": "string", "enum": ["user_gated", "autonomous"], "default": "user_gated", "description": "Agent-chosen decision policy. Defaults to user_gated for copilot and autonomous only for explicit autonomous mode."},
        "autonomous_idea_improvement": {"type": "boolean", "default": False, "description": "Explicit gate for automatic idea or novelty improvement. Defaults false; set true only when the user explicitly asks or the manifest/handoff explicitly requires autonomous idea improvement."},
        "need_research_paper": {"type": "boolean", "default": False, "description": "Whether paper-like output is a default terminal goal. Defaults false unless the agent explicitly chooses a paper goal."},
        "final_goal": {"type": "string", "enum": ["paper", "quality_result", "idea_optimization", "literature_scout", "baseline_reproduction", "analysis_report", "open_ended"], "description": "Agent-defined terminal objective, separate from workspace_mode."},
        "delivery_mode": {"type": "string", "description": "Short agent-defined delivery label such as idea_quality, literature_map, quality_result, or paper_bundle."},
        "completion_criteria": {"type": "array", "items": {"type": "string"}, "description": "Concrete criteria the agent will use to decide that the autonomous task is sufficiently complete."},
        "mode_rationale": {"type": "string", "description": "Short explanation of why the agent selected the mode and final-goal contract."},
        "startup_contract": {"type": "object", "description": "Optional advanced contract fields; explicit values override generated defaults."},
    },
    ["goal"],
)
CS_UPDATE_QUEST_MODE = _schema(
    "cs_update_quest_mode",
    "Switch an existing CodexScientist quest between copilot and autonomous without creating or changing the quest. Use when the same research project moves from user-gated planning to autonomous execution, or back to copilot review.",
    {
        "quest_id": S["quest_id"],
        "workspace_mode": {"type": "string", "enum": ["copilot", "autonomous"], "description": "Agent-chosen mode for this existing quest."},
        "decision_policy": {"type": "string", "enum": ["user_gated", "autonomous"], "default": "user_gated", "description": "Defaults to user_gated for copilot and autonomous only for explicit autonomous mode."},
        "autonomous_idea_improvement": {"type": "boolean", "default": False, "description": "Explicit gate for automatic idea or novelty improvement. Defaults false; set true only when the user explicitly asks or the manifest/handoff explicitly requires autonomous idea improvement."},
        "need_research_paper": {"type": "boolean", "description": "Whether this mode switch makes a paper bundle the terminal goal. Do not infer this from autonomous alone."},
        "final_goal": {"type": "string", "enum": ["paper", "quality_result", "idea_optimization", "literature_scout", "baseline_reproduction", "analysis_report", "open_ended"], "description": "Terminal objective for the next phase, separate from workspace_mode."},
        "delivery_mode": {"type": "string", "description": "Delivery label for the next phase, such as experiment_execution, quality_result, analysis_report, or paper_bundle."},
        "completion_criteria": {"type": "array", "items": {"type": "string"}, "description": "Concrete criteria for determining the autonomous phase is complete."},
        "mode_rationale": {"type": "string", "description": "Required when switching to autonomous; short explanation of why the agent should own progress in the same quest."},
        "startup_contract": {"type": "object", "description": "Optional advanced contract fields to merge into the existing quest startup contract."},
    },
    ["quest_id", "workspace_mode"],
)
CS_ADD_USER_MESSAGE = _schema("cs_add_user_message", "Append a user message/instruction to a quest conversation. Set record_only=true for durable requirements that must not be queued as pending user input.", {"quest_id": S["quest_id"], "message": S["message"], "source": {"type": "string"}, "stage": S["stage"], "record_only": {"type": "boolean", "default": False}, "delivery_state": {"type": "string", "enum": ["sent", "record_only"]}}, ["message"])
CS_RECORD_USER_REQUIREMENT = _schema("cs_record_user_requirement", "Record a durable user requirement in the quest conversation and active-user-requirements memory without leaving a pending user-message queue item.", {"quest_id": S["quest_id"], "message": S["message"], "source": {"type": "string"}, "stage": S["stage"]}, ["message"])
CS_EVENTS = _schema("cs_events", "Read quest events directly from native quest files.", {"quest_id": S["quest_id"], "limit": S["limit"]}, ["quest_id"])
CS_READ_QUEST_DOCUMENTS = _schema("cs_read_quest_documents", "List or read quest documents and skill docs.", {"quest_id": S["quest_id"], "names": {"type": "array", "items": {"type": "string"}}, "include_content": {"type": "boolean", "default": True}, "max_chars": {"type": "integer", "default": 12000}})
CS_MEMORY_SEARCH = _schema("cs_memory_search", "Search CodexScientist global/quest memory cards.", {"query": S["query"], "quest_id": S["quest_id"], "scope": S["scope"], "kind": MEMORY_KIND_FIELD, "limit": S["limit"]}, ["query"])
CS_MEMORY_READ = _schema("cs_memory_read", "Read a CodexScientist memory card by id or path.", {"card_id": {"type": "string"}, "path": S["path"], "quest_id": S["quest_id"], "scope": S["scope"]})
CS_MEMORY_LIST_RECENT = _schema("cs_memory_list_recent", "List the most recently updated CodexScientist memory cards, matching the original memory.list_recent MCP capability through Codex-native transport.", {"quest_id": S["quest_id"], "scope": S["scope"], "kind": MEMORY_KIND_FIELD, "limit": S["limit"]})
CS_MEMORY_WRITE = _schema("cs_memory_write", "Write a CodexScientist memory card. Semantic kind aliases such as constraint/context/observation/hypothesis/result/plan are normalized to knowledge with tags/metadata.", {"title": S["title"], "content": S["content"], "body": S["body"], "markdown": {"type": "string"}, "quest_id": S["quest_id"], "scope": S["scope"], "kind": MEMORY_KIND_FIELD, "tags": {"type": "array", "items": {"type": "string"}}, "metadata": {"type": "object"}}, ["title"])
CS_ARTIFACT_RECORD = _schema("cs_artifact_record", "Record a canonical CodexScientist artifact in a quest. Use kind=report plus payload.report_type for semantic subtypes such as dataset_inspection.", {"quest_id": S["quest_id"], "payload": S["payload"], "kind": ARTIFACT_KIND_FIELD, "summary": {"type": "string"}, "status": {"type": "string"}, "checkpoint": {"type": "boolean"}}, ["quest_id"])
CS_CONFIRM_BASELINE = _schema("cs_confirm_baseline", "Confirm a baseline gate using native artifact service.", {"quest_id": S["quest_id"], "baseline_path": S["path"], "baseline_id": {"type": "string"}, "variant_id": {"type": "string"}, "summary": {"type": "string"}, "comment": {}, "metric_contract": {"type": "object"}}, ["quest_id", "baseline_path"])
CS_WAIVE_BASELINE = _schema("cs_waive_baseline", "Explicitly waive the baseline gate.", {"quest_id": S["quest_id"], "reason": {"type": "string"}, "comment": {}}, ["quest_id", "reason"])
CS_ATTACH_BASELINE = _schema("cs_attach_baseline", "Attach a registered/imported baseline to the quest workspace.", {"quest_id": S["quest_id"], "baseline_id": {"type": "string"}, "variant_id": {"type": "string"}}, ["quest_id", "baseline_id"])
CS_CREATE_LOCAL_BASELINE = _schema("cs_create_local_baseline", "Create a canonical local baseline stub under baselines/local/<baseline_id>/ and return confirm_args for cs_confirm_baseline.", {"quest_id": S["quest_id"], "baseline_id": {"type": "string"}, "title": S["title"], "summary": {"type": "string"}, "content": S["content"], "source_path": S["path"], "filename": {"type": "string", "default": "baseline.md"}, "variant_id": {"type": "string"}, "metric_contract": {"type": "object"}, "overwrite": {"type": "boolean", "default": False}}, ["quest_id", "baseline_id"])
CS_SUBMIT_IDEA = _schema("cs_submit_idea", "Submit or revise a CodexScientist idea line/candidate. In default copilot mode this records user/document-provided ideas; autonomous generation is gated by explicit user or manifest requirements.", {"quest_id": S["quest_id"], "title": S["title"], "source": {"type": "string", "enum": ["human", "paper", "document", "failed_trial", "frontier_gap", "review_gap", "ablation_gap"], "default": "human"}, "autonomous_generated": {"type": "boolean", "default": False, "description": "True only for ideas generated under an explicit autonomous idea-improvement request or manifest/handoff requirement."}, "problem": {"type": "string"}, "hypothesis": {"type": "string"}, "mechanism": {"type": "string"}, "method_brief": {"type": "string"}, "expected_gain": {"type": "string"}, "risks": {"type": "array"}, "decision_reason": {"type": "string"}, "next_target": {"type": "string"}}, ["quest_id", "title"])
CS_LIST_RESEARCH_BRANCHES = _schema("cs_list_research_branches", "List quest research branches/worktrees.", {"quest_id": S["quest_id"]}, ["quest_id"])
CS_RESOLVE_RUNTIME_REFS = _schema("cs_resolve_runtime_refs", "Resolve canonical CodexScientist research ids and runtime refs, matching the original artifact.resolve_runtime_refs MCP capability through Codex-native transport.", {"quest_id": S["quest_id"]})
CS_GET_PAPER_CONTRACT_HEALTH = _schema("cs_get_paper_contract_health", "Inspect whether the active paper line is unblocked for writing/finalize work, matching original artifact.get_paper_contract_health.", {"quest_id": S["quest_id"], "detail": {"type": "string", "enum": ["summary", "full"], "default": "summary"}})
CS_GET_GLOBAL_STATUS = _schema("cs_get_global_status", "Read a concise quest-global status summary, matching original artifact.get_global_status.", {"quest_id": S["quest_id"], "detail": {"type": "string", "enum": ["brief", "full"], "default": "brief"}, "locale": {"type": "string", "default": "zh"}})
CS_GET_METHOD_SCOREBOARD = _schema("cs_get_method_scoreboard", "Read or refresh the quest-level method scoreboard, matching original artifact.get_method_scoreboard.", {"quest_id": S["quest_id"]})
CS_GET_OPTIMIZATION_FRONTIER = _schema("cs_get_optimization_frontier", "Read a compact optimization-frontier summary for algorithm-first quests, matching original artifact.get_optimization_frontier.", {"quest_id": S["quest_id"]})
CS_RECORD_NEGATIVE_RESULT = _schema("cs_record_negative_result", "Record a negative method result into quest method memory.", {"quest_id": S["quest_id"], "trial_id": {"type": "string"}, "idea_id": {"type": "string"}, "failure_reason": {"type": "string"}, "lesson": {"type": "string"}, "mechanism": {"type": "string"}}, ["quest_id", "idea_id"])
CS_UPDATE_METHOD_SCOREBOARD = _schema("cs_update_method_scoreboard", "Update method improvement scoreboard and refresh frontier.", {"quest_id": S["quest_id"], "idea_id": {"type": "string"}, "outcome": {"type": "string"}, "metric_delta": {"type": "number"}, "lesson": {"type": "string"}, "mechanism": {"type": "string"}}, ["quest_id", "idea_id"])
CS_SELECT_NEXT_IDEA = _schema("cs_select_next_idea", "Select the next non-duplicate idea from the quest frontier.", {"quest_id": S["quest_id"]}, ["quest_id"])
CS_CLAIM_GATE = _schema("cs_claim_gate", "Block paper-facing claims until baseline, metric, evidence, analysis, and seed checks pass.", {"quest_id": S["quest_id"], "claim_id": {"type": "string"}, "claim_text": {"type": "string"}, "baseline_id": {"type": "string"}, "metric_contract": {"type": "string"}, "evidence_paths": {"type": "array"}, "analysis_slice_ids": {"type": "array"}, "seed_count": {"type": "integer"}}, ["quest_id", "claim_id"])
CS_GET_CONVERSATION_CONTEXT = _schema("cs_get_conversation_context", "Read a recent window of quest conversation history, matching original artifact.get_conversation_context.", {"quest_id": S["quest_id"], "limit": S["limit"], "include_attachments": {"type": "boolean", "default": False}})
CS_RECORD_MAIN_EXPERIMENT = _schema("cs_record_main_experiment", "Record a main experiment run.", {"quest_id": S["quest_id"], "run_id": {"type": "string"}, "title": S["title"], "hypothesis": {"type": "string"}, "setup": {"type": "string"}, "execution": {"type": "string"}, "results": {"type": "string"}, "conclusion": {"type": "string"}, "metric_rows": {"type": "array"}, "metrics_summary": {"type": "object"}, "evidence_paths": {"type": "array"}, "verdict": {"type": "string"}}, ["quest_id", "run_id"])
CS_CREATE_ANALYSIS_CAMPAIGN = _schema(
    "cs_create_analysis_campaign",
    "Create an evidence analysis campaign. Writing-facing optional fields such as research_questions, experimental_designs, or todo_items require selected_outline_ref.",
    {
        "quest_id": S["quest_id"],
        "campaign_title": S["title"],
        "campaign_goal": {"type": "string"},
        "slices": {"type": "array"},
        "selected_outline_ref": {"type": "string", "description": "Required when supplying writing-facing fields such as research_questions, experimental_designs, or todo_items."},
        "research_questions": {"type": "array", "items": {"type": "string"}, "description": "Writing-facing field; include selected_outline_ref."},
        "experimental_designs": {"type": "array", "items": {"type": "string"}, "description": "Writing-facing field; include selected_outline_ref and describe the exact analysis/experiment design for each slice."},
        "todo_items": {"type": "array", "items": {"type": "object", "required": ["slice_id", "section_id", "item_id", "paper_role", "claim_links"], "properties": {"slice_id": {"type": "string"}, "section_id": {"type": "string"}, "item_id": {"type": "string"}, "paper_role": {"type": "string"}, "claim_links": {"type": "array", "items": {"type": "string"}}}}, "description": "Writing-facing field; include one outline-bound todo per slice with section_id, item_id, paper_role, and claim_links."},
    },
    ["quest_id", "campaign_title", "campaign_goal", "slices"],
)
CS_GET_ANALYSIS_CAMPAIGN = _schema("cs_get_analysis_campaign", "Read the active or specified analysis campaign, including pending slice diagnostics.", {"quest_id": S["quest_id"], "campaign_id": {"type": "string", "default": "active", "description": "Use active or omit to inspect the current active campaign."}}, ["quest_id"])
CS_RECORD_ANALYSIS_SLICE = _schema("cs_record_analysis_slice", "Record an analysis slice result.", {"quest_id": S["quest_id"], "campaign_id": {"type": "string"}, "slice_id": {"type": "string"}, "status": {"type": "string"}, "setup": {"type": "string"}, "execution": {"type": "string"}, "results": {"type": "string"}}, ["quest_id", "campaign_id", "slice_id"])
CS_SUBMIT_PAPER_OUTLINE = _schema("cs_submit_paper_outline", "Submit/select/revise a paper outline. selected is accepted as an alias for select.", {"quest_id": S["quest_id"], "mode": PAPER_OUTLINE_MODE_FIELD, "outline_id": {"type": "string"}, "title": S["title"], "note": {"type": "string"}, "story": {"type": "string"}, "ten_questions": {"type": "array"}, "detailed_outline": {"type": ["object", "array"], "description": "Object with sections/experimental_designs, a list of section title strings, or a list of section objects."}}, ["quest_id"])
CS_LIST_PAPER_OUTLINES = _schema("cs_list_paper_outlines", "List candidate/revised paper outlines and the selected outline reference, matching original artifact.list_paper_outlines.", {"quest_id": S["quest_id"]})
CS_SUBMIT_PAPER_BUNDLE = _schema("cs_submit_paper_bundle", "Submit a paper bundle manifest.", {"quest_id": S["quest_id"], "title": S["title"], "summary": {"type": "string"}, "outline_path": S["path"], "draft_path": S["path"], "writing_plan_path": S["path"], "references_path": S["path"], "claim_evidence_map_path": S["path"], "compile_report_path": S["path"], "pdf_path": S["path"], "latex_root_path": S["path"], "prepare_open_source": {"type": "boolean"}}, ["quest_id"])
CS_REFRESH_SUMMARY = _schema("cs_refresh_summary", "Refresh SUMMARY.md from recent artifact state, matching original artifact.refresh_summary.", {"quest_id": S["quest_id"], "reason": {"type": "string"}})
CS_ARXIV = _schema("cs_arxiv", "Interact with the quest-local arXiv library, matching original artifact.arxiv through Codex-native transport.", {"quest_id": S["quest_id"], "paper_id": {"type": "string"}, "mode": {"type": "string", "enum": ["read", "list"], "default": "read"}, "full_text": {"type": "boolean", "default": False}})
CS_ENVIRONMENT_REGISTER = _schema("cs_environment_register", "Register an execution-grounded research environment manifest without running experiments.", {"quest_id": S["quest_id"], "manifest": S["manifest"]}, ["quest_id", "manifest"])
CS_ENVIRONMENT_VALIDATE = _schema("cs_environment_validate", "Validate a registered execution-grounded environment manifest, protected hashes, and metric parser.", {"quest_id": S["quest_id"], "env_id": S["env_id"]}, ["quest_id", "env_id"])
CS_ENVIRONMENT_SHOW = _schema("cs_environment_show", "Read a bounded registered execution-grounded environment manifest.", {"quest_id": S["quest_id"], "env_id": S["env_id"]}, ["quest_id", "env_id"])
CS_FEEDBACK_INGEST = _schema(
    "cs_feedback_ingest",
    "Ingest local execution feedback metrics/logs into an existing trajectory after validating the environment; does not run experiments.",
    {
        "quest_id": S["quest_id"],
        "env_id": S["env_id"],
        "trajectory_id": S["trajectory_id"],
        "run_id": S["run_id"],
        "source_kind": S["source_kind"],
        "metrics_path": S["path"],
        "log_paths": {"type": "array", "items": {"type": "string"}},
        "trusted_primary_metric": {"type": "boolean", "default": False},
    },
    ["quest_id", "env_id", "trajectory_id", "run_id", "source_kind"],
)
CS_TRAJECTORY_RECORD = _schema(
    "cs_trajectory_record",
    "Create or update an execution-grounded trajectory record; records state only and never creates variants or jobs.",
    {
        "quest_id": S["quest_id"],
        "env_id": S["env_id"],
        "trajectory_id": S["trajectory_id"],
        "operation": {"type": "string", "enum": ["create", "update_patch", "update_variant", "update_job", "update_result"], "default": "create"},
        "idea": S["idea"],
        "strategy": {"type": "string", "default": "manual"},
        "parents": {"type": "array", "items": {"type": "string"}},
        "patch": {"type": "object"},
        "variant": {"type": "object"},
        "job": {"type": "object"},
        "result": {"type": "object"},
        "failure": {"type": "object"},
    },
    ["quest_id"],
)
CS_TRAJECTORY_SEARCH = _schema("cs_trajectory_search", "Search execution-grounded trajectories with optional env/status/positive filters.", {"quest_id": S["quest_id"], "env_id": S["env_id"], "status": {"type": "string"}, "positive_only": {"type": "boolean", "default": False}, "limit": S["limit"]}, ["quest_id"])
CS_TRAJECTORY_SHOW = _schema("cs_trajectory_show", "Read one execution-grounded trajectory with bounded/redacted path output.", {"quest_id": S["quest_id"], "trajectory_id": S["trajectory_id"]}, ["quest_id", "trajectory_id"])
CS_EVOLUTIONARY_PLAN_ROUND = _schema(
    "cs_evolutionary_plan_round",
    "Create a deterministic, plan-only evolutionary round from evaluated trajectories; writes a round-plan artifact but never submits jobs or creates variants.",
    {"quest_id": S["quest_id"], "env_id": S["env_id"], "epoch": S["epoch"], "batch_size": S["batch_size"]},
    ["quest_id", "env_id"],
)
_EXECUTOR_GATE_FIELDS = {
    "approved": {"type": "boolean", "default": False, "description": "Required unless an explicit local-only zero-cost gate is satisfied."},
    "local_only": {"type": "boolean", "default": False, "description": "Allow only zero-GPU/zero-cost local toy execution after environment validation."},
    "executor_gate": {"type": "string", "enum": ["local_only"], "description": "Explicit local-only executor gate token."},
}
CS_VARIANT_CREATE = _schema(
    "cs_variant_create",
    "Create an isolated execution variant worktree after executor approval or local-only gate.",
    {"quest_id": S["quest_id"], "env_id": S["env_id"], "trajectory_id": S["trajectory_id"], "idea_id": S["idea_id"], **_EXECUTOR_GATE_FIELDS},
    ["quest_id", "env_id", "trajectory_id", "idea_id"],
)
CS_VARIANT_APPLY_PATCH = _schema(
    "cs_variant_apply_patch",
    "Apply a patch inside an isolated variant workspace after executor approval or local-only gate.",
    {"quest_id": S["quest_id"], "variant_id": S["variant_id"], "patch_path": S["path"], **_EXECUTOR_GATE_FIELDS},
    ["quest_id", "variant_id", "patch_path"],
)
CS_VARIANT_CHECK = _schema(
    "cs_variant_check",
    "Run environment smoke checks for one isolated variant after executor approval or local-only gate.",
    {"quest_id": S["quest_id"], "variant_id": S["variant_id"], **_EXECUTOR_GATE_FIELDS},
    ["quest_id", "variant_id"],
)
CS_VARIANT_PACK = _schema(
    "cs_variant_pack",
    "Create a deterministic package for one checked variant after executor approval or local-only gate.",
    {"quest_id": S["quest_id"], "variant_id": S["variant_id"], **_EXECUTOR_GATE_FIELDS},
    ["quest_id", "variant_id"],
)
CS_SCHEDULER_SUBMIT = _schema(
    "cs_scheduler_submit",
    "Submit a deterministic local execution job for a packed variant through executor-local SchedulerService.",
    {
        "quest_id": S["quest_id"],
        "env_id": S["env_id"],
        "trajectory_id": S["trajectory_id"],
        "variant_id": S["variant_id"],
        "package_path": S["path"],
        "backend": S["backend"],
        "command": S["command"],
        "expected_outputs": S["expected_outputs"],
        "max_attempts": S["max_attempts"],
    },
    ["quest_id", "env_id", "trajectory_id", "variant_id", "package_path", "command"],
)
CS_SCHEDULER_STATUS = _schema("cs_scheduler_status", "Read executor-local scheduler queue status.", {"quest_id": S["quest_id"], "env_id": S["env_id"]})
CS_WORKER_CLAIM = _schema("cs_worker_claim", "Claim and start one pending executor-local scheduler job.", {"quest_id": S["quest_id"], "env_id": S["env_id"], "worker_id": S["worker_id"], "ttl_seconds": {"type": "integer", "default": 3600}, "dry_run": {"type": "boolean", "default": False}}, ["worker_id"])
CS_WORKER_HEARTBEAT = _schema("cs_worker_heartbeat", "Record a heartbeat for an executor-local worker run.", {"quest_id": S["quest_id"], "env_id": S["env_id"], "run_id": S["run_id"]}, ["run_id"])
CS_WORKER_COLLECT = _schema("cs_worker_collect", "Collect one executor-local worker job and ingest metrics/log feedback.", {"quest_id": S["quest_id"], "env_id": S["env_id"], "job_id": S["job_id"], "trusted_primary_metric": {"type": "boolean", "default": False}}, ["job_id"])
CS_WORKER_UPLOAD_ARTIFACT = _schema("cs_worker_upload_artifact", "Copy one local worker artifact into the quest execution-grounded artifact area.", {"quest_id": S["quest_id"], "env_id": S["env_id"], "job_id": S["job_id"], "artifact_path": S["path"], "kind": S["kind"]}, ["job_id", "artifact_path"])
CS_EVOLUTIONARY_ROUND_SUBMIT = _schema(
    "cs_evolutionary_round_submit",
    "Submit scheduler jobs for an existing EvolutionaryRoundPlan; never creates variants and requires explicit approval when the plan requires it.",
    {"quest_id": S["quest_id"], "env_id": S["env_id"], "round_id": S["round_id"], "approval": S["approval"], "submissions": S["submissions"], "backend": S["backend"]},
    ["quest_id", "env_id", "round_id", "submissions"],
)
CS_IMPLEMENTER_PATCH_CHECK = _schema(
    "cs_implementer_patch_check",
    "Check an implementer patch against a variant gate without running full training.",
    {"quest_id": S["quest_id"], "variant_id": S["variant_id"], "patch_path": S["path"], **_EXECUTOR_GATE_FIELDS},
    ["quest_id", "variant_id", "patch_path"],
)
CS_IMPLEMENTER_REPAIR_PATCH = _schema(
    "cs_implementer_repair_patch",
    "Return fail-closed repair guidance for a failed implementer patch; execution remains gated.",
    {"quest_id": S["quest_id"], "variant_id": S["variant_id"], "patch_path": S["path"], "failure": {"type": "object"}, **_EXECUTOR_GATE_FIELDS},
    ["quest_id", "variant_id"],
)
CS_BASH_EXEC = _schema(
    "cs_bash_exec",
    "Run/list/read/wait/stop quest-local bash sessions. For operation=run this is a formal provenance tool, not a general shell: provide command, command_class, provenance_reason, experiment_or_artifact_id, cwd_policy, and expected_outputs or evidence_paths.",
    {
        "quest_id": S["quest_id"],
        "command": S["command"],
        "operation": {"type": "string", "enum": ["run", "list", "status", "read", "wait", "stop"], "description": "Use run only for formal CodexScientist evidence/provenance commands."},
        "command_class": {"type": "string", "enum": ["formal_experiment", "benchmark", "paper_build", "reproduction", "official_evaluation"], "description": "Required for operation=run; classify the formal evidence command."},
        "provenance_reason": {"type": "string", "description": "Required for operation=run; explain why this command must be recorded as quest-local evidence."},
        "experiment_or_artifact_id": {"type": "string", "description": "Required for operation=run; link the command to a run, baseline, analysis slice, paper artifact, or official evaluation id."},
        "cwd_policy": {"type": "string", "enum": ["quest", "project"], "description": "Required for operation=run; prefer quest, use project only when allow_project_root=true is justified."},
        "expected_outputs": {"type": "array", "items": {"type": "string"}, "description": "For operation=run provide expected output files, metrics, or evidence products unless evidence_paths is already known."},
        "evidence_paths": {"type": "array", "items": {"type": "string"}, "description": "For operation=run provide existing or planned evidence paths when expected_outputs is not used."},
        "bash_id": {"type": "string"},
        "workdir": {"type": "string"},
        "allow_project_root": {"type": "boolean", "default": False},
        "env": {"type": "object"},
        "timeout_seconds": {"type": "integer"},
        "wait": {"type": "boolean"},
        "limit": S["limit"],
        "summary_mode": {"type": "boolean", "default": False},
        "response_mode": {"type": "string", "enum": ["full", "summary", "compact"]},
    },
)
CS_BASH_EXEC["input_schema"]["allOf"] = [
    {
        "if": {"properties": {"operation": {"const": "run"}}, "required": ["operation"]},
        "then": {
            "required": ["quest_id", "command", "command_class", "provenance_reason", "experiment_or_artifact_id", "cwd_policy"],
            "anyOf": [{"required": ["expected_outputs"]}, {"required": ["evidence_paths"]}],
        },
    }
]
CS_WORKFLOW_SMOKE_REPORT = _schema("cs_workflow_smoke_report", "Return a lightweight CodexScientist full-workflow checklist and path readiness report without running training.", {"quest_id": S["quest_id"], "dataset_path": S["path"], "paper_path": S["path"], "report_dir": S["path"]})
CS_STRICT_RESEARCH_PREPARE = _schema("cs_strict_research_prepare", "Initialize strict literature research mode in the active quest: create reference/candidate_references.md and return conservative screening workflow guidance.", {"quest_id": S["quest_id"], "intent": {"type": "string"}, "target_count": {"type": "integer"}, "complexity": {"type": "string", "enum": ["small", "medium", "large", "survey"]}})
CS_STRICT_RESEARCH_RECORD_CANDIDATE = _schema("cs_strict_research_record_candidate", "Append a candidate paper to reference/candidate_references.md during broad scouting before deep reading.", {"quest_id": S["quest_id"], "title": S["title"], "doi": {"type": "string"}, "link": {"type": "string"}, "source": {"type": "string"}, "authors": {"type": "string"}, "year": {"type": "string"}, "note": {"type": "string"}, "status": {"type": "string"}}, ["title"])
CS_STRICT_RESEARCH_UPSERT_CANDIDATE = _schema("cs_strict_research_upsert_candidate", "Upsert or update a strict-research candidate row in reference/candidate_references.md by title, DOI, or link.", {"quest_id": S["quest_id"], "key": {"type": "string", "description": "Existing title/DOI/link to match. Omit when title/doi/link should be used directly."}, "key_field": {"type": "string", "enum": ["title", "doi", "link"]}, "title": S["title"], "doi": {"type": "string"}, "link": {"type": "string"}, "source": {"type": "string"}, "authors": {"type": "string"}, "year": {"type": "string"}, "note": {"type": "string"}, "status": {"type": "string"}, "evidence_card": {"type": "string"}, "reliability_card": {"type": "string"}, "retain_reject_reason": {"type": "string"}, "reason": {"type": "string"}})
CS_PAPER_FETCH = _schema("cs_paper_fetch", "Fetch an official paper PDF into reference/pdfs/ and record canonical_url, sha256, page_count, body_text_status, official_resource_status, and a quest-local ledger row.", {"quest_id": S["quest_id"], "title": S["title"], "url": {"type": "string"}, "pdf_url": {"type": "string"}, "arxiv_id": {"type": "string"}, "arxiv_url": {"type": "string"}, "openreview_id": {"type": "string"}, "pmlr_url": {"type": "string"}, "output_name": {"type": "string"}, "overwrite": {"type": "boolean", "default": False}})
CS_RECORD_LITERATURE_READING_NOTE = _schema("cs_record_literature_reading_note", "Record a strict-research reading note and optional bibliography updates for one retained paper.", {"quest_id": S["quest_id"], "paper_id": {"type": "string"}, "title": S["title"], "pdf_path": S["path"], "surfaces_read": {"type": "array", "items": {"type": "string"}}, "sections_read": {"type": "array", "items": {"type": "string"}}, "note": {"type": "string"}, "claim_routes": {"type": "array", "items": {"type": "string"}}, "status": {"type": "string"}, "bibliography_updates": {"type": "object", "description": "Optional keys: essential_reference_details, reference_list, priority_reference_materials."}})
CS_STRICT_RESEARCH_INIT_BIBLIOGRAPHY = _schema("cs_strict_research_init_bibliography", "Create reference/bibliography/ and the three strict-research bibliography working files after enough retained references exist.", {"quest_id": S["quest_id"], "overwrite": {"type": "boolean", "default": False}})
CS_PAPER_RELIABILITY_VERIFY = _schema("cs_paper_reliability_verify", "Run the bundled paper_reliability_verifier for one candidate and store the JSON evidence card under reference/reliability_cards/; pass dry_run=true or network=false for bounded no-network planning.", {"quest_id": S["quest_id"], "title": S["title"], "doi": {"type": "string"}, "year": {"type": "integer"}, "url": {"type": "string"}, "arxiv_url": {"type": "string"}, "accepted_venue": {"type": "string"}, "accepted_type": {"type": "string"}, "accepted_acronym": {"type": "string"}, "include_raw": {"type": "boolean", "default": False}, "dry_run": {"type": "boolean", "default": False}, "network": {"type": "boolean", "default": True}, "timeout_seconds": {"type": "integer"}, "output_name": {"type": "string"}, "response_mode": {"type": "string", "enum": ["full", "summary", "compact"], "default": "full"}})
CS_PAUSE_QUEST = _schema("cs_pause_quest", "Mark a quest paused.", {"quest_id": S["quest_id"]}, ["quest_id"])
CS_RESUME_QUEST = _schema("cs_resume_quest", "Mark a quest active/resumed.", {"quest_id": S["quest_id"]}, ["quest_id"])
CS_STOP_QUEST = _schema("cs_stop_quest", "Mark a quest stopped.", {"quest_id": S["quest_id"], "reason": {"type": "string"}}, ["quest_id"])

# Compatibility aliases for one transition cycle.
CODEXSCIENTIST_DOCTOR = {**CS_DOCTOR, "name": "codexscientist_doctor"}
CODEXSCIENTIST_LIST_QUESTS = {**CS_LIST_QUESTS, "name": "codexscientist_list_quests"}
CODEXSCIENTIST_STATUS = {**CS_GET_QUEST_STATE, "name": "codexscientist_status"}
CODEXSCIENTIST_NEW_QUEST = {**CS_NEW_QUEST, "name": "codexscientist_new_quest"}
CODEXSCIENTIST_SEND_MESSAGE = {**CS_ADD_USER_MESSAGE, "name": "codexscientist_send_message"}
CODEXSCIENTIST_EVENTS = {**CS_EVENTS, "name": "codexscientist_events"}
CODEXSCIENTIST_READ_DOCUMENTS = {**CS_READ_QUEST_DOCUMENTS, "name": "codexscientist_read_documents"}
CODEXSCIENTIST_MEMORY_SEARCH = {**CS_MEMORY_SEARCH, "name": "codexscientist_memory_search"}
CODEXSCIENTIST_MEMORY_WRITE = {**CS_MEMORY_WRITE, "name": "codexscientist_memory_write"}
CODEXSCIENTIST_CONFIRM_BASELINE = {**CS_CONFIRM_BASELINE, "name": "codexscientist_confirm_baseline"}
CODEXSCIENTIST_SUBMIT_IDEA = {**CS_SUBMIT_IDEA, "name": "codexscientist_submit_idea"}
CODEXSCIENTIST_RECORD_EXPERIMENT = {**CS_RECORD_MAIN_EXPERIMENT, "name": "codexscientist_record_experiment"}
CODEXSCIENTIST_SUBMIT_PAPER_BUNDLE = {**CS_SUBMIT_PAPER_BUNDLE, "name": "codexscientist_submit_paper_bundle"}
CODEXSCIENTIST_PAUSE = {**CS_PAUSE_QUEST, "name": "codexscientist_pause"}
CODEXSCIENTIST_RESUME = {**CS_RESUME_QUEST, "name": "codexscientist_resume"}

NATIVE_SCHEMAS = [
    CS_DOCTOR, CS_LIST_QUESTS, CS_GET_QUEST_STATE, CS_SET_ACTIVE_QUEST, CS_NEW_QUEST, CS_UPDATE_QUEST_MODE,
    CS_ADD_USER_MESSAGE, CS_RECORD_USER_REQUIREMENT, CS_EVENTS, CS_READ_QUEST_DOCUMENTS, CS_MEMORY_SEARCH, CS_MEMORY_READ,
    CS_MEMORY_LIST_RECENT,
    CS_MEMORY_WRITE, CS_ARTIFACT_RECORD, CS_CONFIRM_BASELINE, CS_WAIVE_BASELINE,
    CS_ATTACH_BASELINE, CS_CREATE_LOCAL_BASELINE, CS_SUBMIT_IDEA, CS_LIST_RESEARCH_BRANCHES,
    CS_RESOLVE_RUNTIME_REFS, CS_GET_PAPER_CONTRACT_HEALTH, CS_GET_GLOBAL_STATUS,
    CS_GET_METHOD_SCOREBOARD, CS_GET_OPTIMIZATION_FRONTIER, CS_GET_CONVERSATION_CONTEXT,
    CS_RECORD_MAIN_EXPERIMENT,
    CS_CREATE_ANALYSIS_CAMPAIGN, CS_GET_ANALYSIS_CAMPAIGN, CS_RECORD_ANALYSIS_SLICE, CS_SUBMIT_PAPER_OUTLINE,
    CS_LIST_PAPER_OUTLINES, CS_SUBMIT_PAPER_BUNDLE, CS_REFRESH_SUMMARY, CS_ARXIV,
    CS_ENVIRONMENT_REGISTER, CS_ENVIRONMENT_VALIDATE, CS_ENVIRONMENT_SHOW, CS_FEEDBACK_INGEST,
    CS_TRAJECTORY_RECORD, CS_TRAJECTORY_SEARCH, CS_TRAJECTORY_SHOW, CS_EVOLUTIONARY_PLAN_ROUND,
    CS_VARIANT_CREATE, CS_VARIANT_APPLY_PATCH, CS_VARIANT_CHECK, CS_VARIANT_PACK,
    CS_SCHEDULER_SUBMIT, CS_SCHEDULER_STATUS, CS_WORKER_CLAIM, CS_WORKER_HEARTBEAT, CS_WORKER_COLLECT, CS_WORKER_UPLOAD_ARTIFACT, CS_EVOLUTIONARY_ROUND_SUBMIT,
    CS_IMPLEMENTER_PATCH_CHECK, CS_IMPLEMENTER_REPAIR_PATCH,
    CS_BASH_EXEC, CS_WORKFLOW_SMOKE_REPORT,
    CS_STRICT_RESEARCH_PREPARE, CS_STRICT_RESEARCH_RECORD_CANDIDATE, CS_STRICT_RESEARCH_UPSERT_CANDIDATE,
    CS_PAPER_FETCH, CS_RECORD_LITERATURE_READING_NOTE, CS_STRICT_RESEARCH_INIT_BIBLIOGRAPHY, CS_PAPER_RELIABILITY_VERIFY,
    CS_PAUSE_QUEST, CS_RESUME_QUEST, CS_STOP_QUEST,
]
LEGACY_ONLY_SCHEMAS = [CS_LIST_QUESTS, CS_GET_QUEST_STATE, CS_SET_ACTIVE_QUEST, CS_NEW_QUEST, CS_UPDATE_QUEST_MODE]
LEGACY_ONLY_SCHEMA_NAMES = {schema["name"] for schema in LEGACY_ONLY_SCHEMAS}


def _root_bound_public_schema(schema: dict[str, Any]) -> dict[str, Any]:
    current = dict(schema)
    input_schema = dict(current.get("input_schema") or {})
    properties = dict(input_schema.get("properties") or {})
    if "quest_id" in properties:
        quest_prop = dict(properties["quest_id"])
        quest_prop["description"] = S["quest_id"]["description"]
        properties["quest_id"] = quest_prop
    input_schema["properties"] = properties
    input_schema["required"] = [key for key in input_schema.get("required") or [] if key != "quest_id"]
    current["input_schema"] = input_schema
    return current
ALIAS_SCHEMAS = [
    CODEXSCIENTIST_DOCTOR, CODEXSCIENTIST_LIST_QUESTS, CODEXSCIENTIST_STATUS,
    CODEXSCIENTIST_NEW_QUEST, CODEXSCIENTIST_SEND_MESSAGE, CODEXSCIENTIST_EVENTS,
    CODEXSCIENTIST_READ_DOCUMENTS, CODEXSCIENTIST_MEMORY_SEARCH, CODEXSCIENTIST_MEMORY_WRITE,
    CODEXSCIENTIST_CONFIRM_BASELINE, CODEXSCIENTIST_SUBMIT_IDEA, CODEXSCIENTIST_RECORD_EXPERIMENT,
    CODEXSCIENTIST_SUBMIT_PAPER_BUNDLE, CODEXSCIENTIST_PAUSE, CODEXSCIENTIST_RESUME,
]
LEGACY_ALIAS_TO_CANONICAL = {
    "codexscientist_doctor": "cs_doctor",
    "codexscientist_list_quests": "cs_list_quests",
    "codexscientist_status": "cs_status",
    "codexscientist_new_quest": "cs_new_quest",
    "codexscientist_send_message": "cs_add_user_message",
    "codexscientist_events": "cs_events",
    "codexscientist_read_documents": "cs_read_quest_documents",
    "codexscientist_memory_search": "cs_memory_search",
    "codexscientist_memory_write": "cs_memory_write",
    "codexscientist_confirm_baseline": "cs_confirm_baseline",
    "codexscientist_submit_idea": "cs_submit_idea",
    "codexscientist_record_experiment": "cs_record_main_experiment",
    "codexscientist_submit_paper_bundle": "cs_submit_paper_bundle",
    "codexscientist_pause": "cs_pause_quest",
    "codexscientist_resume": "cs_resume_quest",
}
PUBLIC_SCHEMAS = [_root_bound_public_schema(schema) for schema in NATIVE_SCHEMAS if schema["name"] not in LEGACY_ONLY_SCHEMA_NAMES]
LEGACY_ALIAS_SCHEMAS = ALIAS_SCHEMAS
ALL_SCHEMAS = PUBLIC_SCHEMAS + LEGACY_ONLY_SCHEMAS + LEGACY_ALIAS_SCHEMAS
