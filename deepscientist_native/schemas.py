
"""JSON schemas for native DeepScientist Hermes tools."""
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
    "description": "DeepScientist memory kind. Canonical kinds are papers, ideas, decisions, episodes, knowledge, templates. Singular and semantic aliases such as constraint/context/observation/hypothesis/result/plan are accepted and normalized by the Hermes wrapper.",
}
PAPER_OUTLINE_MODE_FIELD = {
    "type": "string",
    "enum": ["candidate", "select", "revise", "selected"],
    "description": "Paper outline operation. Use candidate, then select, or revise. selected is accepted as a friendly alias for select.",
}

S = {
    "quest_id": {"type": "string", "description": "DeepScientist quest id. Omit to use active quest when supported."},
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
    "command": {"type": "string"},
}

DS_DOCTOR = _schema("ds_doctor", "Run native DeepScientist plugin diagnostics without invoking external ds.")
DS_LIST_QUESTS = _schema("ds_list_quests", "List DeepScientist quests from the native runtime home.", {"limit": S["limit"]})
DS_GET_QUEST_STATE = _schema("ds_get_quest_state", "Read compact or full state for a DeepScientist quest.", {"quest_id": S["quest_id"], "full": {"type": "boolean", "default": False}})
DS_SET_ACTIVE_QUEST = _schema("ds_set_active_quest", "Set the active quest for the current Hermes session.", {"quest_id": S["quest_id"], "session_id": {"type": "string"}, "stage": S["stage"]}, ["quest_id"])
DS_NEW_QUEST = _schema(
    "ds_new_quest",
    "Create a new DeepScientist quest natively. This tool is agent-managed: default to copilot unless the Hermes agent explicitly chooses autonomous and supplies the final-goal contract.",
    {
        "goal": S["goal"],
        "quest_id": S["quest_id"],
        "title": S["title"],
        "session_id": {"type": "string"},
        "workspace_mode": {"type": "string", "enum": ["copilot", "autonomous"], "description": "Agent-chosen mode. Omit for safe default copilot; pass autonomous only when Hermes should own multi-step progress."},
        "decision_policy": {"type": "string", "enum": ["user_gated", "autonomous"], "description": "Agent-chosen decision policy. Defaults to user_gated for copilot and autonomous for autonomous."},
        "need_research_paper": {"type": "boolean", "default": False, "description": "Whether paper-like output is a default terminal goal. Defaults false unless the agent explicitly chooses a paper goal."},
        "final_goal": {"type": "string", "enum": ["paper", "quality_result", "idea_optimization", "literature_scout", "baseline_reproduction", "analysis_report", "open_ended"], "description": "Agent-defined terminal objective, separate from workspace_mode."},
        "delivery_mode": {"type": "string", "description": "Short agent-defined delivery label such as idea_quality, literature_map, quality_result, or paper_bundle."},
        "completion_criteria": {"type": "array", "items": {"type": "string"}, "description": "Concrete criteria the agent will use to decide that the autonomous task is sufficiently complete."},
        "mode_rationale": {"type": "string", "description": "Short explanation of why Hermes selected the mode and final-goal contract."},
        "startup_contract": {"type": "object", "description": "Optional advanced contract fields; explicit values override generated defaults."},
    },
    ["goal"],
)
DS_UPDATE_QUEST_MODE = _schema(
    "ds_update_quest_mode",
    "Switch an existing DeepScientist quest between copilot and autonomous without creating or changing the quest. Use when the same research project moves from user-gated planning to autonomous execution, or back to copilot review.",
    {
        "quest_id": S["quest_id"],
        "workspace_mode": {"type": "string", "enum": ["copilot", "autonomous"], "description": "Agent-chosen mode for this existing quest."},
        "decision_policy": {"type": "string", "enum": ["user_gated", "autonomous"], "description": "Defaults to user_gated for copilot and autonomous for autonomous."},
        "need_research_paper": {"type": "boolean", "description": "Whether this mode switch makes a paper bundle the terminal goal. Do not infer this from autonomous alone."},
        "final_goal": {"type": "string", "enum": ["paper", "quality_result", "idea_optimization", "literature_scout", "baseline_reproduction", "analysis_report", "open_ended"], "description": "Terminal objective for the next phase, separate from workspace_mode."},
        "delivery_mode": {"type": "string", "description": "Delivery label for the next phase, such as experiment_execution, quality_result, analysis_report, or paper_bundle."},
        "completion_criteria": {"type": "array", "items": {"type": "string"}, "description": "Concrete criteria for determining the autonomous phase is complete."},
        "mode_rationale": {"type": "string", "description": "Required when switching to autonomous; short explanation of why Hermes should own progress in the same quest."},
        "startup_contract": {"type": "object", "description": "Optional advanced contract fields to merge into the existing quest startup contract."},
    },
    ["quest_id", "workspace_mode"],
)
DS_ADD_USER_MESSAGE = _schema("ds_add_user_message", "Append a user message/instruction to a quest conversation. Set record_only=true for durable requirements that must not be queued as pending user input.", {"quest_id": S["quest_id"], "message": S["message"], "source": {"type": "string"}, "stage": S["stage"], "record_only": {"type": "boolean", "default": False}, "delivery_state": {"type": "string", "enum": ["sent", "record_only"]}}, ["message"])
DS_RECORD_USER_REQUIREMENT = _schema("ds_record_user_requirement", "Record a durable user requirement in the quest conversation and active-user-requirements memory without leaving a pending user-message queue item.", {"quest_id": S["quest_id"], "message": S["message"], "source": {"type": "string"}, "stage": S["stage"]}, ["message"])
DS_EVENTS = _schema("ds_events", "Read quest events directly from native quest files.", {"quest_id": S["quest_id"], "limit": S["limit"]}, ["quest_id"])
DS_READ_QUEST_DOCUMENTS = _schema("ds_read_quest_documents", "List or read quest documents and skill docs.", {"quest_id": S["quest_id"], "names": {"type": "array", "items": {"type": "string"}}, "include_content": {"type": "boolean", "default": True}, "max_chars": {"type": "integer", "default": 12000}})
DS_MEMORY_SEARCH = _schema("ds_memory_search", "Search DeepScientist global/quest memory cards.", {"query": S["query"], "quest_id": S["quest_id"], "scope": S["scope"], "kind": MEMORY_KIND_FIELD, "limit": S["limit"]}, ["query"])
DS_MEMORY_READ = _schema("ds_memory_read", "Read a DeepScientist memory card by id or path.", {"card_id": {"type": "string"}, "path": S["path"], "quest_id": S["quest_id"], "scope": S["scope"]})
DS_MEMORY_LIST_RECENT = _schema("ds_memory_list_recent", "List the most recently updated DeepScientist memory cards, matching the original memory.list_recent MCP capability through Codex-native transport.", {"quest_id": S["quest_id"], "scope": S["scope"], "kind": MEMORY_KIND_FIELD, "limit": S["limit"]})
DS_MEMORY_WRITE = _schema("ds_memory_write", "Write a DeepScientist memory card. Semantic kind aliases such as constraint/context/observation/hypothesis/result/plan are normalized to knowledge with tags/metadata.", {"title": S["title"], "content": S["content"], "body": S["body"], "markdown": {"type": "string"}, "quest_id": S["quest_id"], "scope": S["scope"], "kind": MEMORY_KIND_FIELD, "tags": {"type": "array", "items": {"type": "string"}}, "metadata": {"type": "object"}}, ["title"])
DS_ARTIFACT_RECORD = _schema("ds_artifact_record", "Record a generic DeepScientist artifact in a quest.", {"quest_id": S["quest_id"], "payload": S["payload"], "kind": S["kind"], "summary": {"type": "string"}, "status": {"type": "string"}, "checkpoint": {"type": "boolean"}}, ["quest_id"])
DS_CONFIRM_BASELINE = _schema("ds_confirm_baseline", "Confirm a baseline gate using native artifact service.", {"quest_id": S["quest_id"], "baseline_path": S["path"], "baseline_id": {"type": "string"}, "variant_id": {"type": "string"}, "summary": {"type": "string"}, "comment": {}, "metric_contract": {"type": "object"}}, ["quest_id", "baseline_path"])
DS_WAIVE_BASELINE = _schema("ds_waive_baseline", "Explicitly waive the baseline gate.", {"quest_id": S["quest_id"], "reason": {"type": "string"}, "comment": {}}, ["quest_id", "reason"])
DS_ATTACH_BASELINE = _schema("ds_attach_baseline", "Attach a registered/imported baseline to the quest workspace.", {"quest_id": S["quest_id"], "baseline_id": {"type": "string"}, "variant_id": {"type": "string"}}, ["quest_id", "baseline_id"])
DS_CREATE_LOCAL_BASELINE = _schema("ds_create_local_baseline", "Create a canonical local baseline stub under baselines/local/<baseline_id>/ and return confirm_args for ds_confirm_baseline.", {"quest_id": S["quest_id"], "baseline_id": {"type": "string"}, "title": S["title"], "summary": {"type": "string"}, "content": S["content"], "source_path": S["path"], "filename": {"type": "string", "default": "baseline.md"}, "variant_id": {"type": "string"}, "metric_contract": {"type": "object"}, "overwrite": {"type": "boolean", "default": False}}, ["quest_id", "baseline_id"])
DS_SUBMIT_IDEA = _schema("ds_submit_idea", "Submit or revise a DeepScientist idea line/candidate.", {"quest_id": S["quest_id"], "title": S["title"], "problem": {"type": "string"}, "hypothesis": {"type": "string"}, "mechanism": {"type": "string"}, "method_brief": {"type": "string"}, "expected_gain": {"type": "string"}, "risks": {"type": "array"}, "decision_reason": {"type": "string"}, "next_target": {"type": "string"}}, ["quest_id", "title"])
DS_LIST_RESEARCH_BRANCHES = _schema("ds_list_research_branches", "List quest research branches/worktrees.", {"quest_id": S["quest_id"]}, ["quest_id"])
DS_RESOLVE_RUNTIME_REFS = _schema("ds_resolve_runtime_refs", "Resolve canonical DeepScientist research ids and runtime refs, matching the original artifact.resolve_runtime_refs MCP capability through Codex-native transport.", {"quest_id": S["quest_id"]})
DS_GET_PAPER_CONTRACT_HEALTH = _schema("ds_get_paper_contract_health", "Inspect whether the active paper line is unblocked for writing/finalize work, matching original artifact.get_paper_contract_health.", {"quest_id": S["quest_id"], "detail": {"type": "string", "enum": ["summary", "full"], "default": "summary"}})
DS_GET_GLOBAL_STATUS = _schema("ds_get_global_status", "Read a concise quest-global status summary, matching original artifact.get_global_status.", {"quest_id": S["quest_id"], "detail": {"type": "string", "enum": ["brief", "full"], "default": "brief"}, "locale": {"type": "string", "default": "zh"}})
DS_GET_METHOD_SCOREBOARD = _schema("ds_get_method_scoreboard", "Read or refresh the quest-level method scoreboard, matching original artifact.get_method_scoreboard.", {"quest_id": S["quest_id"]})
DS_GET_OPTIMIZATION_FRONTIER = _schema("ds_get_optimization_frontier", "Read a compact optimization-frontier summary for algorithm-first quests, matching original artifact.get_optimization_frontier.", {"quest_id": S["quest_id"]})
DS_GET_CONVERSATION_CONTEXT = _schema("ds_get_conversation_context", "Read a recent window of quest conversation history, matching original artifact.get_conversation_context.", {"quest_id": S["quest_id"], "limit": S["limit"], "include_attachments": {"type": "boolean", "default": False}})
DS_RECORD_MAIN_EXPERIMENT = _schema("ds_record_main_experiment", "Record a main experiment run.", {"quest_id": S["quest_id"], "run_id": {"type": "string"}, "title": S["title"], "hypothesis": {"type": "string"}, "setup": {"type": "string"}, "execution": {"type": "string"}, "results": {"type": "string"}, "conclusion": {"type": "string"}, "metric_rows": {"type": "array"}, "metrics_summary": {"type": "object"}, "evidence_paths": {"type": "array"}, "verdict": {"type": "string"}}, ["quest_id", "run_id"])
DS_CREATE_ANALYSIS_CAMPAIGN = _schema("ds_create_analysis_campaign", "Create an analysis campaign.", {"quest_id": S["quest_id"], "campaign_title": S["title"], "campaign_goal": {"type": "string"}, "slices": {"type": "array"}}, ["quest_id", "campaign_title", "campaign_goal", "slices"])
DS_GET_ANALYSIS_CAMPAIGN = _schema("ds_get_analysis_campaign", "Read the active or specified analysis campaign, including pending slice diagnostics.", {"quest_id": S["quest_id"], "campaign_id": {"type": "string", "default": "active", "description": "Use active or omit to inspect the current active campaign."}}, ["quest_id"])
DS_RECORD_ANALYSIS_SLICE = _schema("ds_record_analysis_slice", "Record an analysis slice result.", {"quest_id": S["quest_id"], "campaign_id": {"type": "string"}, "slice_id": {"type": "string"}, "status": {"type": "string"}, "setup": {"type": "string"}, "execution": {"type": "string"}, "results": {"type": "string"}}, ["quest_id", "campaign_id", "slice_id"])
DS_SUBMIT_PAPER_OUTLINE = _schema("ds_submit_paper_outline", "Submit/select/revise a paper outline. selected is accepted as an alias for select.", {"quest_id": S["quest_id"], "mode": PAPER_OUTLINE_MODE_FIELD, "outline_id": {"type": "string"}, "title": S["title"], "note": {"type": "string"}, "story": {"type": "string"}, "ten_questions": {"type": "array"}, "detailed_outline": {"type": "object"}}, ["quest_id"])
DS_LIST_PAPER_OUTLINES = _schema("ds_list_paper_outlines", "List candidate/revised paper outlines and the selected outline reference, matching original artifact.list_paper_outlines.", {"quest_id": S["quest_id"]})
DS_SUBMIT_PAPER_BUNDLE = _schema("ds_submit_paper_bundle", "Submit a paper bundle manifest.", {"quest_id": S["quest_id"], "title": S["title"], "summary": {"type": "string"}, "outline_path": S["path"], "draft_path": S["path"], "writing_plan_path": S["path"], "references_path": S["path"], "claim_evidence_map_path": S["path"], "compile_report_path": S["path"], "pdf_path": S["path"], "latex_root_path": S["path"], "prepare_open_source": {"type": "boolean"}}, ["quest_id"])
DS_REFRESH_SUMMARY = _schema("ds_refresh_summary", "Refresh SUMMARY.md from recent artifact state, matching original artifact.refresh_summary.", {"quest_id": S["quest_id"], "reason": {"type": "string"}})
DS_ARXIV = _schema("ds_arxiv", "Interact with the quest-local arXiv library, matching original artifact.arxiv through Codex-native transport.", {"quest_id": S["quest_id"], "paper_id": {"type": "string"}, "mode": {"type": "string", "enum": ["read", "list"], "default": "read"}, "full_text": {"type": "boolean", "default": False}})
DS_BASH_EXEC = _schema("ds_bash_exec", "Run/list/read/wait/stop quest-local bash execution sessions natively. By default workdir is limited to the quest; set allow_project_root=true only for administrative project-plugin tasks that must run from <project>. Use summary_mode=true for compact provenance output.", {"quest_id": S["quest_id"], "command": S["command"], "operation": {"type": "string", "enum": ["run", "list", "status", "read", "wait", "stop"]}, "bash_id": {"type": "string"}, "workdir": {"type": "string"}, "allow_project_root": {"type": "boolean", "default": False}, "env": {"type": "object"}, "timeout_seconds": {"type": "integer"}, "wait": {"type": "boolean"}, "limit": S["limit"], "summary_mode": {"type": "boolean", "default": False}, "response_mode": {"type": "string", "enum": ["full", "summary", "compact"]}})
DS_WORKFLOW_SMOKE_REPORT = _schema("ds_workflow_smoke_report", "Return a lightweight Hermes-only DeepScientist full-workflow checklist and path readiness report without running training.", {"quest_id": S["quest_id"], "dataset_path": S["path"], "paper_path": S["path"], "report_dir": S["path"]})
DS_STRICT_RESEARCH_PREPARE = _schema("ds_strict_research_prepare", "Initialize strict literature research mode in the active quest: create reference/candidate_references.md and return conservative screening workflow guidance.", {"quest_id": S["quest_id"], "intent": {"type": "string"}, "target_count": {"type": "integer"}, "complexity": {"type": "string", "enum": ["small", "medium", "large", "survey"]}})
DS_STRICT_RESEARCH_RECORD_CANDIDATE = _schema("ds_strict_research_record_candidate", "Append a candidate paper to reference/candidate_references.md during broad scouting before deep reading.", {"quest_id": S["quest_id"], "title": S["title"], "doi": {"type": "string"}, "link": {"type": "string"}, "source": {"type": "string"}, "authors": {"type": "string"}, "year": {"type": "string"}, "note": {"type": "string"}, "status": {"type": "string"}}, ["title"])
DS_STRICT_RESEARCH_UPSERT_CANDIDATE = _schema("ds_strict_research_upsert_candidate", "Upsert or update a strict-research candidate row in reference/candidate_references.md by title, DOI, or link.", {"quest_id": S["quest_id"], "key": {"type": "string", "description": "Existing title/DOI/link to match. Omit when title/doi/link should be used directly."}, "key_field": {"type": "string", "enum": ["title", "doi", "link"]}, "title": S["title"], "doi": {"type": "string"}, "link": {"type": "string"}, "source": {"type": "string"}, "authors": {"type": "string"}, "year": {"type": "string"}, "note": {"type": "string"}, "status": {"type": "string"}, "evidence_card": {"type": "string"}, "reliability_card": {"type": "string"}, "retain_reject_reason": {"type": "string"}, "reason": {"type": "string"}})
DS_PAPER_FETCH = _schema("ds_paper_fetch", "Fetch an official paper PDF into reference/pdfs/ and record canonical_url, sha256, page_count, body_text_status, official_resource_status, and a quest-local ledger row.", {"quest_id": S["quest_id"], "title": S["title"], "url": {"type": "string"}, "pdf_url": {"type": "string"}, "arxiv_id": {"type": "string"}, "arxiv_url": {"type": "string"}, "openreview_id": {"type": "string"}, "pmlr_url": {"type": "string"}, "output_name": {"type": "string"}, "overwrite": {"type": "boolean", "default": False}})
DS_RECORD_LITERATURE_READING_NOTE = _schema("ds_record_literature_reading_note", "Record a strict-research reading note and optional bibliography updates for one retained paper.", {"quest_id": S["quest_id"], "paper_id": {"type": "string"}, "title": S["title"], "pdf_path": S["path"], "surfaces_read": {"type": "array", "items": {"type": "string"}}, "sections_read": {"type": "array", "items": {"type": "string"}}, "note": {"type": "string"}, "claim_routes": {"type": "array", "items": {"type": "string"}}, "status": {"type": "string"}, "bibliography_updates": {"type": "object", "description": "Optional keys: essential_reference_details, reference_list, priority_reference_materials."}})
DS_STRICT_RESEARCH_INIT_BIBLIOGRAPHY = _schema("ds_strict_research_init_bibliography", "Create reference/bibliography/ and the three strict-research bibliography working files after enough retained references exist.", {"quest_id": S["quest_id"], "overwrite": {"type": "boolean", "default": False}})
DS_PAPER_RELIABILITY_VERIFY = _schema("ds_paper_reliability_verify", "Run the bundled paper_reliability_verifier for one candidate and store the JSON evidence card under reference/reliability_cards/.", {"quest_id": S["quest_id"], "title": S["title"], "doi": {"type": "string"}, "year": {"type": "integer"}, "arxiv_url": {"type": "string"}, "accepted_venue": {"type": "string"}, "accepted_type": {"type": "string"}, "accepted_acronym": {"type": "string"}, "include_raw": {"type": "boolean", "default": False}, "output_name": {"type": "string"}, "response_mode": {"type": "string", "enum": ["full", "summary", "compact"], "default": "full"}})
DS_PAUSE_QUEST = _schema("ds_pause_quest", "Mark a quest paused.", {"quest_id": S["quest_id"]}, ["quest_id"])
DS_RESUME_QUEST = _schema("ds_resume_quest", "Mark a quest active/resumed.", {"quest_id": S["quest_id"]}, ["quest_id"])
DS_STOP_QUEST = _schema("ds_stop_quest", "Mark a quest stopped.", {"quest_id": S["quest_id"], "reason": {"type": "string"}}, ["quest_id"])

