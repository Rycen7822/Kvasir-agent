"""Typed research files and a rebuildable project index, without memory injection."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from .evidence_contracts import EvidenceError, read_json, validate_document
from .research_state import ResearchState, digest, file_hash, now, within


class ResearchRecords:
    def __init__(self, project):
        self.state = ResearchState(project)

    def ready(self):
        self.state.read_manifest()
        if self.state.events()[1]:
            raise EvidenceError("corrupt_events", "Event journal needs explicit repair.")

    def read_document(self, path):
        return validate_document(read_json(within(self.state.project, path, exists=True)), "research")

    def bytes_issues(self, document):
        issues, limitations = [], []
        files = [document["content"]]
        metadata = document["metadata"]
        if document["kind"] == "candidate":
            files += metadata["files"]
        if document["kind"] == "review":
            files += [metadata["target"]]
            if metadata["outcome"] == "approved" and metadata["unresolved"]:
                issues.append("approved_review_has_unresolved_issues")
            limitations.append("reviewer_and_outcome_are_declared")
        for item in files:
            try:
                if file_hash(within(self.state.project, item["path"], exists=True)) != item["sha256"]:
                    issues.append("content_stale:" + item["path"])
            except (EvidenceError, OSError):
                issues.append("content_missing:" + item["path"])
        if document["kind"] == "source":
            coverage = metadata["coverage"]
            if coverage["mode"] != "fulltext":
                limitations.append("source_coverage:" + coverage["mode"])
            if coverage["truncated"]:
                limitations.append("source_truncated")
            if coverage.get("pages_total") is not None and coverage.get("pages_received", 0) < coverage["pages_total"]:
                limitations.append("source_pagination_incomplete")
            if metadata.get("submitted_query") != metadata.get("effective_query"):
                limitations.append("query_changed")
            try:
                if datetime.fromisoformat(metadata["retrieved_at"]).tzinfo is None:
                    issues.append("source_time_missing_timezone")
            except ValueError:
                issues.append("source_time_invalid")
            for locator in metadata["locators"]:
                try:
                    path = within(self.state.project, locator["path"], exists=True)
                    if file_hash(path) != locator["sha256"]:
                        issues.append("locator_source_stale")
                        continue
                    if locator["kind"] == "page":
                        limitations.append("page_locator_unresolved")
                        continue
                    if locator["end"] < locator["start"] or path.stat().st_size > 2_000_000:
                        issues.append("locator_range_invalid")
                        continue
                    lines = path.read_text(encoding="utf-8").splitlines()
                    if locator["end"] > len(lines):
                        issues.append("locator_range_invalid")
                    elif locator["excerpt"] not in "\n".join(lines[locator["start"] - 1:locator["end"]]):
                        issues.append("locator_excerpt_mismatch")
                except (EvidenceError, OSError, UnicodeError):
                    issues.append("locator_source_unavailable")
        return sorted(set(issues)), sorted(set(limitations))

    def resolve(self, record_id, revision=None):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", record_id):
            raise EvidenceError("invalid_record_id", "Invalid research record identity.")
        if revision is not None and not re.fullmatch(r"[a-f0-9]{64}", revision):
            raise EvidenceError("invalid_revision", "Invalid research revision.")
        paths = [self.state.path(f"research/records/{record_id}/{revision}.json")] if revision else list(self.state.path(f"research/records/{record_id}").glob("*.json"))
        if not paths:
            raise EvidenceError("research_record_missing", "Research record does not exist.")
        records = []
        for path in paths:
            saved = read_json(path)
            document = validate_document(saved["document"], "research")
            if (document["record_id"] != record_id or saved["revision"] != digest(document)
                    or path.stem != saved["revision"]):
                raise EvidenceError("corrupt_research_record", "Research identity or digest mismatch.")
            records.append(saved)
        return max(records, key=lambda x: (x["registered_at"], x["revision"]))

    @staticmethod
    def references(document):
        refs = list(document["dependencies"])
        if document["kind"] == "candidate":
            refs += document["metadata"]["parents"]
        return refs

    def register(self, path):
        self.ready()
        document = self.read_document(path)
        failures, _ = self.bytes_issues(document)
        if failures:
            raise EvidenceError("invalid_research_content", ", ".join(failures[:3]))
        revision = digest(document)
        record_id = document["record_id"]
        with self.state.locked():
            self.ready()
            for reference in self.references(document):
                self.resolve(reference["record_id"], reference["revision"])
            for run_id in document.get("run_ids", []):
                self.state.read_run(run_id)
            relative = f"research/records/{record_id}/{revision}.json"
            target = self.state.path(relative)
            reused = target.exists()
            if reused:
                self.resolve(record_id, revision)
            else:
                self.state.write(relative, {"schema_version": 1, "revision": revision,
                                           "registered_at": now(), "document": document})
            try:
                self._write_index()
                derivation = "complete"
            except (OSError, EvidenceError, ValueError, KeyError, TypeError):
                derivation = "partial"
        return {"ok": True, "record_id": record_id, "revision": revision, "reused": reused,
                "record_path": str(target), "index_path": str(self.state.path("research/index.json")),
                "derivation_status": derivation}

    def _write_index(self):
        entries = []
        directories = sorted(self.state.path("research/records").glob("*"))
        if len(directories) > 10000:
            raise EvidenceError("index_limit", "Research index exceeds the supported project size.")
        for folder in directories:
            if not folder.is_dir():
                continue
            latest = self.resolve(folder.name)
            document = latest["document"]
            entries.append({"record_id": folder.name, "kind": document["kind"], "title": document["title"],
                            "revision": latest["revision"], "content_path": document["content"]["path"],
                            "record_path": str(self.state.path(f"research/records/{folder.name}/{latest['revision']}.json")),
                            "history_path": str(folder), "run_ids": document.get("run_ids", [])})
        legacy = []
        for receipt in sorted(self.state.path("migrations").glob("*/complete.json")):
            migration = read_json(receipt, limit=50_000_000)
            for old, archived in migration.get("path_map", {}).items():
                # Index the explicit migration map; never activate the old controller.
                legacy.append({"original_path": old, "archived_path": str(self.state.path(archived)),
                               "trust": "legacy_unverified", "migration_receipt": str(receipt)})
        index = {"schema_version": 1, "built_at": now(), "entries": entries, "legacy_paths": legacy,
                 "authority": "research/records; index is derived"}
        self.state.write("research/index.json", index)
        return {"ok": True, "records": len(entries), "legacy_paths": len(legacy),
                "index_path": str(self.state.path("research/index.json"))}

    def reindex(self):
        self.ready()
        with self.state.locked():
            self.ready()
            return self._write_index()

    def inspect(self, record_ids):
        self.ready()
        rows, all_issues, memo = [], [], {}

        def visit(record_id, revision=None, stack=()):
            try:
                saved = self.resolve(record_id, revision)
                key = (record_id, saved["revision"])
                if key in stack:
                    return ["dependency_cycle"], []
                if len(stack) >= 50 or len(memo) >= 1000:
                    return ["dependency_depth_limit"], []
                if key in memo:
                    return memo[key]
                document = saved["document"]
                failures, limitations = self.bytes_issues(document)
                for reference in self.references(document):
                    latest = self.resolve(reference["record_id"])
                    if latest["revision"] != reference["revision"]:
                        failures.append("dependency_superseded:" + reference["record_id"])
                    dep_issues, dep_limits = visit(reference["record_id"], reference["revision"], (*stack, key))
                    failures.extend("dependency:" + reference["record_id"] + ":" + x for x in dep_issues)
                    limitations.extend(dep_limits)
                for run_id in document.get("run_ids", []):
                    from .evidence import EvidenceService
                    service = EvidenceService(str(self.state.project))
                    failures.extend("run:" + run_id + ":" + x for x in service.run_issues(self.state.read_run(run_id)))
                memo[key] = (sorted(set(failures)), sorted(set(limitations)))
                return memo[key]
            except (EvidenceError, OSError, KeyError, TypeError, ValueError) as exc:
                return [exc.kind if isinstance(exc, EvidenceError) else "corrupt_research_record"], []

        for record_id in record_ids:
            failures, limitations = visit(record_id)
            all_issues.extend(record_id + ":" + x for x in failures)
            try:
                saved = self.resolve(record_id)
                identity = {"revision": saved["revision"], "kind": saved["document"]["kind"]}
            except (EvidenceError, OSError, KeyError, TypeError, ValueError):
                identity = {}
            rows.append({"record_id": record_id, **identity, "issues": failures, "limitations": limitations,
                         "status": "stale_or_invalid" if failures else ("checked_with_limits" if limitations else "checked"),
                         "scientific_validity": "not_assessed"})
        return sorted(set(all_issues)), rows
