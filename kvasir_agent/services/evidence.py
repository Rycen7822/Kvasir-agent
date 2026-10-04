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
from .comparison import compare, protocol_issues, request_snapshot
from .observations import observations, timestamp

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

    def receipt(self, record, *, detail=True):
        run_id = record["run_id"]
        status = record["status"]
        if status not in TERMINAL and not alive(record.get("worker")):
            status = "interrupted"
        out = {"ok": True, "run_id": run_id, "status": status,
               "record_path": f"Kvasir-agent/runs/{run_id}/run.json",
               "evidence_status": record.get("evidence_status", "pending"),
               "integrity_check": "not_performed"}
        if record.get("metric") is not None:
            out["metric"] = record["metric"]
        if record.get("derivation_status") == "partial":
            out["derivation_status"] = "partial"
        fields = ("created_at", "started_at", "finished_at", "cancel_requested_at",
                  "exit_code", "error_type", "logs_truncated", "elapsed_seconds") if detail else ("created_at", "error_type")
        for field in fields:
            if field in record:
                value = record[field]
                out[field] = value[:120] if isinstance(value, str) else value
        if record.get("spec", {}).get("schema_version") == 2:
            observed = self.observations(record)
            out["observations"] = observed if detail else {
                "progress": {k: observed["progress"][k] for k in ("status", "phase") if k in observed["progress"]},
                "cost": {k: observed["cost"][k] for k in ("status", "managed_wall_seconds") if k in observed["cost"]}}
        return out

    def observations(self, record):
        return observations(self.state, record)

    def status(self, run_id=None):
        manifest = self.state.read_manifest()
        if run_id:
            return self.receipt(self.state.read_run(run_id))
        paths = sorted(self.state.path("runs").glob("*/run.json"))
        summaries, corrupt = [], []
        for path in paths:
            try:
                record = self.state.read_run(path.parent.name)
                try:
                    created = timestamp(record.get("created_at", "")).timestamp()
                except (ValueError, TypeError):
                    created = float("-inf")
                summaries.append((created, record["run_id"], record))
            except EvidenceError:
                corrupt.append({"run_id": path.parent.name[:80], "status": "corrupt"})
        summaries.sort(key=lambda x: (x[0], x[1]), reverse=True)
        selected = [self.receipt(item[2], detail=False) for item in summaries[:5]]
        _, bad = self.state.events()
        return {"ok": True, "project_id": manifest["project_id"], "status": "ready",
                "manifest_path": str(self.state.manifest), "runs": selected,
                "omitted_runs": max(0, len(paths) - len(selected)),
                "corrupt_runs": corrupt[:5], "omitted_corrupt_runs": max(0, len(corrupt) - 5),
                "research_index_path": "Kvasir-agent/research/index.json",
                "runs_path": str(self.state.path("runs")), "invalid_event_lines": bad[:5],
                "omitted_invalid_lines": max(0, len(bad) - 5)}

    def run(self, spec_path, idempotency_key):
        self.ready()
        spec = self.document(spec_path, "run")
        env = self.document(spec["environment_path"], "environment")
        protocol = self.document(spec["comparison"]["protocol_path"], "comparison") if spec.get("comparison") else None
        candidate = self.document(spec["candidate_path"], "research") if spec.get("candidate_path") else None
        request_digest = digest(request_snapshot(spec, env, protocol, candidate))
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
            if candidate is not None:
                self.validate_candidate(candidate, spec, protocol)
            if protocol is not None:
                problems = protocol_issues(protocol, spec, env, state.project)
                if problems:
                    raise EvidenceError("invalid_comparison", ", ".join(problems[:3]))
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
            for output in [spec["metrics_path"], *spec["outputs"],
                           *[spec[key] for key in ("progress_path", "cost_path") if key in spec]]:
                if Path(output).is_absolute() or output in {"run.json", "result.json", "stdout.log", "stderr.log", "worker.log"}:
                    raise EvidenceError("invalid_output", "Outputs must be relative run artifacts, not control files.")
                target = within(run_dir, output)
                if target == run_dir:
                    raise EvidenceError("invalid_output", "Output must name a file.")
            record = {"schema_version": 1, "run_id": run_id, "project_id": state.read_manifest()["project_id"],
                      "status": "starting", "created_at": now(), "idempotency_key": idempotency_key,
                      "spec": spec, "environment": env, "environment_digest": digest(env),
                      "request_digest": request_digest, "trust": "managed_local", "evidence_status": "pending"}
            if protocol is not None:
                record.update(protocol=protocol, protocol_digest=digest(protocol), protocol_referenced_at=now())
                state.write(f"protocols/{digest(protocol)}.json", protocol)
            if candidate is not None:
                record.update(candidate=candidate, candidate_digest=digest(candidate))
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
        if digest(request_snapshot(spec, env, record.get("protocol"), record.get("candidate"))) != record.get("request_digest"):
            issues.append("request_digest_mismatch")
        if digest(env) != record.get("environment_digest"):
            issues.append("environment_digest_mismatch")
        try:
            self.validate_run_inputs(record)
        except EvidenceError as exc:
            issues.append(exc.kind)
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
        issues.extend(self.metric_issues(
            self.state.path(f"runs/{record['run_id']}"), spec.get("metrics_path"),
            env.get("primary_metric"), record.get("metric"), record.get("artifacts", [])))
        return sorted(set(issues))

    def validate_run_inputs(self, record):
        if record.get("protocol") is not None:
            spec = record["spec"]
            current = self.document(spec["comparison"]["protocol_path"], "comparison")
            if digest(current) != record.get("protocol_digest") or digest(record["protocol"]) != record.get("protocol_digest"):
                raise EvidenceError("protocol_version_changed", "Referenced protocol changed.")
            failures = protocol_issues(record["protocol"], spec, record["environment"], self.state.project)
            if failures:
                raise EvidenceError("invalid_comparison", ", ".join(failures[:3]))
        if record.get("candidate") is not None:
            current = self.document(record["spec"]["candidate_path"], "research")
            if digest(current) != record.get("candidate_digest") or digest(record["candidate"]) != record.get("candidate_digest"):
                raise EvidenceError("candidate_version_changed", "Referenced candidate changed.")
            self.validate_candidate(record["candidate"], record["spec"], record.get("protocol"))

    def validate_candidate(self, candidate, spec, protocol=None):
        from .research_records import ResearchRecords
        if candidate["kind"] != "candidate" or candidate["metadata"]["method_id"] != spec["method_id"]:
            raise EvidenceError("candidate_identity_mismatch", "Candidate and method do not match.")
        records = ResearchRecords(str(self.state.project))
        failures, _ = records.bytes_issues(candidate)
        if failures:
            raise EvidenceError("candidate_input_changed", ", ".join(failures[:3]))
        for reference in records.references(candidate):
            latest = records.resolve(reference["record_id"])
            if latest["revision"] != reference["revision"]:
                raise EvidenceError("candidate_dependency_superseded", reference["record_id"])
            dependency_issues, _ = records.inspect([reference["record_id"]])
            if dependency_issues:
                raise EvidenceError("candidate_dependency_invalid", ", ".join(dependency_issues[:3]))
        if protocol is not None:
            role = "baseline" if spec["purpose"] == "baseline" else "candidate"
            if any(item not in protocol["method_inputs"][role] for item in candidate["metadata"]["files"]):
                raise EvidenceError("protocol_candidate_mismatch", "Protocol does not pin the candidate inputs.")

    @staticmethod
    def metric_issues(root, path, contract, value, artifacts):
        """Check saved numbers against their hashed original, not just finite values."""
        if not path or path not in {a.get("path") for a in artifacts if isinstance(a, dict)}:
            return ["missing_metric_artifact"]
        try:
            extracted = extract_metric_value(read_json(within(root, path, exists=True)), contract)
            if not extracted["ok"]:
                return [extracted["error_type"]]
            valid = validate_metric_result(contract, value=extracted["value"], artifacts=[])
            if not valid["ok"]:
                return [valid["error_type"]]
            return [] if extracted["value"] == value else ["metric_value_mismatch"]
        except (EvidenceError, OSError, TypeError, AttributeError):
            return ["metric_unavailable"]

    def import_issues(self, import_id, record):
        try:
            manifest = validate_document(record["manifest"], "import")
            env = validate_document(record["environment"], "environment")
            if (record.get("import_id") != import_id or record.get("trust") != "external_unverified"
                    or "i_" + digest({"manifest": manifest, "environment": env})[:32] != import_id):
                return ["import_identity_mismatch"]
            artifacts = record["artifacts"]
            if len(artifacts) != len(manifest["artifacts"]):
                return ["import_artifact_manifest_mismatch"]
            root = self.state.path(f"artifacts/imports/{import_id}")
            issues, metric_path = [], None
            for index, (saved, source) in enumerate(zip(artifacts, manifest["artifacts"])):
                if (saved.get("path") != f"artifact-{index}" or saved.get("source") != source["path"]
                        or saved.get("sha256") != source["sha256"]):
                    issues.append("import_artifact_manifest_mismatch")
                    continue
                try:
                    if file_hash(within(root, saved["path"], exists=True)) != source["sha256"]:
                        issues.append("artifact_hash_mismatch")
                except (EvidenceError, OSError):
                    issues.append("artifact_unavailable")
                if source["path"] == manifest["metrics_path"]:
                    metric_path = saved["path"]
            issues.extend(self.metric_issues(root, metric_path, env["primary_metric"],
                                             record.get("metric"), artifacts))
            return sorted(set(issues))
        except (EvidenceError, KeyError, TypeError, AttributeError, ValueError):
            return ["corrupt_import"]

    def check(self, spec_path):
        self.ready()
        spec = self.document(spec_path, "check")
        issues, evidence, integrity_issues = [], [], []
        assessment = {"execution": "not_assessed", "integrity": "not_assessed",
                      "comparability": "not_assessed", "statistical_support": "not_assessed", "review": "not_assessed"}
        if spec["target"] == "environment":
            env = self.document(spec["environment_path"], "environment")
            try:
                evidence.append(self.validate_environment(env))
            except EvidenceError as exc:
                issues.append(exc.kind)
            integrity_issues = list(issues)
            assessment["integrity"] = "passed" if not integrity_issues else "failed"
        elif spec["target"] == "comparison":
            protocol = self.document(spec["protocol_path"], "comparison")
            issues, comparison = compare(self, protocol)
            evidence.append(comparison)
            integrity_issues = [issue for row in comparison["attempts"] for issue in row["integrity_issues"]]
            integrity_issues += [issue for issue in issues if issue.endswith(":unreadable_attempt")]
            assessment["execution"] = "see_attempts"
            assessment["integrity"] = ("passed" if not integrity_issues else "failed") if comparison["attempts"] else "not_assessed"
            assessment["comparability"] = "declared_protocol_satisfied" if not issues else "incomplete"
        elif spec["target"] == "research":
            from .research_records import ResearchRecords
            issues, evidence = ResearchRecords(str(self.state.project)).inspect(spec["record_ids"])
            assessment["integrity"] = "passed" if not issues else "failed"
            if any(row.get("kind") == "review" for row in evidence):
                assessment["review"] = "saved_bindings_checked" if not issues else "stale_or_invalid"
        elif spec["target"] == "import":
            import_id = spec["import_id"]
            try:
                record = read_json(self.state.path(f"artifacts/imports/{import_id}/record.json"))
                issues.extend(self.import_issues(import_id, record))
                evidence.append({"import_id": import_id, "trust": "external_unverified"})
            except (EvidenceError, OSError):
                issues.append("import_unavailable")
            assessment["execution"] = "external_unverified"
            assessment["integrity"] = "passed" if not issues else "failed"
        else:
            ids = spec.get("run_ids", [spec.get("run_id")])
            records = []
            for run_id in ids:
                try:
                    record = self.state.read_run(run_id)
                    records.append(record)
                    failures = self.run_issues(record)
                    integrity_issues.extend(f"{run_id}:{issue}" for issue in failures if issue != "run_not_verified")
                    issues.extend(f"{run_id}:{issue}" for issue in failures)
                    evidence.append({"run_id": run_id, "record_path": str(self.state.path(f"runs/{run_id}/run.json")), "issues": failures})
                except EvidenceError as exc:
                    issues.append(f"{run_id}:{exc.kind}")
                    integrity_issues.append(f"{run_id}:{exc.kind}")
            assessment["execution"] = "completed" if len(records) == len(ids) and all(r.get("status") == "completed" for r in records) else "incomplete"
            assessment["integrity"] = "passed" if not integrity_issues else "failed"
            if spec["target"] == "claim" and records:
                seeds = {r.get("spec", {}).get("seed") for r in records if not self.run_issues(r)} - {None}
                if len(seeds) < spec["minimum_seeds"]:
                    issues.append("insufficient_observed_seeds")
                cohorts = {(r.get("environment_digest"), r.get("spec", {}).get("method_id"),
                            r.get("spec", {}).get("baseline_run_id")) for r in records}
                if len(cohorts) != 1:
                    issues.append("incomparable_runs")
                assessment["comparability"] = "legacy_cohort_satisfied" if not issues else "incomplete"
        report_id = "c_" + uuid4().hex
        report = {"schema_version": 1, "report_id": report_id, "created_at": now(), "spec": spec,
                  "status": "passed" if not issues else "failed", "issues": issues, "evidence": evidence,
                  "assessment": assessment, "integrity_check": "fresh", "scientific_validity": "not_assessed"}
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
                issues = self.import_issues(import_id, record)
                if issues:
                    raise EvidenceError("import_integrity_failed", "Saved import failed verification: " + ", ".join(issues[:3]))
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