# Compatibility aliases for one transition cycle.
DEEPSCIENTIST_DOCTOR = {**DS_DOCTOR, "name": "deepscientist_doctor"}
DEEPSCIENTIST_LIST_QUESTS = {**DS_LIST_QUESTS, "name": "deepscientist_list_quests"}
DEEPSCIENTIST_STATUS = {**DS_GET_QUEST_STATE, "name": "deepscientist_status"}
DEEPSCIENTIST_NEW_QUEST = {**DS_NEW_QUEST, "name": "deepscientist_new_quest"}
DEEPSCIENTIST_SEND_MESSAGE = {**DS_ADD_USER_MESSAGE, "name": "deepscientist_send_message"}
DEEPSCIENTIST_EVENTS = {**DS_EVENTS, "name": "deepscientist_events"}
DEEPSCIENTIST_READ_DOCUMENTS = {**DS_READ_QUEST_DOCUMENTS, "name": "deepscientist_read_documents"}
DEEPSCIENTIST_MEMORY_SEARCH = {**DS_MEMORY_SEARCH, "name": "deepscientist_memory_search"}
DEEPSCIENTIST_MEMORY_WRITE = {**DS_MEMORY_WRITE, "name": "deepscientist_memory_write"}
DEEPSCIENTIST_CONFIRM_BASELINE = {**DS_CONFIRM_BASELINE, "name": "deepscientist_confirm_baseline"}
DEEPSCIENTIST_SUBMIT_IDEA = {**DS_SUBMIT_IDEA, "name": "deepscientist_submit_idea"}
DEEPSCIENTIST_RECORD_EXPERIMENT = {**DS_RECORD_MAIN_EXPERIMENT, "name": "deepscientist_record_experiment"}
DEEPSCIENTIST_SUBMIT_PAPER_BUNDLE = {**DS_SUBMIT_PAPER_BUNDLE, "name": "deepscientist_submit_paper_bundle"}
DEEPSCIENTIST_PAUSE = {**DS_PAUSE_QUEST, "name": "deepscientist_pause"}
DEEPSCIENTIST_RESUME = {**DS_RESUME_QUEST, "name": "deepscientist_resume"}

