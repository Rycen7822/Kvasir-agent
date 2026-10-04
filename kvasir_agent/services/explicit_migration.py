"""Read-only migration planning and resumable, provenance-preserving application."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from uuid import uuid4

import yaml

from .evidence_contracts import EvidenceError, read_json
from .research_state import now

ACTIVE = {"starting", "running", "queued", "pending", "cancelling"}
REFERENCE_KEYS = {"path", "artifact_path", "metrics_path", "stdout_path", "stderr_path", "log_path",
                  "stderr_log_path", "heartbeat_path", "exit_code_path", "detail_path"}
RUN_KEYS = {"run_id", "baseline_run_id", "parent_run_id"}


class Migration:
    def __init__(self, state):
        self.state = state

    def snapshot(self):
        files, empty = [], []
        if not self.state.root.exists():
            return files, empty
        for path in sorted(self.state.root.rglob("*")):
            rel = path.relative_to(self.state.root).as_posix()
            if (rel == "events/write.lock" or rel == "migrations/pending.json"
                    or rel.startswith("migrations/v3-")):
                continue
            if path.is_symlink():
                raise EvidenceError("migration_symlink", "Legacy state contains a symlink; review it before migration.")
            if path.is_file():
                files.append(rel)
            elif path.is_dir() and not any(path.iterdir()):
                empty.append(rel)
        return files, empty

    def plan(self, previous=None):
        if self.state.path("migrations/pending.json").exists():
            raise EvidenceError("migration_pending", "Resume the saved migration plan.")
        files, empty = self.snapshot()
        if not files:
            raise EvidenceError("no_legacy_state", "No legacy evidence to migrate.")
        if "research.yaml" in files:
            try:
                manifest = yaml.safe_load(self.state.manifest.read_text())
            except (ValueError, yaml.YAMLError) as exc:
                raise EvidenceError("corrupt_manifest", "Legacy manifest cannot be parsed.") from exc
            if not isinstance(manifest, dict) or manifest.get("schema_version") not in {1, 2}:
                raise EvidenceError("unsupported_migration", "Only v1/v2 or quest layouts can be migrated.")
        else:
            metadata = [name for name in files if Path(name).name in {"quest.yaml", "quest.yml", "quest.json"}]
            if not metadata:
                raise EvidenceError("unsupported_migration", "No recognized legacy manifest.")
            for name in metadata:
                try:
                    obj = yaml.safe_load(self.state.path(name).read_text())
                except (ValueError, yaml.YAMLError) as exc:
                    raise EvidenceError("corrupt_manifest", "Invalid legacy quest metadata.") from exc
                if not isinstance(obj, dict):
                    raise EvidenceError("corrupt_manifest", "Invalid legacy quest metadata.")
        migration_id = previous["migration_id"] if previous else "v3-" + uuid4().hex[:24]
        identities = {r["source"]: r["run_id"] for r in previous["runs"]} if previous else {}
        archive = f"migrations/{migration_id}/archive"
        path_map = {name: f"{archive}/{name}" for name in files}
        runs, conflicts = [], []
        for dest in path_map.values():
            target = self.state.path(dest)
            if target.exists():
                conflicts.append({"path": dest, "reason": "archive_conflict"})
        for name in files:
            parts = Path(name).parts
            if "runs" not in parts or not name.endswith(".json"):
                continue
            if Path(name).name not in {"run.json", "runner.json"} and Path(name).parent.name != "runs":
                continue
            try:
                record = read_json(self.state.path(name))
            except EvidenceError:
                conflicts.append({"path": name, "reason": "unreadable_run"})
                continue
            if not isinstance(record, dict):
                conflicts.append({"path": name, "reason": "invalid_run"})
                continue
            if record.get("status") in ACTIVE:
                conflicts.append({"path": name, "reason": "active_or_unresolved_run"})
            new_id = identities.get(name) or "legacy_" + uuid4().hex[:24]
            dest = f"runs/{new_id}/run.json"
            if dest in files:
                conflicts.append({"path": dest, "reason": "target_conflict"})
            runs.append({"source": name, "old_id": str(record.get("run_id") or Path(name).stem),
                         "run_id": new_id, "destination": dest})
        return {"schema_version": 1, "migration_id": migration_id, "project": str(self.state.project),
                "sources": files, "path_map": path_map, "runs": runs, "conflicts": conflicts,
                "empty_directory_candidates": empty,
                "unclassified_files": [name for name in files if name not in {r["source"] for r in runs}],
                "policy": "archive originals; legacy evidence remains unverified; controllers remain inactive"}

    def rewrite_references(self, value, source, plan):
        """Rewrite only known typed fields; prose and raw archived bytes are untouched."""
        if isinstance(value, list):
            return [self.rewrite_references(item, source, plan) for item in value]
        if not isinstance(value, dict):
            return value
        result = {}
        namespace = source.split("runs/", 1)[0]
        for key, item in value.items():
            if key in RUN_KEYS and isinstance(item, str):
                matches = [r for r in plan["runs"] if r["old_id"] == item and r["source"].split("runs/", 1)[0] == namespace]
                result[key] = matches[0]["run_id"] if len(matches) == 1 else item
            elif key in REFERENCE_KEYS and isinstance(item, str):
                raw = Path(item)
                candidates = [item, (Path(source).parent / raw).as_posix()]
                if "/Kvasir-agent/" in item:
                    candidates.append(item.split("/Kvasir-agent/", 1)[1])
                if item.startswith("Kvasir-agent/"):
                    candidates.append(item[len("Kvasir-agent/"):])
                if raw.is_absolute() and raw.is_relative_to(self.state.root):
                    candidates.insert(0, raw.relative_to(self.state.root).as_posix())
                found = next((p for p in candidates if p in plan["path_map"]), None)
                result[key] = str(self.state.path(plan["path_map"][found])) if found else item
            else:
                result[key] = self.rewrite_references(item, source, plan)
        return result

    def apply(self, plan):
        if not isinstance(plan, dict) or plan.get("project") != str(self.state.project):
            raise EvidenceError("invalid_plan", "Migration plan belongs to a different project.")
        # Older plans mapped paths to checksums; only their path keys are needed.
        plan = {**plan, "sources": sorted(plan["sources"])}
        migration_id = plan.get("migration_id", "")
        if not re.fullmatch(r"v3-[a-f0-9]{24}", migration_id):
            raise EvidenceError("invalid_plan", "Migration plan identity is invalid.")
        journal_rel = f"migrations/{migration_id}"
        if plan["path_map"] != {name: f"{journal_rel}/archive/{name}" for name in plan["sources"]}:
            raise EvidenceError("invalid_plan", "Migration archive paths are invalid.")
        for name in plan["sources"]:
            self.state.path(name)
        for run in plan["runs"]:
            if (run["source"] not in plan["sources"]
                    or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run["run_id"])
                    or run["destination"] != f"runs/{run['run_id']}/run.json"):
                raise EvidenceError("invalid_plan", "Migration run mapping is invalid.")

        def same_plan(saved):
            return {**saved, "sources": sorted(saved["sources"])} == plan

        done_path = self.state.path(f"{journal_rel}/complete.json")
        pending_path = self.state.path("migrations/pending.json")
        if not done_path.exists() and not pending_path.exists():
            current = self.plan(plan)
            if any(current[key] != plan[key] for key in ("sources", "path_map", "runs")):
                raise EvidenceError("stale_plan", "Migration source paths or run mappings changed.")
            if plan["conflicts"] or current["conflicts"]:
                raise EvidenceError("migration_conflict", "Migration has unresolved conflicts.")
        # No state writes before the complete preflight above.
        with self.state.locked(create=True):
            if done_path.exists():
                if not same_plan(read_json(self.state.path(f"{journal_rel}/plan.json"), limit=50_000_000)):
                    raise EvidenceError("invalid_plan", "Completed migration has a different plan.")
                manifest = self.state.read_manifest(pending_ok=True)
                if manifest.get("provenance", {}).get("migration_id") != migration_id:
                    raise EvidenceError("stale_plan", "Current manifest no longer belongs to this migration.")
                if pending_path.exists():
                    pending = read_json(pending_path, limit=50_000_000)
                    if not same_plan(pending["plan"]) or pending.get("manifest") != manifest:
                        raise EvidenceError("migration_pending", "A different migration is pending.")
                    pending_path.unlink()
                return {"ok": True, "status": "already_applied", "report_path": str(done_path)}
            resuming = pending_path.exists()
            if resuming:
                pending = read_json(pending_path, limit=50_000_000)
                if not same_plan(pending["plan"]):
                    raise EvidenceError("migration_pending", "A different migration is pending.")
            else:
                pending = {"plan": plan,
                           "manifest": {"schema_version": 3, "layout_version": 3, "project_id": uuid4().hex,
                                        "created_at": now(), "provenance": {"migration_id": migration_id,
                                        "source_manifest": plan["path_map"].get("research.yaml")}}}
                self.state.write("migrations/pending.json", pending)
            # Stage every original before publishing any converted run.
            for name in plan["sources"]:
                target = self.state.path(plan["path_map"][name])
                if target.exists():
                    if not resuming or not target.is_file():
                        raise EvidenceError("migration_conflict", "Archive target already exists.")
                    continue  # A resumed migration uses its published archive.
                source = self.state.path(name)
                if not source.is_file():
                    raise EvidenceError("artifact_unavailable", "Legacy source is not a file.")
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.state.path(f"{plan['path_map'][name]}.{uuid4().hex}.copying")
                try:
                    shutil.copyfile(source, tmp)
                    tmp.replace(target)
                finally:
                    tmp.unlink(missing_ok=True)
            for run in plan["runs"]:
                original = read_json(self.state.path(plan["path_map"][run["source"]]))
                migrated = {"schema_version": 1, "run_id": run["run_id"], "project_id": pending["manifest"]["project_id"],
                            "status": "imported", "evidence_status": "unverified", "trust": "legacy_unverified",
                            "source_path": str(self.state.path(plan["path_map"][run["source"]])),
                            "legacy_record": self.rewrite_references(original, run["source"], plan)}
                dest = self.state.path(run["destination"])
                if dest.exists():
                    saved = read_json(dest)
                    if any(saved.get(key) != value for key, value in migrated.items()):
                        raise EvidenceError("migration_conflict", "Converted target changed during migration.")
                if not dest.exists():
                    self.state.write(run["destination"], migrated)
            self.state.write(f"{journal_rel}/plan.json", plan)
            self.state.write("research.yaml", pending["manifest"])
            report = {"ok": True, "status": "applied", "migration_id": migration_id,
                      "preserved_files": len(plan["sources"]),
                      "run_mappings": plan["runs"], "path_map": plan["path_map"],
                      "legacy_trust": "unverified", "controllers_activated": False}
            self.state.write(f"{journal_rel}/complete.json", report)
            pending_path.unlink()
        return {"ok": True, "status": "applied", "report_path": str(done_path), "runs_migrated": len(plan["runs"])}
