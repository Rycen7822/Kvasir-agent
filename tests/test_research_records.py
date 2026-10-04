import json
from pathlib import Path
import subprocess
import sys

from kvasir_agent.services.evidence import EvidenceService
from kvasir_agent.services.research_records import ResearchRecords
from kvasir_agent.services.research_state import now
from test_evidence_v3 import project, write, legacy
from kvasir_agent.services.explicit_migration import Migration

ROOT = Path(__file__).resolve().parents[1]


def document(root, kind, record_id, metadata, dependencies=()):
    content = root / f"{record_id}.md"
    content.write_text("Saved research content.\n")
    return {"schema_version": 1, "record_id": record_id, "kind": kind, "title": record_id,
            "content": {"path": content.name},
            "dependencies": list(dependencies), "metadata": metadata}


def register(root, records, doc):
    path = f"{doc['record_id']}.json"
    write(root / path, doc)
    return records.register(path)


def reference(result):
    return {"record_id": result["record_id"], "revision": result["revision"]}


def test_saved_candidate_claim_and_review_versions(project):
    root, state, _ = project
    records = ResearchRecords(str(root))
    candidate = document(root, "candidate", "candidate", {"method_id": "base", "files": [{"path": "evaluate.py"}], "parents": [], "rationale": "Test one change."})
    saved_candidate = register(root, records, candidate)
    claim = document(root, "claim", "claim", {"statement": "The experiment supports the hypothesis.", "limitations": "One task.", "status": "proposal"}, [reference(saved_candidate)])
    saved_claim = register(root, records, claim)
    review = document(root, "review", "review", {"target": claim["content"], "reviewer": "human-declared", "outcome": "partial", "issues": [], "unresolved": ["Replication pending."]}, [reference(saved_claim)])
    saved_review = register(root, records, review)
    assert records.inspect(["review"])[0] == []
    assert saved_review["revision"] == "v1"
    candidate["metadata"]["rationale"] = "Revised rationale."
    updated = register(root, records, candidate)
    assert updated["revision"] != saved_candidate["revision"]
    issues, rows = records.inspect(["review"])
    assert issues == []
    assert Path(saved_candidate["record_path"]).exists()
    (root / "claim.md").write_text("Edited conclusion.\n")
    assert records.inspect(["review"])[0] == []
    saved = records.resolve("claim", saved_claim["revision"])
    assert state.path(saved["materials"]["claim.md"]).read_text() == "Saved research content.\n"


def test_source_receipt_distinguishes_query_coverage_and_actual_excerpt(project):
    root, state, _ = project
    records = ResearchRecords(str(root))
    (root / "paper.txt").write_text("First line.\nEvidence lives here.\n")
    metadata = {"source_id": "arxiv:1234", "version": "v2", "url": "https://example.org/paper", "retrieved_at": now(),
                "submitted_query": "strict query", "effective_query": "broader query", "coverage": {"mode": "abstract", "truncated": True},
                "locators": [{"kind": "lines", "path": "paper.txt", "start": 2, "end": 2, "excerpt": "Evidence lives here."}]}
    source = document(root, "source", "paper", metadata)
    register(root, records, source)
    (root / "paper.txt").write_text("First line.\nUpdated live material.\n")
    failures, rows = records.inspect(["paper"])
    assert not failures
    assert {"source_coverage:abstract", "source_truncated", "query_changed"} <= set(rows[0]["limitations"])
    source["metadata"]["locators"][0]["excerpt"] = "A made-up quote."
    register(root, records, source)
    assert any("locator_excerpt_mismatch" in issue for issue in records.inspect(["paper"])[0])


def test_index_failure_preserves_record_then_explicit_reindex_recovers(project, monkeypatch):
    root, state, _ = project
    records = ResearchRecords(str(root))
    doc = document(root, "negative_result", "negative", {"observation": "No improvement.", "scope": "This configuration.", "explanation": "Mechanism remains uncertain."})
    original = records._write_index
    monkeypatch.setattr(records, "_write_index", lambda: (_ for _ in ()).throw(OSError("disk failure")))
    result = register(root, records, doc)
    assert result["derivation_status"] == "partial" and Path(result["record_path"]).exists()
    monkeypatch.setattr(records, "_write_index", original)
    assert records.reindex()["records"] == 1
    index = json.loads(Path(result["index_path"]).read_text())
    assert Path(index["entries"][0]["content_path"]).read_text() == "Saved research content.\n"


def test_explicit_index_discovers_preserved_migration_paths(tmp_path):
    state = legacy(tmp_path, multiple=True)
    migration = Migration(state)
    migration.apply(migration.plan())
    result = ResearchRecords(str(tmp_path)).reindex()
    assert result["legacy_paths"] > 0
    index = json.loads(Path(result["index_path"]).read_text())
    assert all(Path(x["archived_path"]).exists() for x in index["legacy_paths"])
    assert all(x["trust"] == "legacy_unverified" for x in index["legacy_paths"])


def test_research_cli_and_mcp_check_share_explicit_project(project):
    root, state, _ = project
    records = ResearchRecords(str(root))
    doc = document(root, "negative_result", "negative", {"observation": "Failure.", "scope": "One test.", "explanation": "Unknown."})
    write(root / "negative.json", doc)
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/ka_admin.py"), "research-register", "--project", str(root), "--spec-path", "negative.json"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    write(root / "check.json", {"schema_version": 2, "target": "research", "record_ids": ["negative"]})
    assert EvidenceService(str(root)).check("check.json")["ok"]


def test_concurrent_research_registration_keeps_all_authority_and_index_entries(project):
    from concurrent.futures import ThreadPoolExecutor
    root, state, _ = project
    paths = []
    for index in range(8):
        doc = document(root, "negative_result", f"negative-{index}", {"observation": "No improvement.", "scope": "One trial.", "explanation": "Unknown."})
        paths.append(write(root / f"negative-{index}.json", doc))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda path: ResearchRecords(str(root)).register(path), paths))
    assert all(result["derivation_status"] == "complete" for result in results)
    index = json.loads(state.path("research/index.json").read_text())
    assert len(index["entries"]) == 8
    assert len({entry["record_id"] for entry in index["entries"]}) == 8