NATIVE_SCHEMAS = [
    DS_DOCTOR, DS_LIST_QUESTS, DS_GET_QUEST_STATE, DS_SET_ACTIVE_QUEST, DS_NEW_QUEST, DS_UPDATE_QUEST_MODE,
    DS_ADD_USER_MESSAGE, DS_RECORD_USER_REQUIREMENT, DS_EVENTS, DS_READ_QUEST_DOCUMENTS, DS_MEMORY_SEARCH, DS_MEMORY_READ,
    DS_MEMORY_LIST_RECENT,
    DS_MEMORY_WRITE, DS_ARTIFACT_RECORD, DS_CONFIRM_BASELINE, DS_WAIVE_BASELINE,
    DS_ATTACH_BASELINE, DS_CREATE_LOCAL_BASELINE, DS_SUBMIT_IDEA, DS_LIST_RESEARCH_BRANCHES,
    DS_RESOLVE_RUNTIME_REFS, DS_GET_PAPER_CONTRACT_HEALTH, DS_GET_GLOBAL_STATUS,
    DS_GET_METHOD_SCOREBOARD, DS_GET_OPTIMIZATION_FRONTIER, DS_GET_CONVERSATION_CONTEXT,
    DS_RECORD_MAIN_EXPERIMENT,
    DS_CREATE_ANALYSIS_CAMPAIGN, DS_GET_ANALYSIS_CAMPAIGN, DS_RECORD_ANALYSIS_SLICE, DS_SUBMIT_PAPER_OUTLINE,
    DS_LIST_PAPER_OUTLINES, DS_SUBMIT_PAPER_BUNDLE, DS_REFRESH_SUMMARY, DS_ARXIV,
    DS_BASH_EXEC, DS_WORKFLOW_SMOKE_REPORT,
    DS_STRICT_RESEARCH_PREPARE, DS_STRICT_RESEARCH_RECORD_CANDIDATE, DS_STRICT_RESEARCH_UPSERT_CANDIDATE,
    DS_PAPER_FETCH, DS_RECORD_LITERATURE_READING_NOTE, DS_STRICT_RESEARCH_INIT_BIBLIOGRAPHY, DS_PAPER_RELIABILITY_VERIFY,
    DS_PAUSE_QUEST, DS_RESUME_QUEST, DS_STOP_QUEST,
]
ALIAS_SCHEMAS = [
    DEEPSCIENTIST_DOCTOR, DEEPSCIENTIST_LIST_QUESTS, DEEPSCIENTIST_STATUS,
    DEEPSCIENTIST_NEW_QUEST, DEEPSCIENTIST_SEND_MESSAGE, DEEPSCIENTIST_EVENTS,
    DEEPSCIENTIST_READ_DOCUMENTS, DEEPSCIENTIST_MEMORY_SEARCH, DEEPSCIENTIST_MEMORY_WRITE,
    DEEPSCIENTIST_CONFIRM_BASELINE, DEEPSCIENTIST_SUBMIT_IDEA, DEEPSCIENTIST_RECORD_EXPERIMENT,
    DEEPSCIENTIST_SUBMIT_PAPER_BUNDLE, DEEPSCIENTIST_PAUSE, DEEPSCIENTIST_RESUME,
]
LEGACY_ALIAS_TO_CANONICAL = {
    "deepscientist_doctor": "ds_doctor",
    "deepscientist_list_quests": "ds_list_quests",
    "deepscientist_status": "ds_get_quest_state",
    "deepscientist_new_quest": "ds_new_quest",
    "deepscientist_send_message": "ds_add_user_message",
    "deepscientist_events": "ds_events",
    "deepscientist_read_documents": "ds_read_quest_documents",
    "deepscientist_memory_search": "ds_memory_search",
    "deepscientist_memory_write": "ds_memory_write",
    "deepscientist_confirm_baseline": "ds_confirm_baseline",
    "deepscientist_submit_idea": "ds_submit_idea",
    "deepscientist_record_experiment": "ds_record_main_experiment",
    "deepscientist_submit_paper_bundle": "ds_submit_paper_bundle",
    "deepscientist_pause": "ds_pause_quest",
    "deepscientist_resume": "ds_resume_quest",
}
PUBLIC_SCHEMAS = NATIVE_SCHEMAS
LEGACY_ALIAS_SCHEMAS = ALIAS_SCHEMAS
ALL_SCHEMAS = PUBLIC_SCHEMAS + LEGACY_ALIAS_SCHEMAS
