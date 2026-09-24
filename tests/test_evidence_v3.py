from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from kvasir_agent.mcp.server import handle_jsonrpc_message
from kvasir_agent.mcp.tool_registry import call_tool, tools_list_payload
from kvasir_agent.services.evidence import EvidenceService
from kvasir_agent.services.evidence_contracts import EvidenceError
from kvasir_agent.services.explicit_migration import Migration
from kvasir_agent.services.research_state import ResearchState, alive, file_hash

ROOT = Path(__file__).resolve().parents[1]


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return str(path)


def snapshot(root):
    return {str(p.relative_to(root)): (p.is_dir(), p.stat().st_mtime_ns,
            p.read_bytes() if p.is_file() else None) for p in root.rglob("*")}


@pytest.fixture
def project(tmp_path):
    state = ResearchState(str(tmp_path))
    state.initialize()
    (tmp_path / "evaluate.py").write_text("# pinned evaluator\n")
    (tmp_path / "data.txt").write_text("fixed data\n")
    env = {"schema_version": 1, "env_id": "toy", "baseline": {"repo_path": "."},
           "protected_files": [{"path": "evaluate.py", "sha256": file_hash(tmp_path / "evaluate.py")}],
           "datasets": [{"path": "data.txt", "sha256": file_hash(tmp_path / "data.txt")}],
           "primary_metric": {"name": "score", "direction": "maximize", "parser": "flat_key", "path": "score"}}
    write(tmp_path / "environment.json", env)
    code = "import os,json,pathlib; p=pathlib.Path(os.environ['KVASIR_RUN_DIR']); (p/'metrics.json').write_text(json.dumps({'score':0.75}))"
    spec = {"schema_version": 1, "purpose": "baseline", "command": [sys.executable, "-c", code],
            "cwd": ".", "environment_path": "environment.json", "method_id": "base", "seed": 1,
            "resources": {"timeout_seconds": 10, "max_log_bytes": 4096},
            "metrics_path": "metrics.json", "outputs": ["metrics.json"]}
    write(tmp_path / "run.json", spec)
    return tmp_path, state, spec


def finish(state, run_id, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = state.read_run(run_id)
        if record["status"] in {"completed", "failed", "cancelled", "timed_out", "interrupted"} and (record.get("derivation_status") == "complete" or not alive(record.get("worker"))):
            return record
        time.sleep(.05)
    raise AssertionError(state.read_run(run_id))


def start(project, key="one"):
    root, state, _ = project
    result = call_tool("ka_experiment_run", {"project": str(root), "spec_path": "run.json", "idempotency_key": key})
    assert result["ok"], result
    return result["run_id"]


def test_discovery_and_missing_project_never_write(tmp_path):
    before = snapshot(tmp_path)
    tools = tools_list_payload()["tools"]
    assert len(tools) == 5
    assert sum(t["annotations"]["readOnlyHint"] for t in tools) == 1
    assert not any("init" in t["description"] for t in tools)
    for name, args in [
        ("ka_research_status", {}), ("ka_experiment_run", {"spec_path": "missing.json", "idempotency_key": "x"}),
        ("ka_evidence_import", {"manifest_path": "missing.json"}), ("ka_evidence_check", {"spec_path": "missing.json"}),
        ("ka_experiment_stop", {"run_id": "r_one"}), ("ka_literature", {}), ("ka_project_init", {}),
    ]:
        result = call_tool(name, {"project": str(tmp_path), **args})
        assert not result["ok"]
        assert "manual/" not in json.dumps(result)
    assert snapshot(tmp_path) == before


def test_minimal_concurrent_init_and_readonly_status(tmp_path):
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: ResearchState(str(tmp_path)).initialize(), range(4)))
    assert len({r["project_id"] for r in results}) == 1
    files = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert files == ["Kvasir-agent/events/events.jsonl", "Kvasir-agent/events/write.lock", "Kvasir-agent/research.yaml"]
    before = snapshot(tmp_path)
    assert not ResearchState(str(tmp_path)).initialize()["created"]
    for _ in range(3):
        assert call_tool("ka_research_status", {"project": str(tmp_path)})["ok"]
    assert snapshot(tmp_path) == before


def test_bad_events_report_only_then_explicit_repair(project):
    root, state, _ = project
    with state.path("events/events.jsonl").open("a") as f:
        f.write("broken\n")
    before = snapshot(root)
    status = EvidenceService(str(root)).status()
    assert status["invalid_event_lines"] == [2]
    assert snapshot(root) == before
    result = state.repair_events()
    assert result["repaired_lines"] == 1
    assert Path(result["backup"]).read_text().endswith("broken\n")


