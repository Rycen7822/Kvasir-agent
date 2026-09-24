"""Five research operations over explicit project state and immutable requests."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

from .evidence_contracts import EvidenceError, read_json, validate_document
from .metric import extract_metric_value, validate_metric_result
from .research_state import ResearchState, alive, digest, file_hash, now, process_identity, within

TERMINAL = {"completed", "failed", "cancelled", "timed_out", "interrupted", "imported"}


class EvidenceService:
    def __init__(self, project):
        self.state = ResearchState(project)

    def document(self, path, kind):
        return validate_document(read_json(within(self.state.project, path, exists=True)), kind)

    def ready(self):
        m = self.state.read_manifest()
        if self.state.events()[1]:
            raise EvidenceError("corrupt_events", "Event journal contains invalid lines.")
        return m

    def validate_environment(self, env):
        validate_document(env, "environment")
        repo = within(self.state.project, env["baseline"]["repo_path"], exists=True)
        if not repo.is_dir():
            raise EvidenceError("invalid_baseline", "Baseline repository is not a directory.")
        commit = env["baseline"].get("commit")
        if commit:
            try:
                result = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                        capture_output=True, text=True, timeout=10)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise EvidenceError("baseline_unavailable", "Baseline commit could not be inspected.") from exc
            if result.returncode or result.stdout.strip() != commit:
                raise EvidenceError("baseline_mismatch", "Baseline commit does not match.")
        for item in env["protected_files"] + env["datasets"]:
            path = within(self.state.project, item["path"], exists=True)
            if not path.is_file() or file_hash(path) != item["sha256"]:
                raise EvidenceError("protected_hash_mismatch", "Protected input hash does not match.")
        return {"ok": True, "environment_digest": digest(env)}

    def receipt(self, record):
        run_id = record["run_id"]
        status = record["status"]
        if status not in TERMINAL and not alive(record.get("worker")):
            status = "interrupted"
        out = {"ok": True, "run_id": run_id, "status": status,
               "record_path": f"Kvasir-agent/runs/{run_id}/run.json",
               "evidence_status": record.get("evidence_status", "pending")}
        if record.get("metric") is not None:
            out["metric"] = record["metric"]
        if record.get("derivation_status") == "partial":
            out["derivation_status"] = "partial"
        return out

    def status(self, run_id=None):
        manifest = self.state.read_manifest()
        if run_id:
            return self.receipt(self.state.read_run(run_id))
        paths = sorted(self.state.path("runs").glob("*/run.json"))
        selected = paths[-5:]
        summaries = []
        for path in selected:
            try:
                summaries.append(self.receipt(self.state.read_run(path.parent.name)))
            except EvidenceError:
                summaries.append({"run_id": path.parent.name[:80], "status": "corrupt"})
        _, bad = self.state.events()
        return {"ok": True, "project_id": manifest["project_id"], "status": "ready",
                "manifest_path": str(self.state.manifest), "runs": summaries,
                "omitted_runs": max(0, len(paths) - len(selected)),
                "runs_path": str(self.state.path("runs")), "invalid_event_lines": bad[:5],
                "omitted_invalid_lines": max(0, len(bad) - 5)}

    def run(self, spec_path, idempotency_key):
        self.ready()
        spec = self.document(spec_path, "run")
        env = self.document(spec["environment_path"], "environment")
        request_digest = digest({"spec": spec, "environment": env})
        state = self.state
        with state.locked():
            self.ready()
            for path in state.path("runs").glob("*/run.json"):
                previous = state.read_run(path.parent.name)
                if previous.get("idempotency_key") == idempotency_key:
                    if previous.get("request_digest") != request_digest:
                        raise EvidenceError("idempotency_conflict", "Key already belongs to a different request.")
                    return self.receipt(previous)
            self.validate_environment(env)
            cwd = within(state.project, spec["cwd"], exists=True)
            if not cwd.is_dir():
                raise EvidenceError("invalid_path", "Run cwd is not a directory.")
            if spec["purpose"] == "experiment":
                baseline = state.read_run(spec["baseline_run_id"])
                if (baseline.get("spec", {}).get("purpose") != "baseline"
                        or baseline.get("environment_digest") != digest(env)
                        or self.run_issues(baseline)):
                    raise EvidenceError("invalid_baseline", "A matching verified baseline run is required.")
            run_id = "r_" + now().replace("-", "").replace(":", "").split(".")[0] + "_" + uuid4().hex[:12]
            run_dir = state.path(f"runs/{run_id}")
            for output in [spec["metrics_path"], *spec["outputs"]]:
                if Path(output).is_absolute() or output in {"run.json", "result.json", "stdout.log", "stderr.log", "worker.log"}:
                    raise EvidenceError("invalid_output", "Outputs must be relative run artifacts, not control files.")
                target = within(run_dir, output)
                if target == run_dir:
                    raise EvidenceError("invalid_output", "Output must name a file.")
            record = {"schema_version": 1, "run_id": run_id, "project_id": state.read_manifest()["project_id"],
                      "status": "starting", "created_at": now(), "idempotency_key": idempotency_key,
                      "spec": spec, "environment": env, "environment_digest": digest(env),
                      "request_digest": request_digest, "trust": "managed_local", "evidence_status": "pending"}
            state.write(f"environments/{digest(env)}.json", env)
            state.write(f"runs/{run_id}/run.json", record)
            state.event("run.prepared", {"run_id": run_id}, key=f"prepared:{run_id}")
            worker_script = Path(__file__).resolve().parents[2] / "scripts" / "ka_run_worker.py"
            try:
                with state.path(f"runs/{run_id}/worker.log").open("ab") as log:
                    worker = subprocess.Popen([sys.executable, str(worker_script), str(state.project), run_id],
                                              cwd=state.project, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                              start_new_session=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
                record["worker"] = process_identity(worker.pid)
            except OSError:
                record.update(status="failed", error_type="worker_start_failed", evidence_status="invalid", finished_at=now())
            state.write(f"runs/{run_id}/run.json", record)
        return self.receipt(record)

    def stop(self, run_id):
        self.ready()
        with self.state.locked():
            record = self.state.read_run(run_id)
            if record["status"] in TERMINAL:
                return self.receipt(record)
            record["cancel_requested_at"] = record.get("cancel_requested_at") or now()
            self.state.write(f"runs/{run_id}/run.json", record)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and alive(record.get("worker")):
            time.sleep(0.05)
            record = self.state.read_run(run_id)
            if record["status"] in TERMINAL:
                return self.receipt(record)
        if not alive(record.get("worker")):
            # A dead wrapper may have left its child alive. Only signal the
            # recorded instance, then persist an interruption, never success.
            from .evidence_runner import terminate
            terminate(record.get("process"))
            with self.state.locked():
                record = self.state.read_run(run_id)
                if record["status"] not in TERMINAL:
                    record.update(status="interrupted", evidence_status="invalid", finished_at=now())
                    self.state.write(f"runs/{run_id}/run.json", record)
        result = self.receipt(record)
        if result["status"] not in TERMINAL:
            result["status"] = "cancelling"
        return result

    def run_issues(self, record):
        issues = []
        if record.get("status") != "completed" or record.get("evidence_status") != "verified":
            issues.append("run_not_verified")
        if record.get("trust") != "managed_local":
            issues.append("unverified_origin")
        spec, env = record.get("spec"), record.get("environment")
        if not isinstance(spec, dict) or not isinstance(env, dict):
            return issues + ["missing_request_snapshot"]
        if digest({"spec": spec, "environment": env}) != record.get("request_digest"):
            issues.append("request_digest_mismatch")
        if digest(env) != record.get("environment_digest"):
            issues.append("environment_digest_mismatch")
        if spec.get("purpose") == "experiment":
            try:
                baseline = self.state.read_run(spec.get("baseline_run_id"))
                baseline_spec = baseline.get("spec")
                if (not isinstance(baseline_spec, dict) or baseline_spec.get("purpose") != "baseline"
                        or baseline.get("environment_digest") != record.get("environment_digest")
                        or self.run_issues(baseline)):
                    issues.append("baseline_evidence_invalid")
            except EvidenceError:
                issues.append("baseline_evidence_unavailable")
        if not record.get("artifacts"):
            issues.append("missing_artifacts")
        for artifact in record.get("artifacts", []):
            try:
                p = within(self.state.path(f"runs/{record['run_id']}"), artifact["path"], exists=True)
                if file_hash(p) != artifact["sha256"]:
                    issues.append("artifact_hash_mismatch")
            except (EvidenceError, OSError):
                issues.append("artifact_unavailable")
        return sorted(set(issues))

    def check(self, spec_path):
        self.ready()
        spec = self.document(spec_path, "check")
        issues, evidence = [], []
        if spec["target"] == "environment":
            env = self.document(spec["environment_path"], "environment")
            try:
                evidence.append(self.validate_environment(env))
            except EvidenceError as exc:
                issues.append(exc.kind)
        else:
            ids = spec.get("run_ids", [spec.get("run_id")])
            records = []
            for run_id in ids:
                try:
                    record = self.state.read_run(run_id)
                    records.append(record)
                    failures = self.run_issues(record)
                    issues.extend(f"{run_id}:{issue}" for issue in failures)
                    evidence.append({"run_id": run_id, "record_path": str(self.state.path(f"runs/{run_id}/run.json")), "issues": failures})
                except EvidenceError as exc:
                    issues.append(f"{run_id}:{exc.kind}")
            if spec["target"] == "claim" and records:
                seeds = {r.get("spec", {}).get("seed") for r in records if not self.run_issues(r)} - {None}
                if len(seeds) < spec["minimum_seeds"]:
                    issues.append("insufficient_observed_seeds")
                cohorts = {(r.get("environment_digest"), r.get("spec", {}).get("method_id"),
                            r.get("spec", {}).get("baseline_run_id")) for r in records}
                if len(cohorts) != 1:
                    issues.append("incomparable_runs")
        report_id = "c_" + uuid4().hex
        report = {"schema_version": 1, "report_id": report_id, "created_at": now(), "spec": spec,
                  "status": "passed" if not issues else "failed", "issues": issues, "evidence": evidence,
                  "scientific_validity": "not_assessed"}
        with self.state.locked():
            self.ready()
            path = self.state.write(f"artifacts/checks/{report_id}.json", report)
            self.state.event("evidence.checked", {"report_id": report_id}, key=report_id)
        return {"ok": not issues, "report_id": report_id, "status": report["status"],
                "issues": issues[:5], "omitted_issues": max(0, len(issues) - 5),
                "report_path": str(path), "scientific_validity": "not_assessed"}

    def import_evidence(self, manifest_path):
        self.ready()
        manifest = self.document(manifest_path, "import")
        env = self.document(manifest["environment_path"], "environment")
        self.validate_environment(env)
        sources = []
        for item in manifest["artifacts"]:
            source = within(self.state.project, item["path"], exists=True)
            if not source.is_file() or file_hash(source) != item["sha256"]:
                raise EvidenceError("artifact_hash_mismatch", "Imported artifact digest does not match.")
            sources.append(source)
        metrics = within(self.state.project, manifest["metrics_path"], exists=True)
        if metrics not in sources:
            raise EvidenceError("missing_metric_artifact", "Metrics must be included in hashed artifacts.")
        extracted = extract_metric_value(read_json(metrics), env["primary_metric"])
        if not extracted["ok"]:
            raise EvidenceError(extracted["error_type"], "Invalid imported metric.")
        checked = validate_metric_result(env["primary_metric"], value=extracted["value"], artifacts=[])
        if not checked["ok"]:
            raise EvidenceError(checked["error_type"], "Imported metric violates its contract.")
        import_id = "i_" + digest({"manifest": manifest, "environment": env})[:32]
        relative = f"artifacts/imports/{import_id}"
        with self.state.locked():
            self.ready()
            final = self.state.path(relative)
            if final.exists():
                record = read_json(self.state.path(f"{relative}/record.json"))
            else:
                stage = self.state.path(f"artifacts/imports/.{import_id}-{uuid4().hex}")
                stage.mkdir(parents=True)
                try:
                    copied = []
                    for index, (source, item) in enumerate(zip(sources, manifest["artifacts"])):
                        dest = stage / f"artifact-{index}"
                        shutil.copyfile(source, dest)
                        if file_hash(dest) != item["sha256"]:
                            raise EvidenceError("artifact_changed", "Source changed while importing.")
                        copied.append({"path": f"artifact-{index}", "source": item["path"], "sha256": item["sha256"]})
                    record = {"schema_version": 1, "import_id": import_id, "manifest": manifest,
                              "environment": env, "created_at": now(), "trust": "external_unverified",
                              "metric": extracted["value"], "artifacts": copied, "derivation_status": "pending"}
                    self.state.write(f"{stage.relative_to(self.state.root)}/record.json", record)
                    stage.rename(final)
                finally:
                    if stage.exists():
                        shutil.rmtree(stage)
            try:
                self.state.write(f"{relative}/result.json", {"import_id": import_id, "metric": record["metric"],
                                 "method_id": manifest["method_id"], "trust": "external_unverified"})
                self.state.event("evidence.imported", {"import_id": import_id}, key=import_id)
                record["derivation_status"] = "complete"
            except (OSError, EvidenceError):
                record["derivation_status"] = "partial"
            self.state.write(f"{relative}/record.json", record)
        return {"ok": True, "import_id": import_id, "trust": "external_unverified", "metric": record["metric"],
                "derivation_status": record["derivation_status"], "record_path": str(final / "record.json")}

    def derive(self, record):
        """Idempotent materialized result; the run itself remains authoritative."""
        run_id = record["run_id"]
        spec = record["spec"]
        result = {"run_id": run_id, "method_id": spec["method_id"], "seed": spec["seed"],
                  "baseline_run_id": spec.get("baseline_run_id"), "status": record["status"],
                  "metric": record.get("metric"), "evidence_status": record["evidence_status"],
                  "trust": record["trust"], "record_path": str(self.state.path(f"runs/{run_id}/run.json"))}
        self.state.write(f"runs/{run_id}/result.json", result)
        self.state.event("run.finished", result, key=f"finished:{run_id}")

    def reconcile(self, run_id):
        self.ready()
        with self.state.locked():
            record = self.state.read_run(run_id)
            if record.get("trust") != "managed_local" or not isinstance(record.get("spec"), dict):
                raise EvidenceError("unsupported_record", "Only managed runs have derived results to reconcile.")
            if alive(record.get("worker")) or alive(record.get("process")):
                raise EvidenceError("run_active", "Run is still active.")
            if record["status"] not in TERMINAL:
                record.update(status="interrupted", evidence_status="invalid", finished_at=now())
            self.derive(record)
            record["derivation_status"] = "complete"
            self.state.write(f"runs/{run_id}/run.json", record)
        return self.receipt(record)
