from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_copy_install_smoke_to_temp_directory(tmp_path):
    target = tmp_path / "plugins" / "ponder_forge"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "copy_install_smoke.py"), "--target", str(target)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["installed"] is True
    assert payload["is_symlink"] is False
    assert payload["module_file"].endswith("ponder_forge/__init__.py")
    assert payload["tool_count"] == 9
    assert (target / "__init__.py").exists()
    assert not (target / "ponder_forge").exists()
