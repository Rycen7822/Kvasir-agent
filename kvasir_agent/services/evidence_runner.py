"""One detached wrapper per run; it owns completion, timeout and cancellation."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time

from .evidence import EvidenceService
from .evidence_contracts import EvidenceError, read_json
from .metric import extract_metric_value, validate_metric_result
from .research_state import alive, digest, file_hash, now, process_identity, within


def terminate(identity):
    if not alive(identity):
        return False
    pid = identity["pid"]
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    deadline = time.monotonic() + 0.5
    while alive(identity) and time.monotonic() < deadline:
        time.sleep(0.02)
    # The leader may already be a zombie while descendants still hold pipes.
    # A PID cannot be reused until this wrapper reaps its direct child.
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return True


def execute(project, run_id):
    service = EvidenceService(project)
    state = service.state
    process = None
    forced = None
    try:
        with state.locked():
            service.ready()
            record = state.read_run(run_id)
            if record["status"] != "starting":
                return
            if record.get("worker") != process_identity(os.getpid()):
                raise EvidenceError("worker_identity_mismatch", "Unexpected worker instance.")
            spec, env = record["spec"], record["environment"]
            if digest({"spec": spec, "environment": env}) != record["request_digest"]:
                raise EvidenceError("request_digest_mismatch", "Request changed before execution.")
            service.validate_environment(env)
            run_dir = state.path(f"runs/{run_id}")
            if record.get("cancel_requested_at"):
                forced = "cancelled"
            else:
                process = subprocess.Popen(spec["command"], cwd=within(state.project, spec["cwd"], exists=True),
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    start_new_session=True, env={**os.environ, "KVASIR_RUN_DIR": str(run_dir),
                                                "KVASIR_RUN_ID": run_id, "KVASIR_SEED": str(spec["seed"])})
                record.update(status="running", process=process_identity(process.pid), started_at=now())
                state.write(f"runs/{run_id}/run.json", record)
        if process:
            started = time.monotonic()
            selector = selectors.DefaultSelector()
            truncated = False
            handles = []
            try:
                for stream, name in [(process.stdout, "stdout.log"), (process.stderr, "stderr.log")]:
                    handle = state.path(f"runs/{run_id}/{name}").open("wb")
                    handles.append(handle)
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_READ, [handle, 0])
                while True:
                    for key, _ in selector.select(timeout=0.05):
                        block = os.read(key.fileobj.fileno(), 65536)
                        if not block:
                            selector.unregister(key.fileobj)
                            continue
                        handle, count = key.data
                        available = max(0, spec["resources"]["max_log_bytes"] - count)
                        handle.write(block[:available])
                        key.data[1] += min(len(block), available)
                        truncated = truncated or len(block) > available
                    # Observe exit before cancellation so a late stop cannot
                    # overwrite an already completed run.
                    # Observe without reaping: retain ownership of this PID
                    # until the whole process group has been cleaned up.
                    if os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
                        break
                    current = state.read_run(run_id)
                    if current.get("cancel_requested_at"):
                        forced = "cancelled"
                    elif time.monotonic() - started > spec["resources"]["timeout_seconds"]:
                        forced = "timed_out"
                    if forced:
                        terminate(record["process"])
                        break
                # Close any descendants left in the owned process group.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
                for key in list(selector.get_map().values()):
                    while True:
                        try:
                            block = os.read(key.fileobj.fileno(), 65536)
                        except BlockingIOError:
                            break
                        if not block:
                            break
                        handle, count = key.data
                        available = max(0, spec["resources"]["max_log_bytes"] - count)
                        handle.write(block[:available])
                        key.data[1] += min(len(block), available)
                        truncated = truncated or len(block) > available
            finally:
                selector.close()
                for handle in handles:
                    handle.close()
                process.stdout.close()
                process.stderr.close()
            record["logs_truncated"] = truncated
        record.update(status=forced or ("completed" if process and process.returncode == 0 else "failed"),
                      exit_code=process.returncode if process else None, finished_at=now(),
                      evidence_status="invalid", artifacts=[])
        if record["status"] == "completed":
            service.validate_environment(record["environment"])
            for output in sorted(set([spec["metrics_path"], *spec["outputs"]])):
                path = within(run_dir, output, exists=True)
                record["artifacts"].append({"path": output, "sha256": file_hash(path)})
            metric = extract_metric_value(read_json(within(run_dir, spec["metrics_path"], exists=True)), env["primary_metric"])
            if not metric["ok"]:
                raise EvidenceError(metric["error_type"], "Run metric is invalid.")
            valid = validate_metric_result(env["primary_metric"], value=metric["value"], artifacts=spec["outputs"])
            if not valid["ok"]:
                raise EvidenceError(valid["error_type"], "Run metric violates its contract.")
            record.update(metric=metric["value"], evidence_status="verified")
    except Exception as exc:
        if process and process.returncode is None:
            terminate(process_identity(process.pid))
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
        record = state.read_run(run_id)
        record.update(status=forced or "failed", finished_at=now(), evidence_status="invalid",
                      exit_code=process.returncode if process else None,
                      error_type=exc.kind if isinstance(exc, EvidenceError) else "execution_error")
    with state.locked():
        # Retain stop provenance, while the wrapper owns the actual terminal fact.
        current = state.read_run(run_id)
        if current.get("cancel_requested_at"):
            record["cancel_requested_at"] = current["cancel_requested_at"]
        if current["status"] in {"cancelled", "interrupted"}:
            return
        record["derivation_status"] = "partial"
        state.write(f"runs/{run_id}/run.json", record)
        try:
            service.derive(record)
            record["derivation_status"] = "complete"
        except (OSError, EvidenceError):
            pass
        state.write(f"runs/{run_id}/run.json", record)
