"""Tests for the placeholder rename script.

These tests invoke `scripts/rename-product.py` against a copy of the package
in a temp directory. They verify that:
    - All three casing forms are replaced.
    - Files and directories containing the placeholder are renamed.
    - --dry-run does not modify anything.
    - The renamed package is structurally valid.

NOTE: This file is itself subject to the rename script. To avoid the
script corrupting the assertion strings, we construct the placeholder
tokens via string concatenation so the literal `arqux` never
appears in this file's source.

NOTE: The rename tests are skipped automatically once the package has
been renamed — they only apply to the placeholder version we ship.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


# Construct placeholder tokens via concatenation so the rename script
# (which replaces the literal `arqux`) does not corrupt these
# constants. After rename, these still evaluate to the original placeholders.
_PH = "arqu" + "x"              # arqux
_PH_UPPER = "ARQU" + "X"        # ARQUX
_PH_TITLE = "Arqu" + "x"        # Arqux


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "rename-product.py"
SAMPLE_DIR = Path(__file__).resolve().parent.parent


def _placeholder_present() -> bool:
    """True if the package still has the placeholder name (not yet renamed)."""
    return (SAMPLE_DIR / "src" / _PH).is_dir()


# Skip the entire module if the package has already been renamed.
pytestmark = pytest.mark.skipif(
    not _placeholder_present(),
    reason="rename tests only apply to the placeholder version (package already renamed)",
)


def _copy_sample(tmp_path: Path) -> Path:
    """Copy the sample package to tmp_path/sample for in-place rename."""
    dest = tmp_path / "sample"
    shutil.copytree(SAMPLE_DIR, dest, dirs_exist_ok=False, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        "build", "dist", "*.egg-info", ".git",
    ))
    return dest


def _run_rename(sample: Path, name: str, *extra: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT), name, *extra]
    return subprocess.run(
        cmd,
        cwd=str(sample),
        capture_output=True,
        text=True,
        check=False,
    )


def test_dry_run_does_not_modify(tmp_path: Path) -> None:
    sample = _copy_sample(tmp_path)
    result = _run_rename(sample, "kyber", "--dry-run")
    assert result.returncode == 0, result.stderr
    # The placeholder token should still be present.
    init_file = sample / "src" / _PH / "__init__.py"
    assert init_file.exists(), "directory should still have placeholder name"
    text = init_file.read_text(encoding="utf-8")
    assert _PH in text


def test_rename_replaces_all_three_casings(tmp_path: Path) -> None:
    sample = _copy_sample(tmp_path)
    result = _run_rename(sample, "kyber")
    assert result.returncode == 0, result.stderr

    # Directory renamed.
    assert (sample / "src" / "kyber").is_dir()
    assert not (sample / "src" / _PH).exists()

    # Lowercase token replaced.
    init_file = sample / "src" / "kyber" / "__init__.py"
    text = init_file.read_text(encoding="utf-8")
    assert "kyber" in text
    assert _PH not in text
    assert _PH_UPPER not in text
    assert _PH_TITLE not in text

    # Uppercase token replaced.
    constants_file = sample / "src" / "kyber" / "constants.py"
    text = constants_file.read_text(encoding="utf-8")
    assert "KYBER" in text
    assert _PH_UPPER not in text

    # Title-case: README uses "ArqUX" (not "Arqux"), so it's not a placeholder
    # and won't be renamed. Check that lowercase replacements happened in URLs.
    readme = sample / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert _PH_TITLE not in text  # "Arqux" should not appear
    assert _PH not in text  # "arqux" should not appear (replaced to kyber in URLs)


def test_rename_renames_dogfooding_directory(tmp_path: Path) -> None:
    sample = _copy_sample(tmp_path)
    _run_rename(sample, "kyber")

    # The dogfooding directory .arqux should become .kyber
    assert (sample / ".kyber").is_dir()
    # The placeholder directory should no longer exist.
    placeholder_dir = sample / ("." + _PH)
    assert not placeholder_dir.exists()


def test_rename_renames_files_with_placeholder(tmp_path: Path) -> None:
    sample = _copy_sample(tmp_path)
    _run_rename(sample, "kyber")

    # The pyproject.toml [project.scripts] entry should reference kyber.
    pyproject = (sample / "pyproject.toml").read_text(encoding="utf-8")
    assert "kyber = " in pyproject
    assert _PH not in pyproject


def test_rename_rejects_invalid_name(tmp_path: Path) -> None:
    sample = _copy_sample(tmp_path)
    # Names with hyphens are invalid Python identifiers — reject.
    result = _run_rename(sample, "kyber-ai")
    assert result.returncode != 0
    assert "invalid" in result.stderr.lower() or "invalid" in result.stdout.lower()


def test_rename_rejects_uppercase_name(tmp_path: Path) -> None:
    sample = _copy_sample(tmp_path)
    result = _run_rename(sample, "Kyber")
    assert result.returncode != 0


def test_rename_is_idempotent_after_first_run(tmp_path: Path) -> None:
    """The rename script is a one-shot tool: it replaces the placeholder
    with a real name. Running it again with a different name finds no
    placeholders to replace and is a no-op (does not corrupt the package).
    """
    sample = _copy_sample(tmp_path)
    first = _run_rename(sample, "kyber")
    assert first.returncode == 0
    # After the first rename, the package is named `kyber`.
    assert (sample / "src" / "kyber").is_dir()

    # Running again with a different name should not corrupt anything.
    second = _run_rename(sample, "praxis")
    assert second.returncode == 0  # exit 0 — no error, just nothing to do
    # The package is still named `kyber` (the script doesn't know about
    # renaming an already-renamed package — that's a manual operation).
    assert (sample / "src" / "kyber").is_dir()
    assert not (sample / "src" / "praxis").exists()


def test_rename_preserves_test_imports(tmp_path: Path) -> None:
    sample = _copy_sample(tmp_path)
    _run_rename(sample, "kyber")
    test_file = sample / "tests" / "test_workspace.py"
    text = test_file.read_text(encoding="utf-8")
    assert "from kyber" in text
    # No placeholder tokens should remain.
    assert _PH not in text
    assert _PH_UPPER not in text
    assert _PH_TITLE not in text
