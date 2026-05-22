from __future__ import annotations

import hashlib
import json
from pathlib import Path

from codex_scientist.services.event_store import EventStore
from codex_scientist.services.project_state import ProjectLayout


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_manifest(project_root: Path, quest_id: str = "QENV") -> dict:
    (project_root / "evaluate.py").write_text("print('eval')\n", encoding="utf-8")
    data_path = project_root / "MATH" / "test.jsonl"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text("{}\n", encoding="utf-8")
    return {
        "schema_version": 1,
        "env_id": "env_toy",
        "quest_id": quest_id,
        "title": "Toy environment",
        "problem": "Validate toy metric",
        "baseline": {
            "repo_path": ".",
            "commit": "local-snapshot",
            "baseline_id": "baseline_main",
            "baseline_metric": {"name": "eval/mean_reward", "value": 0.5, "direction": "maximize"},
        },
        "mutable_allowlist": ["train.py"],
        "protected_files": [{"path": "evaluate.py", "sha256": _sha256(project_root / "evaluate.py"), "role": "evaluator"}],
        "datasets": [{"path": "MATH/test.jsonl", "sha256": _sha256(data_path), "split": "validation"}],
        "commands": {
            "setup": [["python", "-V"]],
            "smoke": [["python", "-m", "py_compile", "evaluate.py"]],
            "run": [["python", "train.py"]],
            "evaluate": [["python", "evaluate.py"]],
        },
        "primary_metric": {"name": "eval/mean_reward", "direction": "maximize", "parser": "json_path", "path": "metrics.eval.mean_reward"},
        "sample_metrics": {"metrics": {"eval": {"mean_reward": 0.75}}},
        "secondary_metrics": ["runtime_sec"],
        "resources": {"gpu_count": 0, "gpu_min_memory_gb": 0, "max_wall_time_sec": 60},
        "budget": {"max_gpu_hours": 0.0, "max_usd": 0.0},
        "security": {"network_policy": "restricted", "forbid_metric_logging_changes": True, "clean_room_revalidation_required_for_top_k": True},
    }


def test_environment_register_show_validate_round_trip(tmp_path: Path):
    from codex_scientist.services.environment import EnvironmentService

    layout = ProjectLayout.from_project_root(tmp_path)
    service = EnvironmentService(layout)
    manifest = _valid_manifest(tmp_path)

    registered = service.register(quest_id="QENV", manifest=manifest)
    assert registered["ok"] is True
    assert registered["env_id"] == "env_toy"
    env_path = tmp_path / "CodexScientist" / "environments" / "env_toy.json"
    assert env_path.exists()

    shown = service.show(quest_id="QENV", env_id="env_toy")
    assert shown["ok"] is True
    assert shown["environment"]["env_id"] == "env_toy"
    assert shown["environment"]["primary_metric"]["name"] == "eval/mean_reward"

    validated = service.validate(quest_id="QENV", env_id="env_toy")
    assert validated["ok"] is True
    assert validated["status"] == "valid"
    assert validated["primary_metric"]["value"] == 0.75

    events = EventStore(layout).read_events()
    assert any(event.get("event_type") == "environment.registered" for event in events)


def test_environment_register_rejects_missing_env_id_without_write(tmp_path: Path):
    from codex_scientist.services.environment import EnvironmentService

    service = EnvironmentService(ProjectLayout.from_project_root(tmp_path))
    manifest = _valid_manifest(tmp_path)
    manifest.pop("env_id")

    result = service.register(quest_id="QENV", manifest=manifest)
    assert result["ok"] is False
    assert result["error_type"] == "invalid_schema"
    assert not (tmp_path / "CodexScientist" / "environments").exists()


def test_environment_validate_rejects_protected_hash_mismatch(tmp_path: Path):
    from codex_scientist.services.environment import EnvironmentService

    service = EnvironmentService(ProjectLayout.from_project_root(tmp_path))
    manifest = _valid_manifest(tmp_path)
    assert service.register(quest_id="QENV", manifest=manifest)["ok"] is True
    (tmp_path / "evaluate.py").write_text("print('changed')\n", encoding="utf-8")

    result = service.validate(quest_id="QENV", env_id="env_toy")
    assert result["ok"] is False
    assert result["error_type"] == "protected_hash_mismatch"
    assert result["recoverable"] is False


def test_environment_validate_rejects_absolute_environment_paths(tmp_path: Path):
    from codex_scientist.services.environment import EnvironmentService

    service = EnvironmentService(ProjectLayout.from_project_root(tmp_path))
    manifest = _valid_manifest(tmp_path)
    manifest["protected_files"][0]["path"] = str(tmp_path / "evaluate.py")
    assert service.register(quest_id="QENV", manifest=manifest)["ok"] is True

    result = service.validate(quest_id="QENV", env_id="env_toy")
    assert result["ok"] is False
    assert result["error_type"] == "invalid_path"


def test_environment_validate_rejects_missing_primary_metric(tmp_path: Path):
    from codex_scientist.services.environment import EnvironmentService

    service = EnvironmentService(ProjectLayout.from_project_root(tmp_path))
    manifest = _valid_manifest(tmp_path)
    manifest["sample_metrics"] = {"metrics": {"eval": {}}}
    assert service.register(quest_id="QENV", manifest=manifest)["ok"] is True

    result = service.validate(quest_id="QENV", env_id="env_toy")
    assert result["ok"] is False
    assert result["error_type"] == "metric_parser_invalid"
