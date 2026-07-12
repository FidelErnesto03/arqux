"""Tests for arqux.quickstart."""
from __future__ import annotations


def test_quickstart_init_new_workspace(tmp_path, monkeypatch) -> None:
    """quickstart initializes a new workspace and returns instructions."""
    from arqux.quickstart import quickstart

    monkeypatch.chdir(tmp_path)
    result = quickstart(path=str(tmp_path))
    assert "initialized" in result.to_text().lower() or "Workspace initialized" in result.to_text()


def test_quickstart_in_governed(tmp_path) -> None:
    """quickstart in an already-governed workspace skips init."""
    from arqux.handlers.workspace import init_workspace
    from arqux.quickstart import quickstart

    init_workspace(path=str(tmp_path))
    result = quickstart(path=str(tmp_path))
    assert "already governed" in result.to_text().lower()
