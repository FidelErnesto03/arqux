#!/usr/bin/env python3
"""Generate HANDLERS.md with governance/utility classification (P1-R).

Usage:
    python scripts/gen_handlers_governance_doc.py > HANDLERS.md

Generates a markdown table classifying each handler as governance or utility,
with role requirements and HMAC flags.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arqux.handlers import REGISTRY
from arqux.permissions import (
    GOVERNOR_ONLY,
    HMAC_REQUIRED,
    MUTATING_HANDLERS,
    READ_ONLY_PREFIXES,
)

# 24-handler governance budget (P1-R)
GOVERNANCE_HANDLERS = {
    # blueprint (16 governance handlers — mutations)
    "blueprint.create", "blueprint.define", "blueprint.mature",
    "blueprint.ready", "blueprint.assign", "blueprint.claim",
    "blueprint.update", "blueprint.complete", "blueprint.fail",
    "blueprint.cancel", "blueprint.approve", "blueprint.re_delegate",
    "blueprint.block_for_architect", "blueprint.task", "blueprint.gate",
    "blueprint.ac",
    # cycle (3 governance — mutations)
    "cycle.create", "cycle.mature", "cycle.close",
    # protocol (4 governance)
    "protocol.adopt", "protocol.release", "protocol.pause", "protocol.resume",
    # evidence (1 governance)
    "evidence.record",
}


def classify(handler: str) -> str:
    if handler in GOVERNANCE_HANDLERS:
        return "governance"
    return "utility"


def role_required(handler: str) -> str:
    if handler in GOVERNOR_ONLY:
        return "GOVERNOR"
    if handler in MUTATING_HANDLERS:
        return "GOVERNOR, EXECUTOR"
    return "ALL (read-only)"


def hmac_flag(handler: str) -> str:
    return "yes" if handler in HMAC_REQUIRED else "no"


def main() -> None:
    by_module: dict[str, list[str]] = {}
    for name in sorted(REGISTRY.keys()):
        module = name.split(".")[0]
        by_module.setdefault(module, []).append(name)

    print("# ArqUX Handlers")
    print()
    print(f"Total: **{len(REGISTRY)}** handlers")
    print()
    print("## Governance Budget (P1-R)")
    print()
    print("ArqUX classifies handlers into two categories:")
    print()
    print("### Governance Handlers (24-handler budget)")
    print()
    print("These 24 handlers manage the lifecycle of governance artifacts. They are the canonical surface area that the governance model enforces.")
    print()
    gov_count = sum(1 for h in REGISTRY if classify(h) == "governance")
    util_count = len(REGISTRY) - gov_count
    print(f"- **Governance**: {gov_count} handlers")
    print(f"- **Utility**: {util_count} handlers")
    print()
    print("The 24-handler governance budget is a design constraint: adding a new governance handler requires removing one.")
    print()

    for module, handlers in sorted(by_module.items()):
        print(f"## {module}")
        print()
        print("| Handler | Description | Category | Role Required | HMAC |")
        print("|---------|-------------|----------|---------------|------|")
        for h in handlers:
            spec = REGISTRY[h]
            desc = spec.description.split("\n")[0][:80]
            cat = classify(h)
            role = role_required(h)
            hmac = hmac_flag(h)
            print(f"| `{h}` | {desc} | {cat} | {role} | {hmac} |")
        print()

    print("## Summary")
    print()
    print(f"- **Total handlers**: {len(REGISTRY)}")
    print(f"- **Governance**: {gov_count}")
    print(f"- **Utility**: {util_count}")
    print(f"- **Governor-only**: {len(GOVERNOR_ONLY)} ({', '.join(GOVERNOR_ONLY)})")
    print(f"- **HMAC-required**: {len(HMAC_REQUIRED)} ({', '.join(HMAC_REQUIRED)})")
    print(f"- **Mutating (denied to auditor)**: {len(MUTATING_HANDLERS)}")
    print(f"- **Read-only (allowed for auditor)**: {len(READ_ONLY_PREFIXES)}")


if __name__ == "__main__":
    main()
