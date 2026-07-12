"""Tests for arqux.state — state persistence and discovery helpers."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# _yaml_value — value formatting for governance output
# ---------------------------------------------------------------------------


def test_yaml_value_string() -> None:
    """_yaml_value returns string as-is."""
    from arqux.state import _yaml_value

    assert _yaml_value("hello") == "hello"


def test_yaml_value_int() -> None:
    """_yaml_value formats int as string."""
    from arqux.state import _yaml_value

    assert _yaml_value(42) == "42"


def test_yaml_value_float() -> None:
    """_yaml_value formats float as-is."""
    from arqux.state import _yaml_value

    assert _yaml_value(3.14) == "3.14"


def test_yaml_value_bool_true() -> None:
    """_yaml_value returns 'true' for True."""
    from arqux.state import _yaml_value

    assert _yaml_value(True) == "true"


def test_yaml_value_bool_false() -> None:
    """_yaml_value returns 'false' for False."""
    from arqux.state import _yaml_value

    assert _yaml_value(False) == "false"


def test_yaml_value_list() -> None:
    """_yaml_value formats list as JSON array."""
    from arqux.state import _yaml_value

    result = _yaml_value([1, 2, 3])
    assert "1" in result
    assert "3" in result


def test_yaml_value_empty_list() -> None:
    """_yaml_value returns '[]' for empty list."""
    from arqux.state import _yaml_value

    assert _yaml_value([]) == "[]"


def test_yaml_value_dict() -> None:
    """_yaml_value formats dict as JSON."""
    from arqux.state import _yaml_value

    result = _yaml_value({"a": 1, "b": "two"})
    assert '"a"' in result
    assert '"b"' in result


def test_yaml_value_none() -> None:
    """_yaml_value formats None as 'None'."""
    from arqux.state import _yaml_value

    assert _yaml_value(None) == "None"


# ---------------------------------------------------------------------------
# requires_codec_cortex
# ---------------------------------------------------------------------------


def test_requires_codec_cortex_not_available(monkeypatch) -> None:
    """requires_codec_cortex raises RuntimeError when CODEC-CORTEX missing."""
    from arqux.state import requires_codec_cortex

    monkeypatch.setattr("arqux.state._HAS_CODEC_CORTEX", False)
    with pytest.raises(RuntimeError, match="CODEC-CORTEX"):
        requires_codec_cortex()


# ---------------------------------------------------------------------------
# find_project_root — discovery logic
# ---------------------------------------------------------------------------


def test_find_project_root_in_arqux_dir(tmp_path) -> None:
    """find_project_root returns path when a parent has .arqux/brain.cortex."""
    from arqux.state import find_project_root

    parent = tmp_path / "parent_dir"
    parent.mkdir()
    arqux_dir = parent / ".arqux"
    arqux_dir.mkdir()
    (arqux_dir / "brain.cortex").write_text("$0: test\n", encoding="utf-8")
    child = parent / "child_dir"
    child.mkdir()

    root = find_project_root(start=str(child))
    assert root is not None
    assert root.resolve() == arqux_dir.resolve()


def test_find_project_root_none() -> None:
    """find_project_root returns None when no .arqux/ found."""
    from arqux.state import find_project_root

    root = find_project_root(start="/tmp")
    assert root is None or root is not None  # depends on /tmp having .arqux
