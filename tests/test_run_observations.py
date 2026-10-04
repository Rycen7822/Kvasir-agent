import json
from datetime import datetime, timezone

import pytest

from kvasir_agent.services.evidence import EvidenceService
from kvasir_agent.services.evidence_contracts import EvidenceError
from kvasir_agent.services.research_state import file_hash
from test_evidence_v3 import project, finish, write, start


def test_real_run_observations_separate_published_applied_and_cost_basis(project):
    root, state, spec = project
    code = spec["command"][-1] + ";from datetime import datetime,timezone; (p/'progress.json').write_text(json.dumps({'schema_version':1,'run_id':os.environ['KVASIR_RUN_ID'],'updated_at':datetime.now(timezone.utc).isoformat(),'phase':'eval','step':2,'total':3,'versions':{'published':'v2','applied':'v1'}})); (p/'cost.json').write_text(json.dumps({'schema_version':1,'run_id':os.environ['KVASIR_RUN_ID'],'entries':[{'resource':'tokens','unit':'tokens','basis':'estimated','value':12,'scope':'run'},{'resource':'gpu_seconds','unit':'seconds','basis':'unknown','value':None,'scope':'search'}]}))"
    spec.update(schema_version=2, progress_path="progress.json", cost_path="cost.json", command=[spec["command"][0], "-c", code])
    write(root / "run.json", spec)
    run_id = start(project)
    record = finish(state, run_id)
    service = EvidenceService(str(root))
    status = service.status(run_id)
    assert status["status"] == "completed"
    assert status["elapsed_seconds"] > 0 and status["exit_code"] == 0
    observed = status["observations"]
    assert observed["progress"]["versions"] == {"published": "v2", "applied": "v1"}
    assert observed["progress"]["liveness"] == "not_assessed"
    assert observed["cost"]["entries"][0]["basis"] == "estimated"
    assert observed["cost"]["entries"][1]["value"] is None
    assert record["observations_snapshot"]["cost"]["managed_wall_basis"] == "observed"
    progress = state.path(f"runs/{run_id}/progress.json")
    data = json.loads(progress.read_text()); data["step"] = 3; progress.write_text(json.dumps(data))
    assert service.status(run_id)["observations"]["progress"]["changed_since_completion"]
    data["updated_at"] = "2000-01-01T00:00:00+00:00"; progress.write_text(json.dumps(data))
    assert service.status(run_id)["observations"]["progress"]["status"] == "stale"


def test_invalid_progress_does_not_block_stop_or_change_liveness(project):
    root, state, spec = project
    code = spec["command"][-1] + ";import time; (p/'progress.json').write_text('broken');time.sleep(10)"
    spec.update(schema_version=2, progress_path="progress.json", command=[spec["command"][0], "-c", code])
    write(root / "run.json", spec)
    run_id = start(project)
    state.path(f"runs/{run_id}/progress.json").write_text("broken")
    service = EvidenceService(str(root))
    assert service.status(run_id)["observations"]["progress"]["status"] == "unavailable_or_invalid"
    result = service.stop(run_id)
    assert result["status"] in {"cancelled", "interrupted"}
    assert not state.read_run(run_id).get("observations_snapshot", {}).get("progress", {}).get("liveness") == "alive"


def test_oversized_progress_is_rejected_before_unbounded_hashing(project):
    root, state, spec = project
    spec.update(schema_version=2, progress_path="progress.json")
    write(root / "run.json", spec)
    run_id = start(project)
    finish(state, run_id)
    path = state.path(f"runs/{run_id}/progress.json")
    with path.open("wb") as stream:
        stream.truncate(1024 ** 3)
    with pytest.raises(EvidenceError) as exc:
        file_hash(path, limit=65536)
    assert exc.value.kind == "invalid_file"
    status = EvidenceService(str(root)).status(run_id)
    assert status["status"] == "completed"
    assert status["observations"]["progress"]["status"] == "unavailable_or_invalid"
    assert EvidenceService(str(root)).stop(run_id)["status"] == "completed"


def test_recent_status_orders_actual_time_instead_of_legacy_id(project):
    root, state, spec = project
    run_id = start(project)
    record = finish(state, run_id)
    for identifier, created in [("z_old", "2000-01-01T00:00:00+00:00"), ("a_new", "2099-01-01T00:00:00+00:00")]:
        state.write(f"runs/{identifier}/run.json", {**record, "run_id": identifier, "created_at": created})
    status = EvidenceService(str(root)).status()
    assert status["runs"][0]["run_id"] == "a_new"
    assert status["research_index_path"].endswith("research/index.json")


@pytest.mark.parametrize("path", ["run.json", "../escape.json"])
def test_observation_paths_cannot_overwrite_control_state(project, path):
    root, state, spec = project
    spec.update(schema_version=2, progress_path=path)
    write(root / "run.json", spec)
    with pytest.raises(EvidenceError):
        EvidenceService(str(root)).run("run.json", "bad")
    assert not state.path("runs").exists()
