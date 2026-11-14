#!/usr/bin/env python3
"""T-1.21 — smoke test: a sub-agent instantiated with the migrated identity.

The Architect required this gate before extending the migration to the other
identities: if an agent booted with the migrated contract starts without
governance, the change does not proceed.

What this proves:
  1. The identity resolves at BEHAVIORAL level (not PACKAGE) — the failure mode
     that option A exists to prevent.
  2. Its contract content is readable: axioms, limits, description and lessons.
  3. A governed handler can be invoked with that identity bound and succeeds.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "/home/vatrox/workspace/ARQUX/src")

from arqux.constants import CortexLevel  # noqa: E402
from arqux.identity import IdentityManager  # noqa: E402

AGENT = "alfred"
PROJECT = "/home/vatrox/workspace/ARQUX"
failures: list[str] = []

# --- 1. Level resolution -------------------------------------------------
manager = IdentityManager()
resolved = manager.resolve(AGENT)
level = resolved.level
print(f"1. level             : {level}")
if level is not CortexLevel.BEHAVIORAL:
    failures.append(f"level is {level}, expected BEHAVIORAL")

# --- 2. Contract content -------------------------------------------------
# Read from the SAME directory the resolver uses, so the test validates what the
# agent actually receives rather than a look-alike copy elsewhere in the tree.
payload = ""
candidate = manager.identities_dir / f"{AGENT}.cortex"
if candidate.exists():
    payload = candidate.read_text(encoding="utf-8")
    print(f"2. contract source   : {candidate}")
if not payload:
    failures.append(f"identity file not found: {candidate}")

checks = {
    "AXM:architect_first": "axiom architect_first",
    "AXM:handlers_only": "axiom handlers_only",
    "LIM:no_auto_commit": "limit no_auto_commit",
    "DESC:persona": "description persona",
    "ARQX:artifact": "artifact metadata",
}
for token, label in checks.items():
    present = token in payload
    print(f"2. contract {label:<24}: {'OK' if present else 'MISSING'}")
    if not present:
        failures.append(f"contract entry missing: {token}")

# --- 3. Governed operation ----------------------------------------------
try:
    from arqux.handlers import REGISTRY
    from arqux.handlers.workspace import status as workspace_status
    from arqux.permissions import ROLE_GOVERNOR, PermissionContext

    in_registry = "workspace.status" in REGISTRY
    print(f"3. handler registry  : {'OK' if in_registry else 'MISSING'} (workspace.status)")
    if not in_registry:
        failures.append("workspace.status not in registry")

    ctx = PermissionContext(agent_id=AGENT, role=ROLE_GOVERNOR)
    out = workspace_status(path=PROJECT, ctx=ctx)
    text = out.to_text() if hasattr(out, "to_text") else str(out)
    ok = "workspace" in text.lower() and "error" not in text.lower()
    print(f"3. governed call     : {'OK' if ok else 'FAIL'} ({text[:80]})")
    if not ok:
        failures.append("governed call did not succeed")
except Exception as exc:  # noqa: BLE001
    print(f"3. governed call     : EXCEPTION {type(exc).__name__}: {exc}")
    failures.append(f"governed call raised {type(exc).__name__}")

# --- Verdict -------------------------------------------------------------
print()
if failures:
    print(f"RESULT: FAIL — {len(failures)} failure(s)")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)

print("RESULT: PASS — the migrated identity boots with its contract and operates under governance")
