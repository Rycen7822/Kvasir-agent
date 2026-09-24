"""Read-only migration planning and resumable, provenance-preserving application."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import yaml

from .evidence_contracts import EvidenceError, read_json
from .research_state import digest, file_hash, now

ACTIVE = {"starting", "running", "queued", "pending", "cancelling"}
REFERENCE_KEYS = {"path", "artifact_path", "metrics_path", "stdout_path", "stderr_path", "log_path",
                  "stderr_log_path", "heartbeat_path", "exit_code_path", "detail_path"}
RUN_KEYS = {"run_id", "baseline_run_id", "parent_run_id"}


class Migration:
    def __init__(self, state):
        self.state = state

    def snapshot(self, exclude=()):
        files, empty = {}, []
        if not self.state.root.exists():
            return files, empty
        for path in sorted(self.state.root.rglob("*")):
            rel = path.relative_to(self.state.root).as_posix()
            if (rel == "events/write.lock" or rel == "migrations/pending.json"
                    or rel.startswith("migrations/v3-") or rel in exclude):
                continue
            if path.is_symlink():
                raise EvidenceError("migration_symlink", "Legacy state contains a symlink; review it before migration.")
            if path.is_file():
                files[rel] = file_hash(path)
            elif path.is_dir() and not any(path.iterdir()):
                empty.append(rel)
        return files, empty

    def plan(self):
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
        migration_id = "v3-" + digest(files)[:24]
        archive = f"migrations/{migration_id}/archive"
        path_map = {name: f"{archive}/{name}" for name in files}
        runs, conflicts = [], []
        for source, dest in path_map.items():
            target = self.state.path(dest)
            if target.exists() and (not target.is_file() or file_hash(target) != files[source]):
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
            new_id = "legacy_" + digest(name)[:24]
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
        migration_id = plan.get("migration_id", "")
        if migration_id != "v3-" + digest(plan.get("sources", {}))[:24]:
            raise EvidenceError("invalid_plan", "Migration plan identity is invalid.")
        journal_rel = f"migrations/{migration_id}"
        done_path = self.state.path(f"{journal_rel}/complete.json")
        if done_path.exists():
            done = read_json(done_path)
            if done.get("plan_digest") != digest(plan):
                raise EvidenceError("invalid_plan", "Completed migration has a different plan.")
            manifest = self.state.read_manifest(pending_ok=True)
            if manifest.get("provenance", {}).get("migration_id") != migration_id:
                raise EvidenceError("stale_plan", "Current manifest no longer belongs to this migration.")
            pending_path = self.state.path("migrations/pending.json")
            if pending_path.exists():
                with self.state.locked():
                    pending = read_json(pending_path, limit=50_000_000)
                    if pending.get("plan_digest") != digest(plan) or pending.get("manifest") != manifest:
                        raise EvidenceError("migration_pending", "A different migration is pending.")
                    pending_path.unlink()
            return {"ok": True, "status": "already_applied", "report_path": str(done_path)}
        pending_path = self.state.path("migrations/pending.json")
        if not pending_path.exists():
            current = self.plan()
            if current != plan:
                raise EvidenceError("stale_plan", "Migration inputs changed; produce a new plan.")
            if plan["conflicts"]:
                raise EvidenceError("migration_conflict", "Migration has unresolved conflicts.")
        # No state writes before the complete preflight above.
        with self.state.locked(create=True):
            if pending_path.exists():
                pending = read_json(pending_path, limit=50_000_000)
                if pending.get("plan_digest") != digest(plan):
                    raise EvidenceError("migration_pending", "A different migration is pending.")
            else:
                locked_plan = self.plan()
                # Creating the write lock may make an empty events directory
                # nonempty; cleanup suggestions are not migration inputs.
                locked_plan["empty_directory_candidates"] = plan["empty_directory_candidates"]
                if locked_plan != plan:
                    raise EvidenceError("stale_plan", "Migration inputs changed before application.")
                pending = {"plan_digest": digest(plan), "plan": plan,
                           "manifest": {"schema_version": 3, "layout_version": 3, "project_id": uuid4().hex,
                                        "created_at": now(), "provenance": {"migration_id": migration_id,
                                        "source_manifest": plan["path_map"].get("research.yaml")}}}
                self.state.write("migrations/pending.json", pending)
            sources, _ = self.snapshot(exclude={r["destination"] for r in plan["runs"]})
            # The manifest is the final commit point. A crash after replacing it
            # resumes against the archived old manifest, not its new content.
            if self.state.manifest.exists():
                try:
                    if yaml.safe_load(self.state.manifest.read_text()) == pending["manifest"]:
                        if "research.yaml" in plan["sources"]:
                            sources["research.yaml"] = file_hash(self.state.path(plan["path_map"]["research.yaml"]))
                        else:
                            sources.pop("research.yaml", None)
                except yaml.YAMLError:
                    pass
            if sources != plan["sources"]:
                raise EvidenceError("stale_plan", "Legacy inputs changed during migration.")
            # Stage every original before publishing any converted run.
            for name, expected in plan["sources"].items():
                target = self.state.path(plan["path_map"][name])
                if target.exists() and file_hash(target) == expected:
                    continue
                if target.exists():
                    raise EvidenceError("migration_conflict", "Archive target changed during migration.")
                source = self.state.path(name)
                if file_hash(source) != expected:
                    raise EvidenceError("stale_plan", "Source changed while copying.")
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_name(target.name + ".copying")
                shutil.copyfile(source, tmp)
                if file_hash(tmp) != expected:
                    raise EvidenceError("stale_plan", "Source changed while copying.")
                tmp.replace(target)
            # Old writers do not share the v3 lock. Recheck the entire input
            # set after staging, including files copied early in the loop.
            for name, expected in plan["sources"].items():
                source = self.state.path(name)
                if name == "research.yaml":
                    try:
                        if yaml.safe_load(source.read_text()) == pending["manifest"]:
                            source = self.state.path(plan["path_map"][name])
                    except (ValueError, yaml.YAMLError):
                        pass  # The hash check below reports the changed source.
                if not source.is_file() or file_hash(source) != expected:
                    raise EvidenceError("stale_plan", "Legacy input changed during staging.")
            for run in plan["runs"]:
                original = read_json(self.state.path(plan["path_map"][run["source"]]))
                migrated = {"schema_version": 1, "run_id": run["run_id"], "project_id": pending["manifest"]["project_id"],
                            "status": "imported", "evidence_status": "unverified", "trust": "legacy_unverified",
                            "source_sha256": plan["sources"][run["source"]],
                            "source_path": str(self.state.path(plan["path_map"][run["source"]])),
                            "legacy_record": self.rewrite_references(original, run["source"], plan)}
                dest = self.state.path(run["destination"])
                if dest.exists() and read_json(dest) != migrated:
                    raise EvidenceError("migration_conflict", "Converted target changed during migration.")
                if not dest.exists():
                    self.state.write(run["destination"], migrated)
            self.state.write(f"{journal_rel}/plan.json", plan)
            self.state.write("research.yaml", pending["manifest"])
            report = {"ok": True, "status": "applied", "migration_id": migration_id,
                      "plan_digest": digest(plan), "preserved_files": len(plan["sources"]),
                      "run_mappings": plan["runs"], "path_map": plan["path_map"],
                      "legacy_trust": "unverified", "controllers_activated": False}
            self.state.write(f"{journal_rel}/complete.json", report)
            pending_path.unlink()
        return {"ok": True, "status": "applied", "report_path": str(done_path), "runs_migrated": len(plan["runs"])}
