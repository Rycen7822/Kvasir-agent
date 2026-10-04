"""Typed research files and a rebuildable project index, without memory injection."""
from __future__ import annotations

from datetime import datetime
import re
import shutil

from .evidence_contracts import EvidenceError, read_json, validate_document
from .research_state import ResearchState, now, within


class ResearchRecords:
    def __init__(self, project):
        self.state = ResearchState(project)

    def ready(self):
        self.state.read_manifest()
        if self.state.events()[1]:
            raise EvidenceError("corrupt_events", "Event journal needs explicit repair.")

    def read_document(self, path):
        return validate_document(read_json(within(self.state.project, path, exists=True)), "research")

    def material_issues(self, document, materials=None):
        issues, limitations = [], []
        materials = materials or {}

        def material_path(item):
            if item["path"] in materials:
                return self.state.path(materials[item["path"]])
            return within(self.state.project, item["path"], exists=True)

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
                if not material_path(item).is_file():
                    issues.append("content_missing:" + item["path"])
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
                    path = material_path(locator)
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
        if revision is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", revision):
            raise EvidenceError("invalid_revision", "Invalid research revision.")
        paths = [self.state.path(f"research/records/{record_id}/{revision}.json")] if revision else list(self.state.path(f"research/records/{record_id}").glob("*.json"))
        if not paths:
            raise EvidenceError("research_record_missing", "Research record does not exist.")
        records = []
        for path in paths:
            saved = read_json(path)
            document = validate_document(saved["document"], "research")
            if document["record_id"] != record_id or path.stem != saved["revision"]:
                raise EvidenceError("corrupt_research_record", "Research identity mismatch.")
            saved["document"] = document
            records.append(saved)
        return max(records, key=lambda x: (x["registered_at"],
                   int(x["revision"][1:]) if re.fullmatch(r"v[0-9]+", x["revision"]) else 0, x["revision"]))

    @staticmethod
    def references(document):
        refs = list(document["dependencies"])
        if document["kind"] == "candidate":
            refs += document["metadata"]["parents"]
        return refs

    def register(self, path):
        self.ready()
        document = self.read_document(path)
        record_id = document["record_id"]
        with self.state.locked():
            self.ready()
            for reference in self.references(document):
                self.resolve(reference["record_id"], reference["revision"])
            for run_id in document.get("run_ids", []):
                self.state.read_run(run_id)
            folder = self.state.path(f"research/records/{record_id}")
            versions = [int(path.stem[1:]) for path in folder.glob("v*.json")
                        if re.fullmatch(r"v[0-9]+", path.stem)]
            version = max(versions, default=0) + 1
            while (folder / f"v{version}").exists():
                version += 1
            revision = f"v{version}"
            relative = f"research/records/{record_id}/{revision}.json"
            target = self.state.path(relative)
            snapshot = self.state.path(f"research/records/{record_id}/{revision}")
            snapshot.mkdir(parents=True)
            items = [document["content"]]
            if document["kind"] == "source":
                items += document["metadata"]["locators"]
            if document["kind"] == "review":
                items += [document["metadata"]["target"]]
            materials = {}
            try:
                for item in items:
                    if item["path"] in materials:
                        continue
                    source = within(self.state.project, item["path"], exists=True)
                    if not source.is_file():
                        raise EvidenceError("invalid_research_content", "Research material must be a file.")
                    copy = snapshot / f"material-{len(materials)}{source.suffix[:16]}"
                    shutil.copyfile(source, copy)
                    materials[item["path"]] = str(copy.relative_to(self.state.root))
                self.state.write(relative, {"schema_version": 1, "revision": revision,
                                           "registered_at": now(), "document": document, "materials": materials})
            except Exception:
                # write() can fail during directory fsync after publishing JSON.
                # A published record must retain its material copies.
                if not target.exists():
                    shutil.rmtree(snapshot)
                raise
            try:
                self._write_index()
                derivation = "complete"
            except (OSError, EvidenceError, ValueError, KeyError, TypeError):
                derivation = "partial"
        return {"ok": True, "record_id": record_id, "revision": revision, "reused": False,
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
            copy = latest.get("materials", {}).get(document["content"]["path"])
            entries.append({"record_id": folder.name, "kind": document["kind"], "title": document["title"],
                            "revision": latest["revision"],
                            "content_path": str(self.state.path(copy)) if copy else document["content"]["path"],
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
                failures, limitations = self.material_issues(document, saved.get("materials"))
                if "materials" not in saved:
                    limitations.append("legacy_materials_not_snapshotted")
                for reference in self.references(document):
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
