"""Host-neutral entry point for Delphi's existing component CLIs."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delphi native-host CLI")
    parser.add_argument("--state-dir", required=True,
                        help="Shared absolute project state directory; pass it to every worker.")
    parser.add_argument("component", choices=("idea-spark", "ponder-forge"))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    state = Path(args.state_dir).expanduser().resolve()
    env = os.environ.copy()
    env["DELPHI_HOME"] = str(state)
    component = Path(__file__).resolve().parent / args.component / "cli.py"
    # Replace this bridge: isolate imports and preserve stdin/inherited payload FDs.
    os.execve(sys.executable, [sys.executable, str(component), *args.args], env)


if __name__ == "__main__":
    raise SystemExit(main())
