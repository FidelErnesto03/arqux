"""Tests for CORTEX-OUT output profiles."""

from __future__ import annotations

from arqux.cortex_out import CortexOUT
from arqux.constants import (
    OUT_AUDIT,
    OUT_ERROR,
    OUT_FULL,
    OUT_MIN,
    OUT_WORK,
)


def test_min_profile_format() -> None:
    out = CortexOUT.min("ok", task="T-001", status="in_progress")
    text = out.to_text()
    assert text.startswith(OUT_MIN)
    assert "task=T-001" in text
    assert "status=in_progress" in text
    assert "ok" in text


def test_work_profile_format() -> None:
    out = CortexOUT.work("done", task="T-001", coverage="87%")
    text = out.to_text()
    assert text.startswith(OUT_WORK)
    assert "coverage=87%" in text


def test_audit_profile_format() -> None:
    out = CortexOUT.audit("review", cycle="CYCLE-01", risk="low")
    text = out.to_text()
    assert text.startswith(OUT_AUDIT)
    assert "cycle=CYCLE-01" in text


def test_full_profile_returns_message_only() -> None:
    out = CortexOUT.full("This is a long human-readable explanation.", task="T-001")
    text = out.to_text()
    assert text == "This is a long human-readable explanation."


def test_error_profile_format() -> None:
    out = CortexOUT.error("denied", code="PERMISSION_DENIED", handler="task.create")
    text = out.to_text()
    assert text.startswith(OUT_ERROR)
    assert "code=PERMISSION_DENIED" in text


def test_bool_value_formatting() -> None:
    out = CortexOUT.work("test", flag=True, other=False)
    text = out.to_text()
    assert "flag=true" in text
    assert "other=false" in text


def test_list_value_formatting() -> None:
    out = CortexOUT.work("test", items=["a", "b", "c"])
    text = out.to_text()
    assert "items=a,b,c" in text


def test_profile_classmethod() -> None:
    out = CortexOUT.profile(OUT_MIN, "hello", key="value")
    assert out.profile == OUT_MIN
    assert "key=value" in out.to_text()


def test_dict_value_formatting() -> None:
    out = CortexOUT.work("test", meta={"a": "1", "b": "2"})
    text = out.to_text()
    assert "meta=a:1;b:2" in text


def test_empty_fields() -> None:
    out = CortexOUT.work("no fields")
    assert out.to_text() == "OUT-WORK no fields"


def test_error_with_code_only() -> None:
    out = CortexOUT.error(message="failed")
    assert out.to_text() == "OUT-ERROR failed"
