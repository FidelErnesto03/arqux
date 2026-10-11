#!/usr/bin/env python3
"""Homologation check: a shared value must read the same across every surface.

Canonical sources:
  * handler count -> the live registry (``arqux.handlers.handler_count``)
  * version       -> ``pyproject.toml`` ``[project].version``

Surfaces (docs, skills, meta-brain, release artifacts) are scanned for the
canonical values. Exit 0 when every surface agrees, 1 (with a report)
otherwise. Wired into pre-commit so a commit with divergent surfaces is
blocked instead of propagating the divergence.

Surfaces outside the repo (the workspace ``.arqux/``) are optional: they are
skipped when absent (e.g. in a CI checkout).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def canonical_handler_count() -> int:
    from arqux.handlers import handler_count

    return handler_count()


def canonical_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise SystemExit("pyproject.toml: no [project].version found")
    return m.group(1)


# (relative path, regex with one capture group, description, optional)
COUNT_SURFACES = [
    ("HANDLERS.md", r"Total:\s*\*\*(\d+)\*\*\s*handlers", "HANDLERS.md total", False),
    ("README.md", r"MCP%20Handlers-(\d+)-", "README handlers badge", False),
    ("src/arqux/skills/comms.skill.md", r"(\d+)\s+handlers", "comms.skill (src)", False),
    ("../.arqux/skills/comms.skill.md", r"(\d+)\s+handlers", "comms.skill (workspace)", True),
    (
        "../.arqux/meta-brain.cortex",
        r'DOM:arqux\{[^}]*?handlers:"(\d+)"',
        "meta-brain DOM:arqux handlers",
        True,
    ),
]

VERSION_SURFACES = [
    ("CHANGELOG.md", r"^##\s*\[([^\]]+)\]", "CHANGELOG first entry", False),
]

# .cortex surfaces that must carry the ArqUX version. Optional: absent in a
# CI checkout (the governance tree is not version-controlled).
CORTEX_VERSION_SURFACES = [
    ("../.arqux/meta-brain.cortex", r'DOM:arqux\{[^}]*?version:"([^"]+)"', "meta-brain DOM:arqux version"),
    ("../.arqux/projects.cortex", r'DOM:arqux\{[^}]*?version:"([^"]+)"', "projects DOM:arqux version"),
    (".arqux/brain.cortex", r'ARQX:artifact\{[^}]*?version:"([^"]+)"', "brain ARQX:artifact version"),
]


def _scan(rel: str, pattern: str) -> list[str] | None:
    path = (ROOT / rel).resolve()
    if not path.is_file():
        return None
    return re.findall(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # Machine-readable output for CI, so the workflow compares against the
    # declared surface instead of a hand-kept constant that drifts.
    if "--print-expected-handlers" in argv:
        print(canonical_handler_count())
        return 0
    if "--print-expected-version" in argv:
        print(canonical_version())
        return 0

    count = str(canonical_handler_count())
    version = canonical_version()
    problems: list[str] = []

    for rel, pattern, desc, optional in COUNT_SURFACES:
        found = _scan(rel, pattern)
        if found is None:
            if not optional:
                problems.append(f"{desc}: file not found ({rel})")
            continue
        if not found:
            problems.append(f"{desc}: no handler count found")
            continue
        bad = sorted({v for v in found if v != count})
        if bad:
            problems.append(f"{desc}: expected {count}, found {bad}")

    for rel, pattern, desc, _optional in VERSION_SURFACES:
        found = _scan(rel, pattern)
        if not found:
            problems.append(f"{desc}: no version found")
            continue
        if found[0] != version:
            problems.append(f"{desc}: expected {version}, found {found[0]}")

    for rel, pattern, desc in CORTEX_VERSION_SURFACES:
        found = _scan(rel, pattern)
        if found is None:
            continue  # optional: no workspace cortex present
        if not found or found[0] != version:
            problems.append(f"{desc}: expected {version}, found {found[0] if found else 'none'}")

    for path in sorted((ROOT / "docs" / "release").glob("*-report.md")):
        m = re.search(r"^#\s*ArqUX\s+(\S+)", path.read_text(encoding="utf-8"), re.MULTILINE)
        if not m or m.group(1) != version:
            problems.append(f"{path.name}: expected {version}, found {m.group(1) if m else 'none'}")
    for path in sorted((ROOT / "docs" / "release").glob("benchmark-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            problems.append(f"{path.name}: invalid JSON")
            continue
        if data.get("version") != version:
            problems.append(f"{path.name}: expected {version}, found {data.get('version')}")

    if problems:
        print("SURFACE HOMOLOGATION FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        print(f"\nCanonical: handlers={count}, version={version}")
        return 1
    print(f"surface homologation OK (handlers={count}, version={version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
