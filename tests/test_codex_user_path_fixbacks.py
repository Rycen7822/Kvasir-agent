from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
PLUGIN_NAMESPACE = "kvasir-agent"


def _run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def _frontmatter_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    frontmatter = text.split("---", 2)[1]
    for line in frontmatter.splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"missing frontmatter name in {path}")


def test_installer_delegates_exact_reference_and_propagates_failures(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    capture = tmp_path / "args.json"
    codex = bin_dir / "codex"
    codex.write_text(f"#!{PYTHON}\nimport json, os, sys\nfrom pathlib import Path\nPath(os.environ['CAPTURE_ARGS']).write_text(json.dumps(sys.argv[1:]))\nsys.exit(int(os.environ.get('CODEX_TEST_EXIT', '0')))\n")
    codex.chmod(0o755)
    env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'], CAPTURE_ARGS=str(capture))
    proc = _run(["bash", "scripts/install.sh", "kvasir-agent@test-market"], env=env)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(capture.read_text()) == ["plugin", "add", "kvasir-agent@test-market"]
    assert "new Codex thread" in proc.stdout
    env["CODEX_TEST_EXIT"] = "7"
    failed = _run(["bash", "scripts/install.sh", "kvasir-agent@test-market"], env=env)
    assert failed.returncode == 7
    assert "new Codex thread" not in failed.stdout
    capture.unlink()
    invalid = _run(["bash", "scripts/install.sh"], env=env)
    assert invalid.returncode == 2
    assert not capture.exists()


def test_manifest_default_prompts_fit_codex_plugin_limits() -> None:
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    prompts = manifest["interface"].get("defaultPrompt")

    assert isinstance(prompts, list)
    assert 1 <= len(prompts) <= 3
    for prompt in prompts:
        assert isinstance(prompt, str)
        assert 1 <= len(prompt) <= 128


def test_packaged_skill_names_fit_codex_namespace_limit() -> None:
    offenders: list[str] = []
    for skill_path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        name = _frontmatter_name(skill_path)
        namespaced = f"{PLUGIN_NAMESPACE}:{name}"
        if len(namespaced) > 64:
            offenders.append(f"{skill_path.relative_to(ROOT)} -> {namespaced} ({len(namespaced)})")
    assert not offenders
