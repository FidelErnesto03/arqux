"""Tests for arqux.__main__ — python -m arqux entry point."""

from __future__ import annotations


def test_main_module_importable() -> None:
    """__main__ module can be imported without error."""
    import arqux.__main__  # noqa: F401
    assert arqux.__main__.main is not None
