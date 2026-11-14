"""Documentation surfaces must match executed reality.

Every claim checked here was wrong at least once (2026-11-13 surface audit):
a stale version fallback, a quickstart path pointing inside `.arqux/`, an
evidence file that does not exist, and counts that drift from the registry.
"""

from __future__ import annotations

import re
from pathlib import Path

from arqux.constants import ARQUX_VERSION
from arqux.handlers import handler_count

ROOT = Path(__file__).resolve().parents[2]


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml has no version"
    return match.group(1)


def test_version_surfaces_agree():
    """pyproject and the package runtime must report the same version."""
    assert _pyproject_version() == ARQUX_VERSION


def test_readme_badge_matches_version():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"version-{_pyproject_version()}-" in readme


def test_handler_counts_match_registry():
    expected = handler_count()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    handlers = (ROOT / "HANDLERS.md").read_text(encoding="utf-8")
    assert f"MCP%20Handlers-{expected}-" in readme
    assert f"Total: **{expected}** handlers" in handlers


def test_entry_docs_have_no_stale_paths():
    for name in ("README.md", "docs/guides/GETTING_STARTED.md", "PILOT_MODE.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert ".arqux/AGENTS.md" not in text, f"{name}: AGENTS.md lives at the root"
        assert "pulse.jsonl" not in text, f"{name}: PULSE lives inside brain.cortex"


def test_quickstart_requires_pre_flag_for_rc():
    version = _pyproject_version()
    if "rc" in version or "a" in version or "b" in version:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        assert "pip install --pre arqux" in readme


def test_readme_quickstart_points_to_root_agents_md():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert 'cat AGENTS.md' in readme


def test_changelog_first_entry_matches_version():
    """The repo's surface-homologation contract: the first CHANGELOG entry is
    the canonical version."""
    version = _pyproject_version()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## \[([^\]]+)\]", changelog, re.MULTILINE)
    versioned = [h for h in headings if h.strip().lower() != "unreleased"]
    assert versioned and versioned[0] == version, (versioned[:2], version)
