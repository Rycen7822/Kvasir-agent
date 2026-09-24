#!/usr/bin/env python3
"""Private per-run wrapper, launched by the validated evidence service."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kvasir_agent.services.evidence_runner import execute

if __name__ == "__main__":
    execute(sys.argv[1], sys.argv[2])
