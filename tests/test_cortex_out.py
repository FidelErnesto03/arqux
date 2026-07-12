"""Tests for arqux.cortex_out — profile-based output protocol."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# CortexOUT profile factories
# ---------------------------------------------------------------------------


def test_min_profile() -> None:
    """CortexOUT.min builds a MIN profile with correct prefix."""
    from arqux.cortex_out import CortexOUT

    msg = CortexOUT.min()
    assert msg.profile == "OUT-MIN"


def test_work_profile() -> None:
    """CortexOUT.work builds a WORK profile."""
    from arqux.cortex_out import CortexOUT

    msg = CortexOUT.work("task done")
    assert msg.profile == "OUT-WORK"
    assert "task done" in msg.to_text()


def test_audit_profile() -> None:
    """CortexOUT.audit builds an AUDIT profile."""
    from arqux.cortex_out import CortexOUT

    msg = CortexOUT.audit(cycle="CYCLE-01", risk="low")
    assert msg.profile == "OUT-AUDIT"
    assert "CYCLE-01" in msg.to_text()


def test_full_profile() -> None:
    """CortexOUT.full builds a FULL profile with raw message."""
    from arqux.cortex_out import CortexOUT

    msg = CortexOUT.full("Detailed analysis\nMulti-line content")
    assert msg.profile == "OUT-FULL"
    text = msg.to_text()
    assert text == "Detailed analysis\nMulti-line content"


def test_error_profile() -> None:
    """CortexOUT.error builds an ERROR profile."""
    from arqux.cortex_out import CortexOUT

    msg = CortexOUT.error(code="NOT_FOUND", reason="missing")
    assert msg.profile == "OUT-ERROR"
    assert "NOT_FOUND" in msg.to_text()


# ---------------------------------------------------------------------------
# to_text field formatting
# ---------------------------------------------------------------------------


def test_to_text_boolean_fields() -> None:
    """to_text formats booleans as 'true'/'false'."""
    from arqux.cortex_out import CortexOUT

    msg = CortexOUT.work(ok=True, failed=False)
    text = msg.to_text()
    assert "ok=true" in text
    assert "failed=false" in text


def test_to_text_list_fields() -> None:
    """to_text formats lists as comma-separated."""
    from arqux.cortex_out import CortexOUT

    msg = CortexOUT.work(items=["a", "b", "c"])
    text = msg.to_text()
    assert "items=a,b,c" in text


def test_to_text_dict_fields() -> None:
    """to_text formats dicts as semicolon-separated key:value."""
    from arqux.cortex_out import CortexOUT

    msg = CortexOUT.work(mapping={"x": "1", "y": "2"})
    text = msg.to_text()
    assert "mapping=x:1;y:2" in text


def test_custom_profile_apid() -> None:
    """CortexOUT.profile() builds a custom profile response."""
    from arqux.cortex_out import CortexOUT

    msg = CortexOUT.profile("CUSTOM", message="hello", status="ok")
    text = msg.to_text()
    assert text.startswith("CUSTOM")
    assert "status=ok" in text
    assert "hello" in text


# ---------------------------------------------------------------------------
# format_status
# ---------------------------------------------------------------------------


def test_format_status_min(tmp_path) -> None:
    """format_status with OUT_MIN profile returns minimal line."""
    from arqux.cortex_out import format_status

    result = format_status(tmp_path, profile="OUT-MIN")
    assert result.startswith("OUT-MIN")
    assert "workspace=" in result


def test_format_status_work(tmp_path) -> None:
    """format_status with OUT_WORK profile checks manifest."""
    from arqux.cortex_out import format_status

    result = format_status(tmp_path, profile="OUT-WORK")
    assert result.startswith("OUT-WORK")
    assert "manifest=no" in result


def test_format_status_work_with_manifest(tmp_path) -> None:
    """format_status OUT_WORK shows manifest=yes when manifest.cortex exists."""
    from arqux.cortex_out import format_status

    (tmp_path / "manifest.cortex").write_text("test", encoding="utf-8")
    result = format_status(tmp_path, profile="OUT-WORK")
    assert "manifest=yes" in result


def test_format_status_audit(tmp_path) -> None:
    """format_status with OUT_AUDIT profile lists directory contents."""
    from arqux.cortex_out import format_status

    (tmp_path / "test_file.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "test_dir").mkdir()

    result = format_status(tmp_path, profile="OUT-AUDIT")
    assert result.startswith("OUT-AUDIT")
    assert "test_file.txt" in result
    assert "test_dir" in result


def test_format_status_full(tmp_path) -> None:
    """format_status with OUT_FULL profile returns descriptive text."""
    from arqux.cortex_out import format_status

    result = format_status(tmp_path, profile="OUT-FULL")
    assert "Workspace" in result
    assert str(tmp_path) in result


def test_format_status_unknown_profile(tmp_path) -> None:
    """format_status with unknown profile returns ERROR."""
    from arqux.cortex_out import format_status

    result = format_status(tmp_path, profile="UNKNOWN")
    assert "ERROR" in result
