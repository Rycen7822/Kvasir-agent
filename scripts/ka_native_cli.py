#!/usr/bin/env python3
"""Retired generic command interface; no handlers or state mutations."""
import json

def main(argv=None):
    print(json.dumps({"ok": False, "error_type": "interface_retired", "error": "This generic command interface has been removed."}))
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
