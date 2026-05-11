from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .event_store import EventStore
from .manifest import ManifestService
from .metric import validate_metric_result
from .project_state import ProjectLayout

TERMINAL_FAILURES = {
    "failed_metric",
    "failed_artifact",
    "failed_readonly",
    "failed_oom",
    "failed_timeout",
    "failed_transient",
    "failed_other",
    "cancelled",
}

ALLOWED_TRANSITIONS = {
    "proposed": {"planned"},
    "planned": {"ready"},
    "ready": {"running"},
    "running": {"collecting", *TERMINAL_FAILURES},
    "collecting": {"evaluated", "failed_metric", "failed_artifact", "failed_other"},
    "evaluated": {"kept", "reverted", *TERMINAL_FAILURES},
}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class TrialService:
    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)
        self.trials_dir = layout.state_root / "trials"

    def _next_trial_id(self) -> str:
        self.trials_dir.mkdir(parents=True, exist_ok=True)
        existing = [path.name for path in self.trials_dir.glob("T[0-9][0-9][0-9][0-9]") if path.is_dir()]
        number = max([int(name[1:]) for name in existing] or [0]) + 1
        return f"T{number:04d}"

    def _trial_path(self, trial_id: str) -> Path:
        return self.trials_dir / trial_id / "trial.json"

    def _write(self, trial: dict[str, Any]) -> None:
        path = self._trial_path(trial["trial_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(json.dumps(trial, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    def get(self, trial_id: str) -> dict[str, Any]:
        path = self._trial_path(trial_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def propose(self, *, quest_id: str, idea_id: str, hypothesis: str, mechanism: str) -> dict[str, Any]:
        now = _utc_now()
        trial = {
            "trial_id": self._next_trial_id(),
            "quest_id": quest_id,
            "parent_node_id": None,
            "idea_id": idea_id,
            "status": "proposed",
            "created_at": now,
            "updated_at": now,
            "hypothesis": hypothesis,
            "mechanism": mechanism,
            "novelty_check": {"decision": "pending", "similar_failed_ideas": [], "similar_papers": []},
            "metric_contract_id": None,
            "budget": {},
            "editable_paths": [],
            "readonly_paths": [],
            "git_checkpoint": {},
            "commands": [],
            "run_ids": [],
            "metrics": {},
            "artifacts": [],
            "failure_reason": None,
            "decision": "pending",
        }
        self._write(trial)
        self.events.append("trial.proposed", {"trial_id": trial["trial_id"], "quest_id": quest_id})
        return trial

    def transition(self, trial_id: str, new_status: str) -> dict[str, Any]:
        trial = self.get(trial_id)
        old_status = trial["status"]
        if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
            return {
                "ok": False,
                "error": f"Invalid transition: {old_status} -> {new_status}",
                "error_type": "invalid_transition",
                "recoverable": True,
                "trial": trial,
            }
        trial["status"] = new_status
        trial["updated_at"] = _utc_now()
        self._write(trial)
        self.events.append("trial.transitioned", {"trial_id": trial_id, "from": old_status, "to": new_status})
        return {"ok": True, "trial": trial}

    def plan(self, trial_id: str, *, metric_contract_id: str, novelty_decision: str) -> dict[str, Any]:
        trial = self.get(trial_id)
        if trial["status"] != "proposed":
            return self.transition(trial_id, "planned")
        trial["metric_contract_id"] = metric_contract_id
        trial["novelty_check"] = {"decision": novelty_decision, "similar_failed_ideas": [], "similar_papers": []}
        trial["updated_at"] = _utc_now()
        self._write(trial)
        return self.transition(trial_id, "planned")

    def ready(self, trial_id: str) -> dict[str, Any]:
        manifest_service = ManifestService(self.layout)
        validation = manifest_service.validate()
        trial = self.get(trial_id)
        if not validation.get("ok", False):
            return {"ok": False, "error": "Manifest validation failed", "error_type": "manifest_invalid", "recoverable": True, "trial": trial, "errors": validation.get("errors", [])}
        if not validation.get("baseline_ready", False):
            return {"ok": False, "error": "Confirmed baseline or waiver required", "error_type": "baseline_required", "recoverable": True, "trial": trial}
        return self.transition(trial_id, "ready")

    def _set_terminal_failure(self, trial: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
        trial["status"] = status
        trial["failure_reason"] = reason
        trial["updated_at"] = _utc_now()
        self._write(trial)
        self.events.append("trial.failed", {"trial_id": trial["trial_id"], "status": status, "reason": reason})
        return {"ok": False, "error": reason, "error_type": status, "recoverable": False, "trial": trial}

    def evaluate(self, trial_id: str, *, metric_values: dict[str, float], artifacts: list[str]) -> dict[str, Any]:
        trial = self.get(trial_id)
        if trial.get("status") not in {"ready", "running", "collecting"}:
            return {"ok": False, "error": "Trial is not ready for evaluation", "error_type": "invalid_transition", "recoverable": True, "trial": trial}
        manifest = ManifestService(self.layout).read()
        metrics = manifest.get("metrics") if isinstance(manifest.get("metrics"), dict) else {}
        primary = metrics.get("primary") if isinstance(metrics, dict) else None
        if not isinstance(primary, dict):
            return self._set_terminal_failure(trial, "failed_metric", "Missing primary metric contract")
        metric_id = primary.get("id", "primary")
        if metric_id not in metric_values:
            return self._set_terminal_failure(trial, "failed_metric", f"Missing metric value: {metric_id}")
        metric_result = validate_metric_result(primary, value=metric_values[metric_id], artifacts=artifacts)
        if not metric_result.get("ok", False):
            error_type = metric_result.get("error_type")
            status = "failed_artifact" if error_type == "missing_metric_artifact" else "failed_metric"
            return self._set_terminal_failure(trial, status, str(metric_result.get("error")))
        trial["metrics"] = dict(metric_values)
        trial["artifacts"] = list(artifacts)
        trial["status"] = "evaluated"
        trial["updated_at"] = _utc_now()
        self._write(trial)
        self.events.append("trial.evaluated", {"trial_id": trial_id, "metrics": metric_values, "artifacts": artifacts})
        return {"ok": True, "trial": trial}

    def decide(self, trial_id: str, *, decision: str, reviewer_verdict: str | None = None) -> dict[str, Any]:
        trial = self.get(trial_id)
        if trial.get("status") in TERMINAL_FAILURES:
            return {"ok": False, "error": "Cannot keep failed trial", "error_type": "cannot_keep_failed_trial", "recoverable": False, "trial": trial}
        if decision == "keep" and (trial.get("status") != "evaluated" or reviewer_verdict != "pass"):
            return {"ok": False, "error": "Keep requires evaluated trial and passing review", "error_type": "keep_gate_failed", "recoverable": True, "trial": trial}
        trial["decision"] = decision
        trial["reviewer_verdict"] = reviewer_verdict
        trial["status"] = "kept" if decision == "keep" else "reverted"
        trial["updated_at"] = _utc_now()
        self._write(trial)
        self.events.append("trial.decided", {"trial_id": trial_id, "decision": decision, "reviewer_verdict": reviewer_verdict})
        return {"ok": True, "trial": trial}
