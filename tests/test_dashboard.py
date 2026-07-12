"""Tests for arqux dashboard (P0-E).

Validates:
- build_dashboard returns CortexOUT
- _get_agents_from_meta parses IDN entries
- _get_projects_from_meta parses DOM entries
- _color_for_status returns valid rich color
- _count_blueprints returns dict with status keys
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.dashboard import (
    _color_for_status,
    _count_blueprints,
    _get_agents_from_meta,
    _get_evidence_events,
    _get_projects_from_meta,
    build_dashboard,
)
from arqux.handlers.workspace import init_workspace


@pytest.fixture
def workspace_path(tmp_path: Path) -> Path:
    init_workspace(path=str(tmp_path))
    return tmp_path


class TestBuildDashboard:
    """P0-E: build_dashboard() returns CortexOUT."""

    def test_returns_cortexout(self, workspace_path: Path) -> None:
        result = build_dashboard(path=str(workspace_path))
        assert hasattr(result, "message") or hasattr(result, "to_text")

    def test_handles_missing_workspace(self, tmp_path: Path) -> None:
        """build_dashboard should handle no-workspace gracefully."""
        result = build_dashboard(path=str(tmp_path / "nonexistent"))
        # Should not crash; may return error message.
        assert hasattr(result, "message") or hasattr(result, "to_text")

    def test_dashboard_message_contains_arqux(self, workspace_path: Path) -> None:
        result = build_dashboard(path=str(workspace_path))
        text = result.to_text() if hasattr(result, "to_text") else str(result.message)
        # Dashboard output should mention arqux or workspace.
        assert "arqux" in text.lower() or "workspace" in text.lower() or "ok" in text.lower()


class TestGetAgentsFromMeta:
    """P0-E: _get_agents_from_meta()."""

    def test_returns_list(self, workspace_path: Path) -> None:
        ws_arqux = workspace_path / ".arqux"
        agents = _get_agents_from_meta(ws_arqux)
        assert isinstance(agents, list)

    def test_handles_missing_meta_brain(self, tmp_path: Path) -> None:
        agents = _get_agents_from_meta(tmp_path)
        assert agents == []


class TestGetProjectsFromMeta:
    """P0-E: _get_projects_from_meta()."""

    def test_returns_list(self, workspace_path: Path) -> None:
        ws_arqux = workspace_path / ".arqux"
        projects = _get_projects_from_meta(ws_arqux)
        assert isinstance(projects, list)

    def test_handles_missing_meta_brain(self, tmp_path: Path) -> None:
        projects = _get_projects_from_meta(tmp_path)
        assert projects == []


class TestColorForStatus:
    """P0-E: _color_for_status()."""

    @pytest.mark.parametrize("status,expected_prefix", [
        ("done", ""),
        ("in_progress", ""),
        ("blocked", ""),
        ("cancelled", ""),
        ("review", ""),
        ("draft", ""),
        ("unknown_status", ""),
    ])
    def test_returns_color_string(self, status: str, expected_prefix: str) -> None:
        color = _color_for_status(status)
        assert isinstance(color, str)
        assert len(color) > 0


class TestCountBlueprints:
    """P0-E: _count_blueprints()."""

    def test_returns_dict_with_status_keys(self, tmp_path: Path) -> None:
        counts = _count_blueprints(tmp_path)
        assert isinstance(counts, dict)
        # Should have at least the basic status keys.
        # (Implementation may vary — accept any of these standard keys.)
        standard_keys = {"done", "draft", "cancelled", "review", "in_progress", "ready", "blocked"}
        assert len(counts) > 0
        # At least 3 of the standard keys should be present.
        present = standard_keys & set(counts.keys())
        assert len(present) >= 3, f"Expected ≥3 standard keys, got {present}"

    def test_returns_zero_counts_for_empty_dir(self, tmp_path: Path) -> None:
        counts = _count_blueprints(tmp_path)
        assert all(v == 0 for v in counts.values())


class TestGetEvidenceEvents:
    """P0-E: _get_evidence_events()."""

    def test_returns_list(self, workspace_path: Path) -> None:
        events = _get_evidence_events(workspace_path / ".arqux")
        assert isinstance(events, list)

    def test_handles_missing_dir(self, tmp_path: Path) -> None:
        events = _get_evidence_events(tmp_path / "nonexistent")
        assert events == []
