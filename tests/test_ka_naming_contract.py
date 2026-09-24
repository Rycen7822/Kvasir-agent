from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_canonical_runtime_package_lives_under_kvasir_agent_runtime():
    import kvasir_agent.runtime.schemas as schemas
    import kvasir_agent.runtime.tools as tools

    public_names = [schema["name"] for schema in schemas.PUBLIC_SCHEMAS]
    assert public_names
    assert all(name.startswith("ka_") for name in public_names)
    assert not any(name.startswith("d" + "s_") or name.startswith("kvasiragent_") for name in public_names)
    assert hasattr(tools, "ka_doctor")
    assert not hasattr(tools, "d" + "s_doctor")
