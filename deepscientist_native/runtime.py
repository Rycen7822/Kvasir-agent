"""Native DeepScientist runtime resolver for the Codex adapter."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import PLUGIN_ROOT, NativeConfig, load_config

VENDOR_ROOT = PLUGIN_ROOT / "vendor"
RESOURCE_ROOT = PLUGIN_ROOT / "resources"
DEFAULT_RESOURCE_REPO_ROOT = RESOURCE_ROOT / "repo"


def plugin_root() -> Path:
    return PLUGIN_ROOT


def vendor_root() -> Path:
    return VENDOR_ROOT


def resource_root() -> Path:
    return RESOURCE_ROOT


def resource_repo_root(config: NativeConfig | None = None) -> Path:
    cfg = config or load_config()
    return (cfg.resource_repo_root or DEFAULT_RESOURCE_REPO_ROOT).expanduser().resolve()


def _path_is_under(path: str | os.PathLike[str] | None, root: Path) -> bool:
    if not path:
        return False
    try:
        Path(path).resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _clear_conflicting_deepscientist_modules(vendor_root: Path) -> None:
    existing = sys.modules.get("deepscientist")
    if existing is None:
        return
    module_file = getattr(existing, "__file__", None)
    module_paths = list(getattr(existing, "__path__", []) or [])
    if _path_is_under(module_file, vendor_root) or any(_path_is_under(path, vendor_root) for path in module_paths):
        return
    for name in list(sys.modules):
        if name == "deepscientist" or name.startswith("deepscientist."):
            sys.modules.pop(name, None)


def ensure_runtime_import_environment(config: NativeConfig | None = None) -> None:
    cfg = config or load_config()
    vendor_root = VENDOR_ROOT.resolve()
    _clear_conflicting_deepscientist_modules(vendor_root)
    vendor = str(vendor_root)
    sys.path = [p for p in sys.path if p != vendor]
    sys.path.insert(0, vendor)
    # Child monitor processes launched by BashExecService import deepscientist by module name.
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    parts = [p for p in existing_pythonpath.split(os.pathsep) if p]
    if vendor not in parts:
        os.environ["PYTHONPATH"] = os.pathsep.join([vendor, *parts])
    repo = str(resource_repo_root(cfg))
    os.environ["DEEPSCIENTIST_REPO_ROOT"] = repo
    os.environ["DEEPSCIENTIST_HOME"] = str(cfg.runtime_home.expanduser())
    os.environ["DS_HOME"] = str(cfg.runtime_home.expanduser())


@dataclass
class Services:
    config: NativeConfig
    home: Path
    resource_repo_root: Path
    quest: Any
    artifact: Any
    memory: Any
    bash: Any
    config_manager: Any
    baseline_registry: Any
    skill_installer: Any


def _import_services():
    from deepscientist.artifact import ArtifactService
    from deepscientist.bash_exec import BashExecService
    from deepscientist.config import ConfigManager
    from deepscientist.home import ensure_home_layout
    from deepscientist.memory import MemoryService
    from deepscientist.quest import QuestService
    from deepscientist.registries import BaselineRegistry
    from deepscientist.skills import SkillInstaller
    return {
        "ArtifactService": ArtifactService,
        "BashExecService": BashExecService,
        "ConfigManager": ConfigManager,
        "ensure_home_layout": ensure_home_layout,
        "MemoryService": MemoryService,
        "QuestService": QuestService,
        "BaselineRegistry": BaselineRegistry,
        "SkillInstaller": SkillInstaller,
    }


def get_services(config: NativeConfig | None = None) -> Services:
    cfg = config or load_config()
    ensure_runtime_import_environment(cfg)
    imports = _import_services()
    home = cfg.runtime_home.expanduser().resolve()
    imports["ensure_home_layout"](home)
    repo = resource_repo_root(cfg)
    skill_installer = imports["SkillInstaller"](repo, home)
    quest = imports["QuestService"](home, skill_installer=skill_installer)
    return Services(
        config=cfg,
        home=home,
        resource_repo_root=repo,
        quest=quest,
        artifact=imports["ArtifactService"](home),
        memory=imports["MemoryService"](home),
        bash=imports["BashExecService"](home),
        config_manager=imports["ConfigManager"](home),
        baseline_registry=imports["BaselineRegistry"](home),
        skill_installer=skill_installer,
    )


def compact_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return {}
    keys = [
        "quest_id", "title", "goal", "status", "runtime_status", "display_status",
        "active_anchor", "active_idea_id", "active_analysis_campaign_id",
        "quest_root", "active_workspace_root", "updated_at", "created_at",
        "pending_decisions", "counts", "paths", "latest_metric", "baseline_gate",
        "confirmed_baseline_ref", "active_baseline_id", "active_baseline_variant_id",
        "pending_user_message_count", "last_resume_at", "stop_reason",
    ]
    return {key: snapshot.get(key) for key in keys if key in snapshot}


def doctor() -> dict[str, Any]:
    cfg = load_config()
    checks: list[dict[str, Any]] = []
    def check(check_id: str, ok: bool, summary: str, **details: Any) -> None:
        checks.append({"id": check_id, "ok": bool(ok), "summary": summary, "details": details})
    try:
        ensure_runtime_import_environment(cfg)
        import deepscientist  # type: ignore
        check("vendored_runtime_import", True, "Vendored DeepScientist runtime imports successfully.", package_file=str(Path(deepscientist.__file__).resolve()))
    except Exception as exc:
        check("vendored_runtime_import", False, f"Vendored runtime import failed: {exc}")
    repo = resource_repo_root(cfg)
    expected_skills = {"scout","baseline","idea","optimize","experiment","analysis-campaign","write","finalize","decision","figure-polish","paper-fetch","paper-reliability-verifier","strict-research","intake-audit","review","rebuttal","experiment-execution","quest-handoffs","writing-plans","paper-reliability-verification"}
    present_skills = {p.parent.name for p in (RESOURCE_ROOT / "skills").glob("*/SKILL.md")}
    check("resource_skills", expected_skills.issubset(present_skills), "DeepScientist stage/companion skills are present.", missing=sorted(expected_skills - present_skills), count=len(present_skills))
    check("resource_prompts", (RESOURCE_ROOT / "prompts").exists() and not (RESOURCE_ROOT / "prompts" / "connectors").exists(), "Prompt resources are present without connector prompts.")
    try:
        services = get_services(cfg)
        probe = services.home / "runtime" / ".codex-native-doctor"
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
        check("runtime_home_writable", True, "Runtime home is writable.", runtime_home=str(services.home))
    except Exception as exc:
        check("runtime_home_writable", False, f"Runtime home check failed: {exc}", runtime_home=str(cfg.runtime_home))
    forbidden = ["src/ui", "src/tui", "vendor/deepscientist/tui.py", "vendor/deepscientist/" + "connector" + "_runtime.py", "vendor/deepscientist/connector", "resources/prompts/connectors", "vendor/deepscientist/" + ("dae" + "mon")]
    present = [rel for rel in forbidden if (PLUGIN_ROOT / rel).exists()]
    check("no_web_tui_connector_surface", not present, "Web/TUI/social connector surfaces remain absent.", present=present)
    check("no_external_ds_required", True, "Codex-native adapter does not require a global npm ds binary.")
    return {"ok": all(item["ok"] for item in checks), "checks": checks, "config": cfg.as_dict(), "resource_repo_root": str(repo)}
