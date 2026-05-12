from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from test_goal_e2e_toy_research import FORBIDDEN, run_toy_goal_research


def _contains_hidden_cli_command(args: Any) -> bool:
    if isinstance(args, (list, tuple)):
        return any(_contains_hidden_cli_command(item) for item in args)
    return any(forbidden in str(args) for forbidden in FORBIDDEN)


def test_goal_e2e_does_not_invoke_hidden_cli(monkeypatch, tmp_path: Path):
    original_run = subprocess.run
    original_popen = subprocess.Popen
    observed: list[str] = []

    def guarded_run(*args, **kwargs):
        observed.append(str(args[0] if args else ""))
        assert not _contains_hidden_cli_command(args), args
        assert not _contains_hidden_cli_command(kwargs), kwargs
        return original_run(*args, **kwargs)

    class GuardedPopen(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            observed.append(str(args[0] if args else ""))
            assert not _contains_hidden_cli_command(args), args
            assert not _contains_hidden_cli_command(kwargs), kwargs
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", guarded_run)
    monkeypatch.setattr(subprocess, "Popen", GuardedPopen)

    result = run_toy_goal_research(tmp_path)
    assert result["claim"]["claim_gate"]["claimable"] is True
    assert all("csctl.py" not in item for item in observed)
