#!/usr/bin/env python3
"""Doctor for the DeepScientist Codex-native plugin."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    problems: list[str] = []
    if (ROOT / ".mcp.json").exists():
        problems.append("Unexpected .mcp.json exists; this adapter must not use MCP.")
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    server_key = "mcp" + "Servers"
    if server_key in manifest:
        problems.append("plugin.json must not contain a server-transport registry field.")
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "dsctl.py"), "doctor", "--format", "json"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {"ok": False, "error": proc.stderr}
    ok = proc.returncode == 0 and payload.get("ok") is True and not problems
    out = {"ok": ok, "plugin_root": str(ROOT), "mcp": False, "problems": problems, "runtime_doctor": payload}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
