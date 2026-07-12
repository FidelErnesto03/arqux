"""Tests for arqux.plantuml — PlantUML integration."""

from __future__ import annotations


def test_is_available_no_java(monkeypatch) -> None:
    """is_available returns False when java is not in PATH."""
    from arqux.plantuml import is_available

    monkeypatch.setattr("arqux.plantuml.shutil.which", lambda _: None)
    assert is_available() is False
