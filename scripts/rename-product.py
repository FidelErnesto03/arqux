#!/usr/bin/env python3
"""Placeholder rename script for Arqux.

Replaces the placeholder product name tokens throughout the package with a
real, user-chosen name. Three casing forms are derived from a single
argument:

    arqux            -> <name>           (lowercase, package/cli/paths)
    ARQUX      -> <NAME>           (uppercase, constants/markers)
    Arqux      -> <Name>           (title case, display names)

Usage:
    python scripts/rename-product.py <name>           # apply rename in-place
    python scripts/rename-product.py <name> --dry-run # preview only, no changes
    python scripts/rename-product.py <name> --verbose # print every file touched

Constraints on the chosen name:
    - Lowercase ASCII letters and digits only (a-z, 0-9).
    - Must start with a letter.
    - Must be a valid Python identifier (no hyphens, no underscores at start).
    - 1-20 characters.

Examples:
    python scripts/rename-product.py kyber
    python scripts/rename-product.py praxis --dry-run
    python scripts/rename-product.py keel --verbose
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# --- Placeholder tokens ----------------------------------------------------

PLACEHOLDER_LOWER = "arqux"
PLACEHOLDER_UPPER = "ARQUX"
PLACEHOLDER_TITLE = "Arqux"

# Order matters: replace the more specific tokens first so we don't partially
# replace `ARQUX` by matching `arqux` first.
ALL_PLACEHOLDERS = (PLACEHOLDER_UPPER, PLACEHOLDER_TITLE, PLACEHOLDER_LOWER)

# Files that contain placeholder tokens and should be content-edited.
# We scan ALL files (no allow-list) so nothing is missed.
SKIP_DIRECTORIES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    "build",
    "dist",
    ".venv",
    "venv",
    "node_modules",
}

# Directory name suffixes to skip (e.g. editable-install metadata).
SKIP_DIR_SUFFIXES = (".egg-info",)
SKIP_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".so",
    ".egg-info",
}

# Files that should never be content-edited (this script itself, for instance).
SKIP_FILES = {
    "rename-product.py",
}


# --- Name validation -------------------------------------------------------

_NAME_RE = re.compile(r"^[a-z][a-z0-9]{0,19}$")


def validate_name(name: str) -> tuple[bool, str]:
    """Validate the chosen name. Returns (ok, reason)."""
    if not name:
        return False, "name is empty"
    if not _NAME_RE.match(name):
        return False, (
            "name must be 1-20 chars, lowercase ASCII letters/digits, "
            "starting with a letter (no hyphens, underscores, or uppercase)"
        )
    return True, ""


def derive_casings(name: str) -> dict[str, str]:
    """Derive the three casing forms from the lowercase name.

    Iteration order is longest-token-first to avoid partial replacements:
    `ARQUX` must be replaced before `arqux`,
    otherwise the latter would corrupt the former into `kyber_UPPER__`.
    """
    return {
        PLACEHOLDER_UPPER: name.upper(),
        PLACEHOLDER_TITLE: name.capitalize(),
        PLACEHOLDER_LOWER: name,
    }


# --- File scanning ---------------------------------------------------------

def should_skip(path: Path) -> bool:
    """Whether a path should be skipped during scanning."""
    parts = path.parts
    for skipped in SKIP_DIRECTORIES:
        if skipped in parts:
            return True
    # Check suffix-based skips (e.g. `*.egg-info`).
    for part in parts:
        for suffix in SKIP_DIR_SUFFIXES:
            if part.endswith(suffix):
                return True
    if path.suffix in SKIP_EXTENSIONS:
        return True
    if path.name in SKIP_FILES:
        return True
    return False


def is_text_file(path: Path) -> bool:
    """Heuristic: try to read as UTF-8; if it fails, treat as binary."""
    try:
        path.read_text(encoding="utf-8")
        return True
    except (UnicodeDecodeError, OSError):
        return False


def replace_in_text(text: str, replacements: dict[str, str]) -> tuple[str, int]:
    """Replace all placeholder tokens in `text`. Returns (new_text, count)."""
    new_text = text
    total = 0
    for token, value in replacements.items():
        count = new_text.count(token)
        if count:
            new_text = new_text.replace(token, value)
            total += count
    return new_text, total


def rename_path(path: Path, replacements: dict[str, str]) -> Path:
    """Rename a single path (file or directory) if its name contains a placeholder."""
    name = path.name
    new_name = name
    for token, value in replacements.items():
        if token in new_name:
            new_name = new_name.replace(token, value)
    if new_name == name:
        return path
    new_path = path.with_name(new_name)
    if new_path.exists() and new_path != path:
        # Conflict — leave the original in place and report.
        print(f"WARNING: cannot rename {path} -> {new_path} (target exists)", file=sys.stderr)
        return path
    path.rename(new_path)
    return new_path


# --- Core rename logic -----------------------------------------------------

def find_repo_root(start: Path) -> Path:
    """Find the repo root by looking for `pyproject.toml`.

    Walks up from `start` (default: cwd) looking for `pyproject.toml`.
    Works both before and after the placeholder has been renamed.
    """
    cursor = start.resolve()
    while True:
        candidate = cursor / "pyproject.toml"
        if candidate.exists():
            return cursor
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    # Fall back to start — better to operate in place than to do nothing.
    return start.resolve()


def collect_files(root: Path) -> list[Path]:
    """Collect all files under root that should be scanned for placeholders."""
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if should_skip(path):
            continue
        if not is_text_file(path):
            continue
        files.append(path)
    return files


def collect_dirs(root: Path) -> list[Path]:
    """Collect all directories under root (excluding skip set) for rename pass.

    Returns deepest-first so renames don't invalidate parent paths.
    """
    dirs: list[Path] = []
    for path in root.rglob("*"):
        if path.is_dir() and not should_skip(path):
            dirs.append(path)
    # Sort by depth descending (deepest first).
    dirs.sort(key=lambda p: len(p.parts), reverse=True)
    return dirs


def apply_rename(root: Path, name: str, dry_run: bool, verbose: bool) -> int:
    """Apply the rename operation. Returns 0 on success, non-zero on error."""
    ok, reason = validate_name(name)
    if not ok:
        print(f"ERROR: invalid name '{name}': {reason}", file=sys.stderr)
        return 2

    replacements = derive_casings(name)

    if dry_run:
        print(f"[DRY-RUN] Preview of rename to '{name}':", file=sys.stderr)
        print(f"  {PLACEHOLDER_LOWER}  -> {replacements[PLACEHOLDER_LOWER]}", file=sys.stderr)
        print(f"  {PLACEHOLDER_UPPER}  -> {replacements[PLACEHOLDER_UPPER]}", file=sys.stderr)
        print(f"  {PLACEHOLDER_TITLE}  -> {replacements[PLACEHOLDER_TITLE]}", file=sys.stderr)
        print(file=sys.stderr)

    # 1. Scan files for content replacements.
    files = collect_files(root)
    total_replacements = 0
    files_modified = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new_text, count = replace_in_text(text, replacements)
        if count == 0:
            continue
        files_modified += 1
        total_replacements += count
        if dry_run:
            rel = f.relative_to(root)
            print(f"  [content] {rel}  ({count} replacements)", file=sys.stderr)
        else:
            f.write_text(new_text, encoding="utf-8")
            if verbose:
                rel = f.relative_to(root)
                print(f"  [content] {rel}  ({count} replacements)")

    # 2. Rename files whose names contain a placeholder.
    file_renames = 0
    for f in collect_files(root):
        if any(token in f.name for token in replacements):
            rel = f.relative_to(root)
            new_name = f.name
            for token, value in replacements.items():
                new_name = new_name.replace(token, value)
            if dry_run:
                print(f"  [rename-file] {rel} -> {new_name}", file=sys.stderr)
                file_renames += 1
            else:
                new_path = rename_path(f, replacements)
                if new_path != f:
                    file_renames += 1
                    if verbose:
                        print(f"  [rename-file] {rel} -> {new_path.relative_to(root)}")

    # 3. Rename directories whose names contain a placeholder (deepest first).
    dir_renames = 0
    for d in collect_dirs(root):
        if any(token in d.name for token in replacements):
            rel = d.relative_to(root)
            new_name = d.name
            for token, value in replacements.items():
                new_name = new_name.replace(token, value)
            if dry_run:
                print(f"  [rename-dir]  {rel} -> {new_name}", file=sys.stderr)
                dir_renames += 1
            else:
                new_path = rename_path(d, replacements)
                if new_path != d:
                    dir_renames += 1
                    if verbose:
                        print(f"  [rename-dir]  {rel} -> {new_path.relative_to(root)}")

    # 4. Summary.
    print(file=sys.stderr)
    if dry_run:
        print(
            f"[DRY-RUN] Would modify {files_modified} files ({total_replacements} replacements), "
            f"rename {file_renames} files and {dir_renames} directories.",
            file=sys.stderr,
        )
    else:
        print(
            f"Done. Modified {files_modified} files ({total_replacements} replacements), "
            f"renamed {file_renames} files and {dir_renames} directories.",
            file=sys.stderr,
        )
        print(f"Next steps:", file=sys.stderr)
        print(f"  pip install -e .", file=sys.stderr)
        print(f"  {name} --version", file=sys.stderr)
        print(f"  {name} init", file=sys.stderr)
        print(f"  {name} serve", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rename-product.py",
        description="Replace the arqux placeholder with a real product name.",
    )
    parser.add_argument(
        "name",
        help="The chosen product name (lowercase, valid Python identifier).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying any files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every file and directory touched.",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=None,
        help="Path to the package root (default: auto-detect).",
    )
    args = parser.parse_args(argv)

    if args.root:
        root = Path(args.root).resolve()
    else:
        # Start from cwd so the script operates on the directory the user
        # invoked it from (consistent with shell UX).
        root = find_repo_root(Path.cwd())

    if not root.exists():
        print(f"ERROR: root path does not exist: {root}", file=sys.stderr)
        return 1

    return apply_rename(root, args.name, dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
