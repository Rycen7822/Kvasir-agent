from __future__ import annotations

import hashlib
import json
from pathlib import Path

from codex_scientist.services.environment import EnvironmentService
from codex_scientist.services.project_state import ProjectLayout

PROMPT_ROOT = Path(__file__).resolve().parents[1] / "codex_scientist" / "runtime" / "resources" / "prompts" / "execution_grounded"
QUEST_ID = "QCTX"
ENV_ID = "env_ctx"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_context_project(project_root: Path) -> dict:
    repo = project_root / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "train.py").write_text("VALUE = 1\n# mutable training code\n", encoding="utf-8")
    (repo / "model.py").write_text("MODEL = 'tiny'\n" * 80, encoding="utf-8")
    (repo / "evaluate.py").write_text("EVAL_SECRET = 'do-not-leak'\nprint('eval')\n", encoding="utf-8")
    (repo / "data.jsonl").write_text('{"secret_label": "dataset-raw"}\n', encoding="utf-8")
    (repo / "README.md").write_text("# Context note\nUse the tiny model.\n", encoding="utf-8")
    return {
        "schema_version": 1,
        "env_id": ENV_ID,
        "quest_id": QUEST_ID,
        "title": "Implementer context environment",
        "problem": "build a safe bounded context",
        "baseline": {"repo_path": "repo", "baseline_metric": {"name": "score", "value": 0.5, "direction": "maximize"}},
        "mutable_allowlist": ["repo/train.py", "repo/model.py"],
        "context_files": ["repo/README.md"],
        "protected_files": [{"path": "repo/evaluate.py", "sha256": _sha256(repo / "evaluate.py"), "role": "evaluator"}],
        "datasets": [{"path": "repo/data.jsonl", "sha256": _sha256(repo / "data.jsonl"), "split": "validation", "rows": 1, "sample_rows": ["raw_dataset_secret_from_manifest"]}],
        "commands": {"setup": [["python", "-V"]], "smoke": [["python", "-m", "py_compile", "train.py"]], "run": [["python", "train.py"]], "evaluate": [["python", "evaluate.py"]]},
        "primary_metric": {"name": "score", "direction": "maximize", "parser": "json_path", "path": "metrics.score"},
        "sample_metrics": {"metrics": {"score": 0.5}},
        "resources": {"gpu_count": 0},
        "budget": {"max_gpu_hours": 0.0, "max_usd": 0.0},
        "security": {"network_policy": "restricted"},
    }


def _registered_layout(tmp_path: Path) -> ProjectLayout:
    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = _write_context_project(tmp_path)
    assert EnvironmentService(layout).register(quest_id=QUEST_ID, manifest=manifest)["ok"] is True
    return layout


