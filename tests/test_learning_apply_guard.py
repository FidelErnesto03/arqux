from __future__ import annotations

from arqux.cortex.transaction import guard_write


def test_guard_write_reverts_collateral_damage(tmp_path):
    target = tmp_path / "brain.cortex"
    before = "$0\n\n$1: A\nX:a{k:1}\n\n$2: B\nY:b{k:2}\n"
    target.write_text(before, encoding="utf-8")
    # Simulate a write that damaged unrelated section $2 while intending $1.
    after = "$0\n\n$1: A\nX:a{k:9}\n\n$2: B\nY:b{k:999}\n"
    target.write_text(after, encoding="utf-8")
    violation = guard_write(str(target), before, allowed_sections=["$1"])
    assert violation is not None
    assert violation.get("rolled_back") is True
    assert "error" in violation and violation["error"]
    assert target.read_text(encoding="utf-8") == before


def test_guard_write_allows_target_section_only(tmp_path):
    target = tmp_path / "brain.cortex"
    before = "$0\n\n$1: A\nX:a{k:1}\n\n$2: B\nY:b{k:2}\n"
    target.write_text(before, encoding="utf-8")
    after = "$0\n\n$1: A\nX:a{k:1}\nX:c{k:3}\n\n$2: B\nY:b{k:2}\n"
    target.write_text(after, encoding="utf-8")
    guard_write(str(target), after, allowed_sections=["$1"])
    # allowed set must include changed target; passing after-as-before equivalent clean case:
    violation2 = guard_write(str(target), before, allowed_sections=["$1"])
    assert violation2 is None
    assert target.read_text(encoding="utf-8") == after
