#!/usr/bin/env python3
"""Standalone template validator — runs outside pytest.

Usage:
    python scripts/validate_templates.py
    python scripts/validate_templates.py --strict   # exit 1 on any warning
    python scripts/validate_templates.py --json      # machine-readable output

Validates every .cortex template shipped with ArqUX against the strict
schema validation introduced in codec-cortex 0.5.0.

Exit codes:
    0 = all templates valid (no errors)
    1 = one or more templates invalid (E* errors)
    2 = warnings present (--strict mode only)
    3 = script error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TEMPLATES = [
    "src/arqux/templates/meta-brain.cortex",
    "src/arqux/templates/learn-policies.cortex",
    "src/arqux/templates/brain.cortex",
    "src/arqux/UPGRADE.cortex",
    "src/arqux/identities/jarvis.cortex",
    "src/arqux/identities/governor.cortex",
    "src/arqux/identities/auditor.cortex",
    "src/arqux/identities/executor.cortex",
    "src/arqux/identities/alfred.cortex",
    "src/arqux/identities/heimdall.cortex",
    "src/arqux/identities/seshat.cortex",
]


def validate_all() -> list[dict]:
    """Validate every template and return a list of result dicts."""
    from arqux.handlers.cortex import verify_handler
    from arqux.permissions import PermissionContext

    ctx = PermissionContext(agent_id="validator", role="governor")
    results = []
    for rel in TEMPLATES:
        path = REPO_ROOT / rel
        if not path.exists():
            results.append({
                "template": rel,
                "exists": False,
                "valid": False,
                "error": "file not found",
            })
            continue
        try:
            r = verify_handler(path=str(path), ctx=ctx)
            fields = r.fields or {}
            diagnostics = fields.get("diagnostics", []) or []
            results.append({
                "template": rel,
                "exists": True,
                "valid": fields.get("valid"),
                "sections": fields.get("sections"),
                "entries": fields.get("entries"),
                "diagnostics": diagnostics,
                "errors": [d for d in diagnostics if d.startswith("[E")],
                "warnings": [d for d in diagnostics if d.startswith("[W")],
                "infos": [d for d in diagnostics if d.startswith("[I")],
            })
        except Exception as e:
            results.append({
                "template": rel,
                "exists": True,
                "valid": False,
                "error": str(e),
            })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ArqUX .cortex templates")
    parser.add_argument("--strict", action="store_true",
                        help="exit 2 on any warning (default: only errors fail)")
    parser.add_argument("--json", action="store_true",
                        help="output JSON (machine-readable)")
    parser.add_argument("--quiet", action="store_true",
                        help="only show failures")
    args = parser.parse_args()

    try:
        results = validate_all()
    except ImportError as e:
        print(f"ERROR: cannot import arqux — is it installed? {e}", file=sys.stderr)
        return 3

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        total = len(results)
        valid = sum(1 for r in results if r.get("valid"))
        invalid = [r for r in results if r.get("valid") is False]
        with_warnings = [r for r in results if r.get("warnings")]

        if not args.quiet or invalid:
            print(f"Templates validated: {total}")
            print(f"  valid:   {valid}")
            print(f"  invalid: {len(invalid)}")
            print(f"  with warnings: {len(with_warnings)}")
            print()

        for r in results:
            if r.get("valid") is False:
                print(f"FAIL  {r['template']}")
                if r.get("errors"):
                    for e in r["errors"]:
                        print(f"      {e}")
                elif r.get("error"):
                    print(f"      error: {r['error']}")
            elif r.get("warnings") and args.strict:
                print(f"WARN  {r['template']}")
                for w in r["warnings"]:
                    print(f"      {w}")
            elif not args.quiet:
                tag = "OK   " if not r.get("warnings") else "WARN "
                print(f"{tag} {r['template']}  (sections={r.get('sections')}, entries={r.get('entries')})")
                for w in r.get("warnings", []):
                    print(f"      {w}")

    if any(r.get("valid") is False for r in results):
        return 1
    if args.strict and any(r.get("warnings") for r in results):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
