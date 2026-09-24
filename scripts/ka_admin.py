#!/usr/bin/env python3
"""Explicit terminal maintenance; deliberately absent from model discovery."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kvasir_agent.services.evidence import EvidenceService
from kvasir_agent.services.evidence_contracts import EvidenceError, read_json
from kvasir_agent.services.research_state import ResearchState


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "migrate", "repair-events", "reconcile"):
        sub = commands.add_parser(command)
        sub.add_argument("--project", required=True)
        if command == "migrate":
            mode = sub.add_mutually_exclusive_group(required=True)
            mode.add_argument("--plan-out")
            mode.add_argument("--apply-plan")
        if command == "reconcile":
            sub.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        state = ResearchState(args.project)
        if args.command == "init":
            result = state.initialize()
        elif args.command == "repair-events":
            result = state.repair_events()
        elif args.command == "reconcile":
            result = EvidenceService(args.project).reconcile(args.run_id)
        else:
            from kvasir_agent.services.explicit_migration import Migration
            migration = Migration(state)
            if args.plan_out:
                path = Path(args.plan_out)
                if not path.is_absolute() or path.resolve().is_relative_to(state.root):
                    raise EvidenceError("invalid_path", "Migration plans must be written outside the research state tree.")
                plan = migration.plan()
                with path.open("x") as f:
                    json.dump(plan, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                result = {"ok": not plan["conflicts"], "plan_path": str(path), "conflicts": plan["conflicts"][:5]}
            else:
                result = migration.apply(read_json(Path(args.apply_plan), limit=50_000_000))
    except (EvidenceError, OSError) as exc:
        result = {"ok": False, "error_type": exc.kind if isinstance(exc, EvidenceError) else "io_error",
                  "error": str(exc)[:240]}
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        result = {"ok": False, "error_type": "state_error", "error": "Invalid maintenance state or plan."}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
