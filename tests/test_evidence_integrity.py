"""Fault probes for saved evidence, independent of saved verified labels."""
import json
from pathlib import Path

import pytest

from kvasir_agent.services.evidence import EvidenceService
from kvasir_agent.services.evidence_contracts import EvidenceError
from kvasir_agent.services.research_state import file_hash
from test_evidence_v3 import project, start, finish, write


def test_reparse_saved_metric_without_changing_hashed_artifact(project):
    root, state, _ = project
    run_id = start(project)
    record = finish(state, run_id)
    record["metric"] = 42
    state.write(f"runs/{run_id}/run.json", record)
    write(root / "check.json", {"schema_version": 1, "target": "run", "run_id": run_id})
    checked = EvidenceService(str(root)).check("check.json")
    assert any("metric_value_mismatch" in x for x in checked["issues"])
    assert EvidenceService(str(root)).status(run_id)["integrity_check"] == "not_performed"


def imported(project):
    root, state, _ = project
    write(root / "external.json", {"score": .9})
    manifest = {"schema_version": 1, "origin": {"type": "external_run", "source": "lab", "run_id": "outside"},
                "environment_path": "environment.json", "method_id": "external", "seed": 3,
                "metrics_path": "external.json", "artifacts": [{"path": "external.json", "sha256": file_hash(root / "external.json")}]}
    write(root / "import.json", manifest)
    service = EvidenceService(str(root))
    return root, state, service, service.import_evidence("import.json")


@pytest.mark.parametrize("fault", ["bytes", "missing", "saved_metric", "identity"])
def test_idempotent_import_rechecks_saved_target(project, fault):
    root, state, service, result = imported(project)
    folder = state.path(f"artifacts/imports/{result['import_id']}")
    record = json.loads((folder / "record.json").read_text())
    if fault == "bytes":
        (folder / "artifact-0").write_text('{"score": 0}')
    elif fault == "missing":
        (folder / "artifact-0").unlink()
    else:
        record["metric" if fault == "saved_metric" else "trust"] = 100 if fault == "saved_metric" else "managed_local"
        (folder / "record.json").write_text(json.dumps(record))
    with pytest.raises(EvidenceError) as exc:
        service.import_evidence("import.json")
    assert exc.value.kind == "import_integrity_failed"
    write(root / "check.json", {"schema_version": 2, "target": "import", "import_id": result["import_id"]})
    assert not service.check("check.json")["ok"]


def test_import_check_uses_saved_bytes_when_original_is_gone(project):
    root, state, service, result = imported(project)
    (root / "external.json").unlink()
    write(root / "check.json", {"schema_version": 2, "target": "import", "import_id": result["import_id"]})
    checked = service.check("check.json")
    assert checked["ok"]
    report = json.loads(Path(checked["report_path"]).read_text())
    assert report["evidence"][0]["trust"] == "external_unverified"
    assert report["integrity_check"] == "fresh"
    assert report["scientific_validity"] == "not_assessed"