def test_success_idempotency_and_claims_use_real_runs(project):
    root, state, spec = project
    run_id = start(project)
    record = finish(state, run_id)
    assert (record["status"], record["evidence_status"], record["metric"]) == ("completed", "verified", .75)
    assert state.path(f"runs/{run_id}/result.json").exists()
    assert start(project) == run_id
    spec["seed"] = 2
    write(root / "run.json", spec)
    result = call_tool("ka_experiment_run", {"project": str(root), "spec_path": "run.json", "idempotency_key": "one"})
    assert result["error_type"] == "idempotency_conflict"
    write(root / "check.json", {"schema_version": 1, "target": "claim", "claim": "toy", "run_ids": [run_id], "minimum_seeds": 2})
    checked = EvidenceService(str(root)).check("check.json")
    assert not checked["ok"] and "insufficient_observed_seeds" in checked["issues"]
    assert checked["scientific_validity"] == "not_assessed"
    before = snapshot(root)
    assert EvidenceService(str(root)).status(run_id)["status"] == "completed"
    assert snapshot(root) == before
    assert EvidenceService(str(root)).stop(run_id)["status"] == "completed"


def test_concurrent_same_key_starts_one_process(project):
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: start(project, "concurrent"), range(4)))
    assert len(set(ids)) == 1
    assert finish(project[1], ids[0])["status"] == "completed"


@pytest.mark.parametrize("change", ["protected", "traversal", "symlink", "baseline", "unknown_field"])
def test_preflight_rejects_without_creating_runs(project, change):
    root, state, spec = project
    if change == "protected":
        (root / "evaluate.py").write_text("changed")
    elif change == "traversal":
        spec["outputs"] = ["../outside"]
    elif change == "symlink":
        (root / "outside").symlink_to(root.parent, target_is_directory=True)
        spec["cwd"] = "outside"
    elif change == "baseline":
        spec.update(purpose="experiment", baseline_run_id="missing")
    else:
        spec["trusted"] = True
    write(root / "run.json", spec)
    result = call_tool("ka_experiment_run", {"project": str(root), "spec_path": "run.json", "idempotency_key": "x"})
    assert not result["ok"]
    assert not state.path("runs").exists()


@pytest.mark.parametrize("mode,expected", [("failure", "failed"), ("bad_metric", "failed"), ("tamper", "failed"),
                                            ("timeout", "timed_out"), ("cancel", "cancelled")])
def test_failure_timeout_cancel_and_evaluator_tamper(project, mode, expected):
    root, state, spec = project
    code = {"failure": "raise SystemExit(4)", "bad_metric": spec["command"][2].replace("0.75", "float('nan')"),
            "tamper": spec["command"][2] + ";pathlib.Path('evaluate.py').write_text('tampered')",
            "timeout": "import time; time.sleep(20)", "cancel": "import time; time.sleep(20)"}[mode]
    spec["command"] = [sys.executable, "-c", code]
    if mode == "timeout":
        spec["resources"]["timeout_seconds"] = .1
    write(root / "run.json", spec)
    run_id = start(project)
    if mode == "cancel":
        EvidenceService(str(root)).stop(run_id)
    record = finish(state, run_id)
    assert record["status"] == expected, record
    assert record["evidence_status"] == "invalid"


