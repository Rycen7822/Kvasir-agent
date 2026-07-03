from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIR_NAMES = {".git", "__pycache__", ".pytest_cache", "reference", "tmp"}
EXCLUDED_FILE_NAMES = {".coverage"}


class FakeContext:
    def __init__(self):
        self.tools = []
        self.hooks = []
        self.commands = []
        self.skills = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_hook(self, hook_name, callback):
        self.hooks.append({"hook_name": hook_name, "callback": callback})

    def register_command(self, **kwargs):
        self.commands.append(kwargs)

    def register_skill(self, name, path, description=""):
        self.skills.append({"name": name, "path": str(path), "description": description})


def _ignore(dir_path: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        if name in EXCLUDED_DIR_NAMES or name in EXCLUDED_FILE_NAMES:
            ignored.add(name)
        if name == "tmp_ponder_forge_plan_v2" and Path(dir_path).name == "worknotes":
            ignored.add(name)
    return ignored


def copy_install(target: Path) -> None:
    if target.exists() or target.is_symlink():
        if target.is_symlink():
            raise RuntimeError(f"target must not be a symlink: {target}")
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT, target, ignore=_ignore, symlinks=False)


def load_installed(target: Path):
    parent = types.ModuleType("hermes_plugins")
    parent.__path__ = [str(target.parent)]
    sys.modules.setdefault("hermes_plugins", parent)
    spec = importlib.util.spec_from_file_location(
        "hermes_plugins.ponder_forge",
        target / "__init__.py",
        submodule_search_locations=[str(target)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load installed plugin")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=Path.home() / ".hermes" / "plugins" / "ponder_forge")
    args = parser.parse_args()
    target = args.target.expanduser().resolve()
    copy_install(target)
    module = load_installed(target)
    ctx = FakeContext()
    module.register(ctx)
    module_file = getattr(module, "__file__", None)
    if not module_file:
        raise RuntimeError("installed module has no __file__")
    payload = {
        "installed": target.exists(),
        "target": str(target),
        "is_symlink": target.is_symlink(),
        "module_file": str(Path(module_file).resolve()),
        "tool_count": len(ctx.tools),
        "hook_count": len(ctx.hooks),
        "command_count": len(ctx.commands),
        "skill_count": len(ctx.skills),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
