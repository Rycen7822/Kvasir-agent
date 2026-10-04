#!/usr/bin/env python3
"""Read-only diagnostics for the installed five-tool evidence plugin."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    problems = []
    tools = []
    try:
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        config = json.loads((ROOT / ".mcp.json").read_text())
        if manifest.get("mcpServers") != "./.mcp.json" or manifest.get("skills") != "./skills":
            problems.append("Unexpected plugin discovery paths.")
        if "kvasir-agent" not in config.get("mcpServers", {}):
            problems.append("Missing evidence server configuration.")
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/ka_mcp.py"), "--stdio-smoke", "tools/list"],
                              capture_output=True, text=True, timeout=15)
        if proc.returncode:
            problems.append("Evidence server discovery failed.")
        else:
            tools = [item["name"] for item in json.loads(proc.stdout)["tools"]]
            expected = {"ka_research_status", "ka_experiment_run", "ka_experiment_stop", "ka_evidence_check", "ka_evidence_import"}
            if set(tools) != expected:
                problems.append("Evidence server does not expose exactly five expected tools.")
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        problems.append("Plugin files or server discovery are unavailable.")
    result = {"ok": not problems, "plugin_root": str(ROOT), "tools": tools,
              "mcp_entrypoint": "scripts/ka_mcp.py", "maintenance_entrypoint": "scripts/ka_admin.py", "problems": problems}
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