def _write_variant_record(layout: ProjectLayout, *, variant_id: str = "var_ctx", env_id: str = ENV_ID, idea_id: str = "idea_ctx") -> Path:
    path = layout.quest_detail_path(QUEST_ID, Path("variants") / variant_id / "variant.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "quest_id": QUEST_ID,
                "env_id": env_id,
                "trajectory_id": "traj_ctx",
                "variant_id": variant_id,
                "idea_id": idea_id,
                "status": "failed_smoke",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _register_second_env(layout: ProjectLayout, tmp_path: Path, env_id: str = "env_other") -> None:
    manifest = _write_context_project(tmp_path)
    manifest["env_id"] = env_id
    assert EnvironmentService(layout).register(quest_id=QUEST_ID, manifest=manifest)["ok"] is True


def test_execution_grounded_prompts_define_schema_first_patch_contracts():
    runtime_root = PROMPT_ROOT
    repo_root = Path(__file__).resolve().parents[1] / "codex_scientist" / "runtime" / "resources" / "repo" / "src" / "prompts" / "execution_grounded"
    for filename in ("implementer.md", "patch_repair.md"):
        runtime_content = (runtime_root / filename).read_text(encoding="utf-8")
        repo_content = (repo_root / filename).read_text(encoding="utf-8")
        assert repo_content == runtime_content
        lowered = runtime_content.lower()
        assert "schema-first" in lowered
        assert "implementation_plan" in runtime_content
        assert "patch_artifact_path" in runtime_content
        assert "role=mutable" in runtime_content
        assert "role=context" in runtime_content
        assert "read-only reference" in lowered
        assert "git diff" in lowered
        assert "do not handwrite final hunk counts" in lowered
        assert "protected" in lowered and "dataset" in lowered


def test_implementer_context_includes_only_mutable_and_declared_context_files_with_line_numbers(tmp_path: Path):
    from codex_scientist.services.implementer_context import ImplementerContextBuilder

    layout = _registered_layout(tmp_path)
    context = ImplementerContextBuilder(layout).build(quest_id=QUEST_ID, env_id=ENV_ID, idea_id="idea_ctx", token_budget=800)

    assert context["ok"] is True, context
    included = {item["path"]: item for item in context["included_files"]}
    assert set(included) == {"README.md", "model.py", "train.py"}
    assert included["train.py"]["project_path"] == "repo/train.py"
    assert included["train.py"]["role"] == "mutable"
    assert included["README.md"]["role"] == "context"
    assert included["train.py"]["sha256"] == _sha256(tmp_path / "repo" / "train.py")
    assert included["train.py"]["byte_count"] == len((tmp_path / "repo" / "train.py").read_bytes())
    assert "1|VALUE = 1" in included["train.py"]["content"]
    assert "2|# mutable training code" in included["train.py"]["content"]
    assert "Use the tiny model" in included["README.md"]["content"]
    assert all("evaluate.py" != item["path"] for item in context["included_files"])
    assert all("data.jsonl" != item["path"] for item in context["included_files"])


def test_implementer_context_excludes_protected_and_dataset_content_but_keeps_metadata(tmp_path: Path):
    from codex_scientist.services.implementer_context import ImplementerContextBuilder

    layout = _registered_layout(tmp_path)
    context = ImplementerContextBuilder(layout).build(quest_id=QUEST_ID, env_id=ENV_ID, idea_id="idea_ctx", token_budget=800)
    text = repr(context)

    protected = context["protected_files"][0]
    assert protected["path"] == "evaluate.py"
    assert protected["project_path"] == "repo/evaluate.py"
    assert protected["role"] == "evaluator"
    assert protected["sha256"] == _sha256(tmp_path / "repo" / "evaluate.py")
    assert protected["content"] == "[PROTECTED_FILE_CONTENT_REDACTED]"
    assert "EVAL_SECRET" not in text
    assert "do-not-leak" not in text

    dataset = context["datasets"][0]
    assert dataset["path"] == "data.jsonl"
    assert dataset["project_path"] == "repo/data.jsonl"
    assert dataset["sha256"] == _sha256(tmp_path / "repo" / "data.jsonl")
    assert dataset["split"] == "validation"
    assert dataset["rows"] == 1
    assert "sample_rows" not in dataset
    assert dataset["content"] == "[DATASET_CONTENT_EXCLUDED]"
    assert "dataset-raw" not in text
    assert "raw_dataset_secret_from_manifest" not in text


def test_implementer_context_dataset_metadata_filters_non_scalar_values(tmp_path: Path):
    from codex_scientist.services.implementer_context import ImplementerContextBuilder

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = _write_context_project(tmp_path)
    manifest["env_id"] = "env_bad_dataset_meta"
    manifest["datasets"][0]["rows"] = ["RAW_ROW_SHOULD_NOT_LEAK"]
    manifest["datasets"][0]["split"] = {"sample": "RAW_SPLIT_SHOULD_NOT_LEAK"}
    assert EnvironmentService(layout).register(quest_id=QUEST_ID, manifest=manifest)["ok"] is True

    context = ImplementerContextBuilder(layout).build(quest_id=QUEST_ID, env_id="env_bad_dataset_meta", idea_id="idea_ctx", token_budget=800)
    dataset = context["datasets"][0]
    text = repr(context)

    assert context["ok"] is True, context
    assert "rows" not in dataset
    assert "split" not in dataset
    assert dataset["sha256"] == _sha256(tmp_path / "repo" / "data.jsonl")
    assert "RAW_ROW_SHOULD_NOT_LEAK" not in text
    assert "RAW_SPLIT_SHOULD_NOT_LEAK" not in text


def test_malformed_manifest_metadata_never_leaks_raw_values(tmp_path: Path):
    from codex_scientist.services.implementer_context import ImplementerContextBuilder

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = _write_context_project(tmp_path)
    manifest["env_id"] = "env_malformed_meta"
    manifest["protected_files"][0]["role"] = {"raw": "RAW_PROTECTED_ROLE_LEAK"}
    manifest["protected_files"][0]["sha256"] = "RAW_PROTECTED_SHA_LEAK"
    manifest["datasets"][0]["path"] = {"raw": "RAW_DATASET_PATH_LEAK"}
    manifest["datasets"][0]["rows"] = ["RAW_DATASET_ROWS_LEAK"]
    manifest["datasets"][0]["split"] = {"raw": "RAW_DATASET_SPLIT_LEAK"}
    manifest["context_files"].append({"raw": "RAW_CONTEXT_ITEM_LEAK"})
    assert EnvironmentService(layout).register(quest_id=QUEST_ID, manifest=manifest)["ok"] is True

    builder = ImplementerContextBuilder(layout)
    context = builder.build(quest_id=QUEST_ID, env_id="env_malformed_meta", idea_id="idea_ctx", token_budget=800)
    text = repr(context)

    assert context["ok"] is True, context
    assert context["protected_files"][0]["role"] == "protected"
    assert context["protected_files"][0]["sha256"] == "[INVALID_SHA256_REDACTED]"
    assert context["datasets"][0]["path"] == "[INVALID_DATASET_PATH]"
    for sentinel in (
        "RAW_PROTECTED_ROLE_LEAK",
        "RAW_PROTECTED_SHA_LEAK",
        "RAW_DATASET_PATH_LEAK",
        "RAW_DATASET_ROWS_LEAK",
        "RAW_DATASET_SPLIT_LEAK",
        "RAW_CONTEXT_ITEM_LEAK",
    ):
        assert sentinel not in text

    _write_variant_record(layout, env_id="env_malformed_meta")
    repair = builder.build_repair(
        quest_id=QUEST_ID,
        env_id="env_malformed_meta",
        variant_id="var_ctx",
        token_budget=800,
        previous_failure={"stderr_tail": "patch failed"},
    )
    assert repair["ok"] is True, repair
    assert "RAW_PROTECTED_SHA_LEAK" not in repr(repair)
    assert repair["repair"]["protected_hash_report"].get("expected_sha256") == "[INVALID_SHA256_REDACTED]"


def test_repair_context_sanitizes_hash_report_error_messages(tmp_path: Path):
    from codex_scientist.services.implementer_context import ImplementerContextBuilder

    layout = ProjectLayout.from_project_root(tmp_path)
    manifest = _write_context_project(tmp_path)
    manifest["env_id"] = "env_hash_report_leak"
    manifest["datasets"][0]["path"] = {"raw": "RAW_DATASET_PATH_REPORT_LEAK"}
    assert EnvironmentService(layout).register(quest_id=QUEST_ID, manifest=manifest)["ok"] is True
    _write_variant_record(layout, env_id="env_hash_report_leak")

    repair = ImplementerContextBuilder(layout).build_repair(
        quest_id=QUEST_ID,
        env_id="env_hash_report_leak",
        variant_id="var_ctx",
        token_budget=800,
        previous_failure={"stderr_tail": "patch failed"},
    )

    assert repair["ok"] is True, repair
    report = repair["repair"]["protected_hash_report"]
    assert report["ok"] is False
    assert report["error"] == "[SANITIZED_HASH_REPORT_ERROR]"
    assert "RAW_DATASET_PATH_REPORT_LEAK" not in repr(repair)


def test_implementer_context_token_budget_truncation_is_deterministic_and_records_omissions(tmp_path: Path):
    from codex_scientist.services.implementer_context import ImplementerContextBuilder

    layout = _registered_layout(tmp_path)
    first = ImplementerContextBuilder(layout).build(quest_id=QUEST_ID, env_id=ENV_ID, idea_id="idea_ctx", token_budget=20)
    second = ImplementerContextBuilder(layout).build(quest_id=QUEST_ID, env_id=ENV_ID, idea_id="idea_ctx", token_budget=20)

    assert first == second
    assert first["ok"] is True
    assert first["budget"]["token_budget"] == 20
    assert first["budget"]["char_budget"] == 80
    assert first["budget"]["used_chars"] <= 80
    assert first["omitted_files"], first
    assert {item["reason"] for item in first["omitted_files"]} <= {"token_budget_exceeded", "content_truncated"}


def test_repair_context_includes_failure_digests_and_redacts_secrets(tmp_path: Path):
    from codex_scientist.services.implementer_context import ImplementerContextBuilder

    layout = _registered_layout(tmp_path)
    _write_variant_record(layout)
    variant_root = tmp_path / "CodexScientist" / "quests" / QUEST_ID / "variants" / "var_ctx"
    variant_root.mkdir(parents=True, exist_ok=True)
    (variant_root / "checks.json").write_text(
        '{"smoke_status":"failed","failure_class":"syntax_fail","stderr_tail":"SyntaxError: token=sk-proj-SECRETSECRETSECRETSECRET"}',
        encoding="utf-8",
    )
    previous_failure = {
        "error_type": "patch_fail",
        "git_apply_check_stderr": "bad hunk password=super-secret",
        "stderr_tail": "ModuleNotFoundError: token=github-token-redacted-fixture",
        "failure_class": "import_fail",
    }

    context = ImplementerContextBuilder(layout).build_repair(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        variant_id="var_ctx",
        token_budget=800,
        previous_failure=previous_failure,
    )
    text = repr(context)

    assert context["ok"] is True, context
    assert context["repair"]["failure_taxonomy"] == "import_fail"
    assert "git apply --check" in context["repair"]["git_apply_check_stderr_label"]
    assert "[REDACTED]" in context["repair"]["git_apply_check_stderr"]
    assert "[REDACTED]" in context["repair"]["previous_patch_failure"]["git_apply_check_stderr"]
    assert "[REDACTED]" in context["repair"]["smoke_failure_digest"]["stderr_tail"]
    assert context["repair"]["protected_hash_report"]["ok"] is True
    assert "super-secret" not in text
    assert "sk-proj" not in text
    assert "ghp_SECRET" not in text


def test_repair_context_accepts_patch_check_stderr_tail_and_rejects_bad_variant_inputs(tmp_path: Path):
    from codex_scientist.services.implementer_context import ImplementerContextBuilder

    layout = _registered_layout(tmp_path)
    _write_variant_record(layout)
    builder = ImplementerContextBuilder(layout)

    tail_only = builder.build_repair(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        variant_id="var_ctx",
        token_budget=800,
        previous_failure={"error_type": "patch_fail", "stderr_tail": "git apply failed token=secret-token"},
    )
    assert tail_only["ok"] is True, tail_only
    assert tail_only["repair"]["git_apply_check_stderr"] == "git apply failed token=[REDACTED]"

    invalid = builder.build_repair(
        quest_id=QUEST_ID,
        env_id=ENV_ID,
        variant_id="../evil",
        token_budget=800,
        previous_failure={"stderr_tail": "x"},
    )
    assert invalid["ok"] is False
    assert invalid["error_type"] == "invalid_path"

    _register_second_env(layout, tmp_path, env_id="env_other")
    mismatch = builder.build_repair(
        quest_id=QUEST_ID,
        env_id="env_other",
        variant_id="var_ctx",
        token_budget=800,
        previous_failure={"stderr_tail": "x"},
    )
    assert mismatch["ok"] is False
    assert mismatch["error_type"] == "repair_context_env_mismatch"
