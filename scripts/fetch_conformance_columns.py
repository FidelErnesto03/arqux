#!/usr/bin/env python3
"""Fetch the two CODEC-CORTEX conformance columns at pinned refs.

The conformance suites (`tests/test_cortex_two_column_conformance.py` and
`tests/test_cortex_invalid_column_conformance.py`) measure ArqUX against two
engines. Until 2026-10-11 both engines and the corpus were read from absolute
paths under `/home/vatrox/workspace`, so the suites could only ever run on one
machine — while `docs/release/0.9.0-report.md` §3 cites them as reproducible
release evidence. They failed in CI with 5 failures and 8 errors.

Both columns come from the SAME upstream repository, `codec-cortex`, at two
different commits:

    A — fallback 0.6.2   legacy layout `cortex/{core,crud,hcortex}`
    B — candidate rc1    flat layout `codec_cortex`, carries conformance/

Pinning by commit sha (not by tag or branch) is what makes the measurement
reproducible: a tag can move, a branch definitely moves.

Usage:
    python scripts/fetch_conformance_columns.py --dest /tmp/columns
    python scripts/fetch_conformance_columns.py --dest /tmp/columns \\
        --github-env "$GITHUB_ENV"

Stdlib only, like the rest of scripts/.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/FidelErnesto03/codec-cortex.git"

# Column A — the fallback engine. `src/` holds the legacy `cortex` package
# with cortex.core.parser / cortex.core.validator / cortex.hcortex.*.
REF_A = "e68966bab7616180c8cb5ba4214f3ccea154dfab"

# Column B — the candidate engine. Root holds the flat `codec_cortex` package
# and the governed corpus under conformance/.
REF_B = "d850a88df01604c651fc631f3f6a74826072eb2a"

# sha256 of conformance/corpus/manifest.json at REF_B. The corpus is the
# governed artifact the whole matrix is measured against; if it ever changes
# upstream the measurement changes silently, so it is pinned and verified.
CORPUS_MANIFEST_SHA256 = "164c8cc6a54a0f13923fe35b3a3be27d07398f6f8c3bc40fd75b3c290733f780"

COLUMN_A = "column-a"
COLUMN_B = "column-b"


def _run(*args: str, cwd: Path | None = None) -> None:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\n"
            f"stdout: {result.stdout.strip()}\n"
            f"stderr: {result.stderr.strip()}"
        )


def fetch_column(dest: Path, name: str, ref: str) -> Path:
    """Shallow-clone one pinned ref into `dest/name` and return its path."""
    target = dest / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    _run("git", "init", "--quiet", str(target))
    _run("git", "-C", str(target), "remote", "add", "origin", REPO_URL)
    # Fetching by sha requires the server to allow it; GitHub does.
    _run("git", "-C", str(target), "fetch", "--depth", "1", "--quiet", "origin", ref)
    _run("git", "-C", str(target), "checkout", "--quiet", "FETCH_HEAD")
    return target


def verify_corpus(column_b: Path) -> Path:
    """Check the corpus manifest against the pinned digest, then return it."""
    manifest = column_b / "conformance" / "corpus" / "manifest.json"
    if not manifest.is_file():
        raise RuntimeError(
            f"corpus manifest missing at {manifest}. The ref {REF_B[:7]} does "
            f"not carry conformance/corpus — pick a different pinned ref."
        )
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if digest != CORPUS_MANIFEST_SHA256:
        raise RuntimeError(
            "corpus manifest digest mismatch — the governed corpus changed "
            f"upstream and the conformance numbers in "
            f"docs/release/0.9.0-report.md §3 would no longer describe it.\n"
            f"  expected: {CORPUS_MANIFEST_SHA256}\n"
            f"  found:    {digest}\n"
            f"Re-run BLP-001 and re-issue the report before updating this pin."
        )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        default=os.environ.get("CODEC_COLUMNS_DIR", ".cache/codec-columns"),
        help="directory to clone the columns into",
    )
    parser.add_argument(
        "--github-env",
        help="append KEY=value lines to this file (GitHub Actions convention)",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    dest = Path(args.dest).expanduser().resolve()

    def say(message: str) -> None:
        if not args.quiet:
            print(message)

    try:
        say(f"fetching column A ({COLUMN_A}) at {REF_A[:7]}…")
        column_a = fetch_column(dest, COLUMN_A, REF_A)
        say(f"fetching column B ({COLUMN_B}) at {REF_B[:7]}…")
        column_b = fetch_column(dest, COLUMN_B, REF_B)
        manifest = verify_corpus(column_b)
    except (RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    env = {
        "CODEC_ROOT": str(column_b),
        "CODEC_062_PATH": str(column_a / "src"),
        "CODEC_RC1_PATH": str(column_b),
        "CODEC_CORPUS_MANIFEST": str(manifest),
    }
    say("conformance columns ready:")
    for key, value in env.items():
        say(f"  {key}={value}")

    if args.github_env:
        with open(args.github_env, "a", encoding="utf-8") as handle:
            for key, value in env.items():
                handle.write(f"{key}={value}\n")
    else:
        for key, value in env.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