def test_connection_exit_does_not_prevent_completion(project):
    root, state, _ = project
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ka_experiment_run",
               "arguments": {"project": str(root), "spec_path": "run.json", "idempotency_key": "disconnect"}}}
    output = subprocess.run([sys.executable, str(ROOT / "scripts/ka_mcp.py")], input=json.dumps(request) + "\n",
                            capture_output=True, text=True, timeout=10, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    result = json.loads(output.stdout)["result"]
    assert set(result) == {"structuredContent", "content", "isError"}
    run_id = result["structuredContent"]["run_id"]
    assert finish(state, run_id)["evidence_status"] == "verified"


def test_external_import_is_unverified_and_idempotent(project):
    root, state, _ = project
    write(root / "external.json", {"score": .9})
    manifest = {"schema_version": 1, "origin": {"type": "external_run", "source": "lab", "run_id": "external-1"},
                "environment_path": "environment.json", "method_id": "external", "seed": 3,
                "metrics_path": "external.json", "artifacts": [{"path": "external.json", "sha256": file_hash(root / "external.json")}]}
    write(root / "import.json", manifest)
    service = EvidenceService(str(root))
    result = service.import_evidence("import.json")
    assert result["trust"] == "external_unverified"
    assert result["derivation_status"] == "complete"
    assert service.import_evidence("import.json")["import_id"] == result["import_id"]
    manifest["trusted"] = True
    write(root / "import.json", manifest)
    with pytest.raises(EvidenceError, match="Invalid import"):
        service.import_evidence("import.json")


def test_changed_artifact_fails_run_check(project):
    root, state, _ = project
    run_id = start(project)
    finish(state, run_id)
    state.path(f"runs/{run_id}/metrics.json").write_text('{"score":999}')
    write(root / "check.json", {"schema_version": 1, "target": "run", "run_id": run_id})
    result = EvidenceService(str(root)).check("check.json")
    assert not result["ok"]
    assert any("artifact_hash_mismatch" in issue for issue in result["issues"])


def legacy(root, multiple=False):
    state = ResearchState(str(root))
    for q in ["A", "B"] if multiple else ["A"]:
        prefix = f"quests/{q}"
        write(state.path(f"{prefix}/quest.yaml"), {"quest_id": q, "goal": {"title": "old"}})
        write(state.path(f"{prefix}/runtime/goal_state.json"), {"stage": "do not reactivate"})
        write(state.path(f"{prefix}/runs/R1/run.json"), {"run_id": "R1", "status": "completed", "notes": "R1 unchanged prose"})
    return state


def test_multiple_quest_migration_preserves_sources_and_inactive_controllers(tmp_path):
    state = legacy(tmp_path, multiple=True)
    before = snapshot(tmp_path)
    migration = Migration(state)
    plan = migration.plan()
    assert snapshot(tmp_path) == before
    assert len({r["run_id"] for r in plan["runs"]}) == 2
    result = migration.apply(plan)
    assert result["ok"] and result["runs_migrated"] == 2
    assert state.read_manifest()["schema_version"] == 3
    assert not state.path("runtime/goal_state.json").exists()
    for name, (_, _, contents) in before.items():
        if contents is not None:
            assert (tmp_path / name).read_bytes() == contents
    for mapped in plan["runs"]:
        record = state.read_run(mapped["run_id"])
        assert record["trust"] == "legacy_unverified"
        assert record["legacy_record"]["notes"] == "R1 unchanged prose"
    assert migration.apply(plan)["status"] == "already_applied"


def test_migration_conflict_never_partially_copies(tmp_path):
    state = legacy(tmp_path)
    path = state.path("quests/A/runs/R1/run.json")
    write(path, {"run_id": "R1", "status": "running"})
    before = snapshot(tmp_path)
    plan = Migration(state).plan()
    assert plan["conflicts"]
    with pytest.raises(EvidenceError, match="conflicts"):
        Migration(state).apply(plan)
    assert snapshot(tmp_path) == before


def test_migration_resume_after_copy_interruption(tmp_path, monkeypatch):
    state = legacy(tmp_path)
    migration = Migration(state)
    plan = migration.plan()
    import kvasir_agent.services.explicit_migration as module
    original = module.shutil.copyfile
    count = 0
    def broken(*args):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("interrupted copy")
        return original(*args)
    monkeypatch.setattr(module.shutil, "copyfile", broken)
    with pytest.raises(OSError):
        migration.apply(plan)
    assert call_tool("ka_research_status", {"project": str(tmp_path)})["error_type"] == "migration_pending"
    monkeypatch.setattr(module.shutil, "copyfile", original)
    assert migration.apply(plan)["ok"]
    assert not state.path("migrations/pending.json").exists()


def test_bounded_errors_and_invalid_rpc_arguments(tmp_path):
    response = handle_jsonrpc_message({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                      "params": {"name": "ka_research_status", "arguments": "x" * 100000}})
    assert len(json.dumps(response)) < 1000
    assert response["result"]["isError"]


def test_real_v2_runner_layout_and_mixed_quest_migration(tmp_path):
    from kvasir_agent.services.manifest import ManifestService
    from kvasir_agent.services.project_state import ProjectLayout
    from kvasir_agent.services.runner import RunnerService
    layout = ProjectLayout.from_project_root(tmp_path)
    ManifestService(layout).init(name="old", goal="preserve evidence")
    old = RunnerService(layout).start(command="echo old", dry_run=True)["run"]
    Path(old["log_path"]).write_text("R0001 original text\n")
    state = legacy(tmp_path, multiple=True)
    plan = Migration(state).plan()
    assert len(plan["runs"]) == 3
    assert Migration(state).apply(plan)["ok"]
    mapped = next(r for r in plan["runs"] if r["source"] == "runs/R0001/runner.json")
    record = state.read_run(mapped["run_id"])
    assert Path(record["legacy_record"]["log_path"]).read_text() == "R0001 original text\n"
    assert record["legacy_record"]["run_id"] == mapped["run_id"]
    assert EvidenceService(str(tmp_path)).status(mapped["run_id"])["status"] == "imported"


def test_migration_rejects_stale_and_future_or_corrupt_inputs(tmp_path):
    state = legacy(tmp_path)
    plan = Migration(state).plan()
    state.path("quests/A/extra.txt").write_text("new material")
    before = snapshot(tmp_path)
    with pytest.raises(EvidenceError, match="changed"):
        Migration(state).apply(plan)
    assert snapshot(tmp_path) == before
    state.manifest.write_text('{"schema_version": 999}')
    with pytest.raises(EvidenceError, match="Only v1/v2"):
        Migration(state).plan()
    state.manifest.write_text("[broken")
    with pytest.raises(EvidenceError, match="cannot be parsed"):
        Migration(state).plan()


def test_real_experiment_requires_matching_baseline(project):
    root, state, spec = project
    baseline = start(project)
    finish(state, baseline)
    spec.update(purpose="experiment", baseline_run_id=baseline, method_id="improved")
    write(root / "run.json", spec)
    experiment = start(project, "experiment")
    assert finish(state, experiment)["evidence_status"] == "verified"
    write(root / "check.json", {"schema_version": 1, "target": "claim", "claim": "toy", "run_ids": [experiment], "minimum_seeds": 1})
    assert EvidenceService(str(root)).check("check.json")["ok"]
    state.path(f"runs/{baseline}/metrics.json").write_text('{"score":100}')
    checked = EvidenceService(str(root)).check("check.json")
    assert not checked["ok"]
    assert any("baseline_evidence_invalid" in issue for issue in checked["issues"])


def test_interrupted_worker_reports_readonly_then_explicit_stop(project):
    import signal
    from kvasir_agent.services.research_state import alive
    root, state, spec = project
    spec["command"] = [sys.executable, "-c", "import time; time.sleep(30)"]
    write(root / "run.json", spec)
    run_id = start(project)
    deadline = time.monotonic() + 5
    while state.read_run(run_id)["status"] != "running" and time.monotonic() < deadline:
        time.sleep(.05)
    record = state.read_run(run_id)
    assert record["status"] == "running"
    try:
        os.kill(record["worker"]["pid"], signal.SIGKILL)
        time.sleep(.1)
        before = snapshot(root)
        assert EvidenceService(str(root)).status(run_id)["status"] == "interrupted"
        assert snapshot(root) == before
        stopped = EvidenceService(str(root)).stop(run_id)
        assert stopped["status"] == "interrupted"
        assert not alive(record["process"])
        assert EvidenceService(str(root)).reconcile(run_id)["status"] == "interrupted"
    finally:
        from kvasir_agent.services.evidence_runner import terminate
        terminate(record.get("process"))


def test_partial_import_derivation_can_retry_without_duplicate_events(project, monkeypatch):
    root, state, _ = project
    write(root / "external.json", {"score": .5})
    manifest = {"schema_version": 1, "origin": {"type": "external_run", "source": "lab", "run_id": "x"},
                "environment_path": "environment.json", "method_id": "external", "seed": 1,
                "metrics_path": "external.json", "artifacts": [{"path": "external.json", "sha256": file_hash(root / "external.json")}]}
    write(root / "import.json", manifest)
    service = EvidenceService(str(root))
    original = service.state.write
    def broken(path, data):
        if path.endswith("result.json"):
            raise OSError("disk failure")
        return original(path, data)
    monkeypatch.setattr(service.state, "write", broken)
    first = service.import_evidence("import.json")
    assert first["derivation_status"] == "partial"
    monkeypatch.setattr(service.state, "write", original)
    second = service.import_evidence("import.json")
    assert first["import_id"] == second["import_id"]
    assert second["derivation_status"] == "complete"
    assert sum(e["event_type"] == "evidence.imported" for e in state.events()[0]) == 1


def test_many_runs_and_large_invalid_spec_return_bounded_summaries(project):
    root, state, spec = project
    run_id = start(project)
    record = finish(state, run_id)
    for n in range(30):
        clone = dict(record, run_id=f"z_{n:04}")
        state.write(f"runs/{clone['run_id']}/run.json", clone)
    result = EvidenceService(str(root)).status()
    assert len(result["runs"]) == 5 and result["omitted_runs"] == 26
    assert len(json.dumps(result, ensure_ascii=False)) < 2500
    spec["command"] = ["错误" * 10000]
    write(root / "run.json", spec)
    result = call_tool("ka_experiment_run", {"project": str(root), "spec_path": "run.json", "idempotency_key": "big"})
    assert not result["ok"] and len(json.dumps(result)) < 500


def test_failed_run_derivation_is_explicitly_recoverable(project):
    root, state, spec = project
    spec["command"][2] = "import time; time.sleep(.5); " + spec["command"][2]
    write(root / "run.json", spec)
    run_id = start(project)
    blocker = state.path(f"runs/{run_id}/result.json")
    blocker.mkdir()
    record = finish(state, run_id)
    assert record["status"] == "completed" and record["derivation_status"] == "partial"
    blocker.rmdir()
    EvidenceService(str(root)).reconcile(run_id)
    EvidenceService(str(root)).reconcile(run_id)
    assert state.read_run(run_id)["derivation_status"] == "complete"
    assert sum(e["event_type"] == "run.finished" for e in state.events()[0]) == 1


def test_wrapper_cleans_descendants_after_command_exits(project):
    root, state, spec = project
    child = "import time,pathlib; time.sleep(.7); pathlib.Path('orphan-marker').write_text('leaked')"
    spec["command"][2] = "import subprocess; subprocess.Popen(" + repr([sys.executable, "-c", child]) + "); " + spec["command"][2]
    write(root / "run.json", spec)
    run_id = start(project)
    assert finish(state, run_id)["status"] == "completed"
    time.sleep(.8)
    assert not (root / "orphan-marker").exists()


def test_migration_resumes_after_commit_before_pending_cleanup(tmp_path, monkeypatch):
    state = legacy(tmp_path)
    migration = Migration(state)
    plan = migration.plan()
    pending = state.path("migrations/pending.json")
    original = Path.unlink
    def interrupted(path, *args, **kwargs):
        if path == pending:
            raise OSError("crash at final cleanup")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", interrupted)
    with pytest.raises(OSError):
        migration.apply(plan)
    assert pending.exists()
    assert state.read_manifest(pending_ok=True)["schema_version"] == 3
    monkeypatch.setattr(Path, "unlink", original)
    assert migration.apply(plan)["status"] == "already_applied"
    assert not pending.exists()
    assert state.read_manifest()["schema_version"] == 3


def test_migration_rechecks_early_sources_before_commit(tmp_path, monkeypatch):
    state = legacy(tmp_path)
    migration = Migration(state)
    plan = migration.plan()
    import kvasir_agent.services.explicit_migration as module
    original = module.shutil.copyfile
    changed = None
    previous = None
    def copying(source, dest):
        nonlocal changed, previous
        result = original(source, dest)
        if changed is None:
            changed = source
            previous = source.read_bytes()
            source.write_bytes(previous + b"\n")
        return result
    monkeypatch.setattr(module.shutil, "copyfile", copying)
    with pytest.raises(EvidenceError, match="during staging"):
        migration.apply(plan)
    assert not state.manifest.exists()
    assert not any(state.path(r["destination"]).exists() for r in plan["runs"])
    changed.write_bytes(previous)
    monkeypatch.setattr(module.shutil, "copyfile", original)
    assert migration.apply(plan)["ok"]


def test_interleaved_projects_ignore_ambient_routing(project, monkeypatch):
    root, state, _ = project
    other = root / "other-project"
    other.mkdir()
    other_state = ResearchState(str(other))
    other_state.initialize()
    ambient_home = root / "old-home"
    monkeypatch.setenv("KVASIR_AGENT_HOME", str(ambient_home))
    monkeypatch.setenv("KVASIR_AGENT_PROJECT_ROOT", str(other))
    before = snapshot(other)
    run_id = start(project)
    assert call_tool("ka_research_status", {"project": str(other)})["project_id"] == other_state.read_manifest()["project_id"]
    assert not call_tool("ka_research_status", {"project": str(other), "run_id": run_id})["ok"]
    assert finish(state, run_id)["evidence_status"] == "verified"
    assert call_tool("ka_research_status", {"project": str(root)})["project_id"] == state.read_manifest()["project_id"]
    assert snapshot(other) == before
    assert not ambient_home.exists()
