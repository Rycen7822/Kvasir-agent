from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .environment import EnvironmentService
from .event_store import EventStore, utc_now
from .journal import JournalService
from .project_state import ProjectLayout, _safe_segment
from .trajectory import TrajectoryStore

_EXPLORATION_FAMILIES = (
    "adapter",
    "optimizer",
    "regularization",
    "data_curriculum",
    "architecture",
    "loss_shaping",
)


def _error(error_type: str, message: str, *, recoverable: bool = True, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "error_type": error_type, "error": message, "recoverable": recoverable}
    payload.update(extra)
    return payload


class EvolutionarySearchService:
    """Plan-only evolutionary search support for execution-grounded variants.

    This service intentionally does not create variants, queue jobs, run commands, or submit work. It reads already-evaluated trajectories and environment metadata, then writes a deterministic round plan artifact that later gated executor tools may consume.
    """

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.events = EventStore(layout)

    def plan_round(self, *, quest_id: str, env_id: str, epoch: int = 0, batch_size: int = 4) -> dict[str, Any]:
        try:
            safe_quest_id = _safe_segment(quest_id, label="quest_id")
            safe_env_id = _safe_segment(env_id, label="env_id")
        except ValueError as exc:
            return _error("invalid_path", str(exc), recoverable=False)
        safe_batch_size = max(1, min(int(batch_size or 1), 32))
        safe_epoch = max(0, int(epoch or 0))

        environment_payload = EnvironmentService(self.layout).show(quest_id=safe_quest_id, env_id=safe_env_id)
        if environment_payload.get("ok") is not True:
            return environment_payload
        environment = environment_payload["environment"]
        baseline_metric = ((environment.get("baseline") or {}).get("baseline_metric") or {}) if isinstance(environment.get("baseline"), dict) else {}
        primary_metric = environment.get("primary_metric") if isinstance(environment.get("primary_metric"), dict) else {}
        direction = str(primary_metric.get("direction") or baseline_metric.get("direction") or "maximize")
        baseline_value = baseline_metric.get("value")

        trajectories_payload = TrajectoryStore(self.layout).search(quest_id=safe_quest_id, env_id=safe_env_id, status="evaluated", limit=100)
        if trajectories_payload.get("ok") is not True:
            return trajectories_payload
        records = list(trajectories_payload.get("trajectories") or [])
        exploit_parents, negative_signals = self._select_exploit_parents(records=records, baseline_value=baseline_value, direction=direction)
        risk_flags, blocked_families = self._negative_memory_risks(quest_id=safe_quest_id)
        candidates = self._candidate_batch(exploit_parents=exploit_parents, blocked_families=blocked_families, batch_size=safe_batch_size, epoch=safe_epoch)
        family_counts = Counter(str(item.get("mechanism_family") or "unknown") for item in candidates)
        max_fraction = round((max(family_counts.values()) / len(candidates)) if candidates else 0.0, 4)

        round_id = f"round_{safe_epoch:04d}"
        created_at = utc_now()
        plan = {
            "schema_version": 1,
            "round_id": round_id,
            "quest_id": safe_quest_id,
            "env_id": safe_env_id,
            "epoch": safe_epoch,
            "batch_size": safe_batch_size,
            "status": "planned",
            "submit_allowed": False,
            "approval_required": True,
            "executor_side_effects": False,
            "metric_direction": direction,
            "baseline_value": baseline_value,
            "exploit_parents": exploit_parents,
            "candidates": candidates,
            "negative_signals": sorted(set(negative_signals)),
            "risk_flags": risk_flags,
            "diversity": {
                "mechanism_family_counts": dict(sorted(family_counts.items())),
                "max_same_mechanism_family_fraction": max_fraction,
                "max_per_family": self._max_per_family(safe_batch_size),
            },
            "created_at": created_at,
            "updated_at": created_at,
        }
        path = self._round_plan_path(quest_id=safe_quest_id, round_id=round_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
        self.events.append(
            "evolutionary.round_planned",
            {"quest_id": safe_quest_id, "env_id": safe_env_id, "round_id": round_id, "candidate_count": len(candidates)},
            idempotency_key=f"evolutionary.round_planned:{safe_quest_id}:{safe_env_id}:{round_id}",
        )
        return {"ok": True, "round_plan": plan, "round_id": round_id, "path": str(path)}

    def submit_round(
        self,
        *,
        quest_id: str,
        env_id: str,
        round_id: str,
        submissions: list[dict[str, Any]],
        approval: dict[str, Any] | None = None,
        backend: str = "local",
    ) -> dict[str, Any]:
        try:
            safe_quest_id = _safe_segment(quest_id, label="quest_id")
            safe_env_id = _safe_segment(env_id, label="env_id")
            safe_round_id = _safe_segment(round_id, label="round_id")
        except ValueError as exc:
            return _error("invalid_path", str(exc), recoverable=False)
        plan_payload = self.show_round_plan(quest_id=safe_quest_id, round_id=safe_round_id)
        if plan_payload.get("ok") is not True:
            return plan_payload
        plan = plan_payload["round_plan"]
        if str(plan.get("env_id") or "") != safe_env_id:
            return _error("round_env_mismatch", "Round plan env_id does not match submit request.", env_id=safe_env_id, round_env_id=plan.get("env_id"))
        if str(plan.get("status") or "") == "submitted":
            return _error("round_already_submitted", "Evolutionary round has already been submitted.", recoverable=False, submitted_job_ids=plan.get("submitted_job_ids") or [])
        approval_check = self._round_approval(plan=plan, approval=approval or {})
        if approval_check.get("ok") is not True:
            return approval_check
        if not isinstance(submissions, list) or not submissions:
            return _error("missing_argument", "round submit requires at least one submission", recoverable=True)
        candidate_ids = {str(candidate.get("candidate_id") or "") for candidate in (plan.get("candidates") or []) if isinstance(candidate, dict)}
        from .scheduler import SchedulerService

        scheduler = SchedulerService(self.layout)
        validated_submissions: list[dict[str, Any]] = []
        for index, submission in enumerate(submissions, start=1):
            if not isinstance(submission, dict):
                return _error("invalid_schema", f"submission #{index} must be an object", recoverable=True)
            candidate_id = str(submission.get("candidate_id") or "").strip()
            if candidate_id not in candidate_ids:
                return _error("unknown_candidate", f"Submission candidate_id is not in round plan: {candidate_id}", candidate_id=candidate_id)
            missing = [key for key in ("variant_id", "trajectory_id", "package_path", "command") if not str(submission.get(key) or "").strip()]
            if missing:
                return _error("missing_argument", "round submission is missing required fields", recoverable=True, candidate_id=candidate_id, missing=missing)
            try:
                safe_variant_id = _safe_segment(str(submission["variant_id"]), label="variant_id")
            except ValueError as exc:
                return _error("invalid_path", str(exc), recoverable=False, candidate_id=candidate_id)
            backend_name = str(submission.get("backend") or backend or "local")
            validation = scheduler.validate_package(
                quest_id=safe_quest_id,
                env_id=safe_env_id,
                trajectory_id=str(submission["trajectory_id"]),
                variant_id=safe_variant_id,
                package_path=str(submission["package_path"]),
            )
            if validation.get("ok") is not True:
                validation["candidate_id"] = candidate_id
                validation["submission_index"] = index
                return validation
            validated_submissions.append({"candidate_id": candidate_id, "variant_id": safe_variant_id, "submission": submission, "backend": backend_name})

        job_ids: list[str] = []
        seen_candidate_ids: set[str] = set()
        seen_job_ids: set[str] = set()
        for item in validated_submissions:
            candidate_id = str(item["candidate_id"])
            submission = item["submission"]
            variant_id = str(item["variant_id"])
            job_id = f"job_{variant_id}"
            if candidate_id in seen_candidate_ids or job_id in seen_job_ids:
                return _error("duplicate_round_submission", "Round submit contains duplicate candidate or job ids.", recoverable=True, candidate_id=candidate_id, job_id=job_id)
            seen_candidate_ids.add(candidate_id)
            seen_job_ids.add(job_id)
            job_ids.append(job_id)
        from .queue import QueueService

        existing_jobs = QueueService(self.layout).status().get("jobs") or {}
        if isinstance(existing_jobs, dict):
            for job_id in job_ids:
                if job_id in existing_jobs:
                    return _error("round_job_exists", "Round submit refuses to overwrite an existing queue job.", recoverable=True, job_id=job_id)

        submitted_jobs: list[dict[str, Any]] = []
        for item in validated_submissions:
            submission = item["submission"]
            candidate_id = item["candidate_id"]
            submitted = scheduler.submit(
                quest_id=safe_quest_id,
                env_id=safe_env_id,
                trajectory_id=str(submission["trajectory_id"]),
                variant_id=str(item["variant_id"]),
                package_path=str(submission["package_path"]),
                backend=str(item["backend"]),
                command=str(submission["command"]),
                expected_outputs=[str(output) for output in (submission.get("expected_outputs") or [])],
                max_attempts=int(submission.get("max_attempts") or 1),
            )
            if submitted.get("ok") is not True:
                submitted["candidate_id"] = candidate_id
                return submitted
            submitted_jobs.append(submitted["job"])
        plan["status"] = "submitted"
        plan["submit_allowed"] = False
        plan["submitted_job_ids"] = [str(job.get("job_id")) for job in submitted_jobs]
        plan["updated_at"] = utc_now()
        path = self._round_plan_path(quest_id=safe_quest_id, round_id=safe_round_id)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
        self.events.append(
            "evolutionary.round_submitted",
            {"quest_id": safe_quest_id, "env_id": safe_env_id, "round_id": safe_round_id, "job_ids": plan["submitted_job_ids"]},
            idempotency_key=f"evolutionary.round_submitted:{safe_quest_id}:{safe_round_id}",
        )
        return {"ok": True, "quest_id": safe_quest_id, "env_id": safe_env_id, "round_id": safe_round_id, "submitted_jobs": submitted_jobs, "round_plan_path": str(path)}

    def show_round_plan(self, *, quest_id: str, round_id: str) -> dict[str, Any]:
        try:
            path = self._round_plan_path(quest_id=quest_id, round_id=round_id)
        except ValueError as exc:
            return _error("invalid_path", str(exc), recoverable=False)
        if not path.is_file():
            return _error("not_found", f"Round plan not found: {round_id}", recoverable=True)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            return _error("invalid_schema", "Round plan must be a JSON object", recoverable=True)
        return {"ok": True, "round_plan": loaded, "path": str(path)}

    def _round_approval(self, *, plan: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
        if plan.get("approval_required") is not True:
            return {"ok": True, "decision": "plan_allows_submit"}
        if approval.get("approved") is not True:
            return _error("approval_required", "Evolutionary round submit requires explicit approval for this plan.", recoverable=True)
        expires_raw = str(approval.get("budget_expires_at") or approval.get("expires_at") or "").strip()
        if not expires_raw:
            return _error("budget_decision_required", "Round approval requires non-expired budget_expires_at.", recoverable=True)
        try:
            expires_at = datetime.fromisoformat(expires_raw)
        except ValueError:
            return _error("invalid_approval", "budget_expires_at must be ISO-8601.", recoverable=True)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            return _error("budget_decision_expired", "Round approval budget decision is expired.", recoverable=True)
        return {"ok": True, "decision": "explicit_approval"}

    def _round_plan_path(self, *, quest_id: str, round_id: str) -> Path:
        return self.layout.state_root / "runtime" / "execution_grounded" / "evolutionary_rounds" / f"{_safe_segment(round_id, label='round_id')}.json"

    def _select_exploit_parents(self, *, records: list[dict[str, Any]], baseline_value: Any, direction: str) -> tuple[list[dict[str, Any]], list[str]]:
        selected: list[dict[str, Any]] = []
        negative_signals: list[str] = []
        for record in records:
            raw_patch = record.get("patch")
            patch = raw_patch if isinstance(raw_patch, dict) else {}
            if patch.get("protected_hashes_ok") is False:
                negative_signals.append("protected_hash_mismatch")
                continue
            raw_result = record.get("result")
            result = raw_result if isinstance(raw_result, dict) else {}
            if result.get("trusted_primary_metric") is not True and result.get("revalidated") is not True:
                negative_signals.append("metric_untrusted")
                continue
            raw_metric = result.get("primary_metric")
            metric = raw_metric if isinstance(raw_metric, dict) else {}
            if not self._is_improved(metric.get("value"), baseline_value, direction):
                negative_signals.append("no_improvement")
                continue
            raw_idea = record.get("idea")
            idea = raw_idea if isinstance(raw_idea, dict) else {}
            raw_lineage = record.get("lineage")
            lineage = raw_lineage if isinstance(raw_lineage, dict) else {}
            selected.append(
                {
                    "trajectory_id": str(record.get("trajectory_id") or ""),
                    "idea_id": str(idea.get("idea_id") or ""),
                    "mechanism_family": str(idea.get("mechanism_family") or lineage.get("mechanism_family") or "unknown"),
                    "primary_metric": metric,
                    "strategy": str(record.get("strategy") or "manual"),
                    "updated_at": str(record.get("updated_at") or ""),
                }
            )
        selected.sort(key=lambda item: self._metric_sort_key(item.get("primary_metric"), direction), reverse=(direction != "minimize"))
        return selected, negative_signals

    @staticmethod
    def _is_improved(metric_value: Any, baseline_value: Any, direction: str) -> bool:
        try:
            current = float(metric_value)
            baseline = float(baseline_value)
        except (TypeError, ValueError):
            return False
        return current < baseline if direction == "minimize" else current > baseline

    @staticmethod
    def _metric_sort_key(metric: Any, direction: str) -> float:
        if not isinstance(metric, dict):
            return float("inf") if direction == "minimize" else float("-inf")
        try:
            return float(metric["value"])
        except (TypeError, ValueError):
            return float("inf") if direction == "minimize" else float("-inf")

    def _negative_memory_risks(self, *, quest_id: str) -> tuple[list[dict[str, Any]], set[str]]:
        risks: list[dict[str, Any]] = []
        blocked: set[str] = set()
        for record in JournalService(self.layout).list_negative_memory(quest_id=quest_id):
            mechanism = str(record.get("mechanism") or record.get("lesson") or "").strip()
            if not mechanism:
                continue
            family = mechanism.casefold()
            blocked.add(family)
            risks.append(
                {
                    "risk": "duplicate_negative_memory",
                    "mechanism_family": mechanism,
                    "idea_id": str(record.get("idea_id") or ""),
                    "failure_reason": str(record.get("failure_reason") or ""),
                }
            )
        return risks, blocked

    def _candidate_batch(self, *, exploit_parents: list[dict[str, Any]], blocked_families: set[str], batch_size: int, epoch: int) -> list[dict[str, Any]]:
        max_per_family = self._max_per_family(batch_size)
        families: list[str] = []
        for parent in exploit_parents:
            family = str(parent.get("mechanism_family") or "unknown").strip() or "unknown"
            if family.casefold() not in blocked_families and family not in families:
                families.append(family)
        for family in _EXPLORATION_FAMILIES:
            if family.casefold() not in blocked_families and family not in families:
                families.append(family)
        if not families:
            families = ["exploration"]

        counts: Counter[str] = Counter()
        candidates: list[dict[str, Any]] = []
        cursor = 0
        while len(candidates) < batch_size and len(candidates) < max(1, len(families) * max_per_family):
            family = families[cursor % len(families)]
            cursor += 1
            if counts[family] >= max_per_family:
                if all(counts[item] >= max_per_family for item in families):
                    break
                continue
            counts[family] += 1
            parent = self._parent_for_family(exploit_parents, family)
            candidates.append(
                {
                    "candidate_id": f"cand_{epoch:04d}_{len(candidates) + 1:03d}",
                    "strategy": "exploit" if parent else "explore",
                    "mechanism_family": family,
                    "parent_trajectory_ids": [parent["trajectory_id"]] if parent else [],
                    "mutation_hint": self._mutation_hint(family=family, ordinal=counts[family]),
                    "executor_ready": False,
                }
            )
        return candidates

    @staticmethod
    def _max_per_family(batch_size: int) -> int:
        return max(1, int(max(1, batch_size) * 0.25))

    @staticmethod
    def _parent_for_family(parents: list[dict[str, Any]], family: str) -> dict[str, Any] | None:
        for parent in parents:
            if str(parent.get("mechanism_family") or "") == family:
                return parent
        return None

    @staticmethod
    def _mutation_hint(*, family: str, ordinal: int) -> str:
        return f"Propose a small local-only {family} variant #{ordinal}; preserve evaluator, dataset, and metric contracts."
