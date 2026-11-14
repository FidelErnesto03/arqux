#!/usr/bin/env python3
"""Dialect conformance — how many .cortex artifacts does codec-cortex 1.0 parse?

BLP-001 (CYCLE-16) instrument. It measures, it does not migrate: the migration
tool (scripts/migrate_dialect.py) verifies every file through this same parser
before writing anything.

The count this prints is the scope. Never hardcode it — the corpus derives with
normal workspace use.

Usage:
    python scripts/dialect_conformance.py --root /home/vatrox/workspace
    python scripts/dialect_conformance.py --root . --corpus migrable --report out.txt
    python scripts/dialect_conformance.py --root . --count
    python scripts/dialect_conformance.py --root . --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKIP_DIRS = {
    ".venv",
    ".venv-voice",
    "node_modules",
    "archive",
    "__pycache__",
    ".git",
    "site-packages",
    "UTILS",
}

# Ephemeral or historical artifacts: archived, not migrated (BLP-001 §6).
EPHEMERAL_DIRS = {"contexts", "timelog"}


def iter_cortex_files(root: Path, corpus: str = "vivo"):
    """Yield every .cortex file in scope under root.

    Scope is the governance trees of the ecosystem (BLP-001 §6):
      <root>/ARQUX/.arqux and <root>/ARQUX/src
      <root>/Proyecto_X/.arqux
      <root>/.arqux            (workspace meta-brain, agents, contexts, templates)

    corpus="vivo"     -> everything except build dirs and caches
    corpus="migrable" -> also excludes ephemeral/historical artifacts
    """
    trees = [
        root / "ARQUX" / ".arqux",
        root / "ARQUX" / "src",
        root / "Proyecto_X" / ".arqux",
        root / ".arqux",
    ]
    seen: set[Path] = set()
    for tree in trees:
        if not tree.exists():
            continue
        for path in sorted(tree.rglob("*.cortex")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            rel_parts = set(path.relative_to(root).parts[:-1])
            if rel_parts & SKIP_DIRS:
                continue
            if corpus == "migrable" and rel_parts & EPHEMERAL_DIRS:
                continue
            yield path


def parse_with_codec_1(path: Path) -> tuple[bool, str, str]:
    """Parse one file with codec-cortex 1.0. Returns (ok, code, detail)."""
    try:
        from codec_cortex.dispatcher import parse_cortex
    except ImportError:
        return False, "NO_CODEC_1", "codec_cortex not importable in this interpreter"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return False, "UNREADABLE", str(exc)

    # Two legacy shapes are not CORTEX artifacts and are declared out of scope in
    # BLP-001 §6: markdown tasks (frontmatter + ``# OBJ`` headers) and artifacts
    # whose YAML frontmatter precedes ``$0``. They are reported as SKIP rather
    # than FAIL so the migration target stays honest about its boundary.
    if text.lstrip().startswith("---"):
        return True, "SKIP_LEGACY_FRONTMATTER", "YAML frontmatter precedes $0"
    if not re.search(r"^[ \t]*\$0[ \t]*$", text, re.M):
        return True, "SKIP_NOT_CORTEX", "no $0 kernel"

    try:
        doc = parse_cortex(text)
        version = getattr(doc, "cortex_version", "?")
        return True, f"v{version}", ""
    except Exception as exc:  # noqa: BLE001 - the parser raises vendor errors
        code = getattr(exc, "code", "") or type(exc).__name__
        return False, str(code), str(exc).split("\n")[0][:160]


def _safe(rel: str) -> str:
    """Make a relative path safe for line-oriented reports.

    The workspace contains at least one artifact whose filename embeds a literal
    newline (``handoffs/jarvis\\nsummary:...``). Emitting it verbatim splits one
    file into two report lines and breaks every downstream count.
    """
    return rel.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="/home/vatrox/workspace")
    ap.add_argument("--corpus", choices=["vivo", "migrable"], default="vivo")
    ap.add_argument("--report", help="write per-file verdicts here")
    ap.add_argument("--count", action="store_true", help="print only the file count")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--fail-on-error", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        print(f"ERROR: root not found: {root}", file=sys.stderr)
        return 2

    files = list(iter_cortex_files(root, args.corpus))

    if args.count:
        print(len(files))
        return 0

    rows, passed, failed = [], 0, 0
    for path in files:
        ok, code, detail = parse_with_codec_1(path)
        rel = _safe(str(path.relative_to(root)))
        rows.append({"file": rel, "ok": ok, "code": code, "detail": detail})
        if ok:
            passed += 1
        else:
            failed += 1

    if args.json:
        print(json.dumps(
            {"root": str(root), "corpus": args.corpus, "total": len(files),
             "pass": passed, "fail": failed, "files": rows},
            indent=2, ensure_ascii=False))
    else:
        for r in rows:
            status = "PASS" if r["ok"] else "FAIL"
            line = f"{status} {r['code']:<28} {r['file']}"
            if not r["ok"] and r["detail"]:
                line += f"  # {r['detail']}"
            print(line)
        print()
        print(f"total={len(files)} pass={passed} fail={failed} corpus={args.corpus}")

    if args.report:
        out = Path(args.report).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for r in rows:
                status = "PASS" if r["ok"] else "FAIL"
                fh.write(f"{status}\t{r['code']}\t{r['file']}\n")
        print(f"report -> {out}")

    if args.fail_on_error and failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
