from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = [
    ROOT / "codex_scientist" / "runtime" / "resources" / "prompts" / "system_copilot.md",
    ROOT / "codex_scientist" / "runtime" / "resources" / "repo" / "src" / "prompts" / "system_copilot.md",
]


def _prompt_texts() -> list[tuple[Path, str]]:
    return [(path, path.read_text(encoding="utf-8")) for path in PROMPTS]


def test_system_copilot_does_not_force_all_shell_through_bash_exec():
    forbidden = "All shell, CLI, Python, bash, node, git, package, environment, and terminal-like operations must go through"
    for path, text in _prompt_texts():
        assert forbidden not in text, path
        assert "Use Codex-native" in text, path
        assert "formal experiment" in text, path
        assert "cs_bash_exec" in text, path


def test_system_copilot_keeps_formal_provenance_fields_for_bash_exec():
    for path, text in _prompt_texts():
        for required in (
            "command_class",
            "provenance_reason",
            "experiment_or_artifact_id",
            "cwd_policy",
            "expected_outputs or evidence_paths",
        ):
            assert required in text, (path, required)
