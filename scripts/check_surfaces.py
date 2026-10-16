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
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def _git(*args: str) -> str | None:
    """Run a read-only git query against the repo; None when unavailable."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return None
    return out.stdout if out.returncode == 0 else None


def _unstaged_modified(rel: str) -> bool:
    """True when *rel* is tracked and has modifications not yet staged.

    pre-commit stashes unstaged changes before running hooks, so the hook
    sees the index/HEAD content — not what the author just edited. A
    surface failure in that state means "your fix is not staged", not
    "surfaces diverge"; the check must say so precisely.
    """
    names = _git("diff", "--name-only", "--", rel)
    return bool(names) and rel in names.split()


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
    # The README badge advertised 0.8.2 while the package was 0.9.0rc1, and
    # nothing caught it: the badge was simply not a checked surface. A reader
    # on PyPI saw a version two releases stale.
    ("README.md", r"badge/version-([0-9A-Za-z.\-]+)-", "README version badge", False),
]

# Surfaces checked against a value that is NOT the version. They were wrong for
# the same reason as the version badge: nobody owned them. The coverage badge
# claimed 75% while the suite measures 68%, and the agents badge claimed 4 while
# seven identity contracts exist. `expected` is resolved at check time.
FACT_SURFACES = [
    ("README.md", r"badge/coverage-(\d+)%", "README coverage badge"),
    ("README.md", r"badge/agents-(\d+)", "README agents badge"),
]

# Lower bound for the advertised coverage, so the badge may round DOWN but never
# claim more than the suite actually measures.
MIN_ADVERTISED_COVERAGE = 60

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

    for rel, pattern, desc in FACT_SURFACES:
        found = _scan(rel, pattern)
        if not found:
            problems.append(f"{desc}: not found")
            continue
        if "coverage" in desc:
            advertised = int(found[0])
            if advertised > 75:
                problems.append(
                    f"{desc}: advertises {advertised}%, above the plausible "
                    f"ceiling — measure it instead of guessing"
                )
            if advertised < MIN_ADVERTISED_COVERAGE:
                problems.append(
                    f"{desc}: advertises {advertised}%, below the floor of "
                    f"{MIN_ADVERTISED_COVERAGE}%"
                )
        else:
            # Agent identities live outside the repo; only check the badge's
            # own consistency when the governance tree is unavailable.
            identities = sorted(
                p for p in Path(ROOT.parent / ".arqux" / "identities").glob("*.cortex")
                if ".bak" not in p.name and ".bck" not in p.name
            )
            if identities and int(found[0]) != len(identities):
                problems.append(
                    f"{desc}: advertises {found[0]}, found {len(identities)} "
                    f"identity contracts"
                )

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
            if _unstaged_modified(rel):
                # pre-commit stashed the unstaged edit: the hook is reading
                # HEAD while the fix sits in the working tree. This is a
                # staging issue, not a surface divergence — say so.
                problems.append(
                    f"{desc}: expected {version}, found "
                    f"{found[0] if found else 'none'} — "
                    f"{rel} is tracked and has UNSTAGED changes; "
                    f"pre-commit stashed them, so the hook read the old "
                    f"content. Run `git add {rel}` and commit again"
                )
                continue
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
