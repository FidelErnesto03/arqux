"""Tests for arqux.sync — brain synchronization after mutations."""

from __future__ import annotations


def test_sync_brain_none_skips() -> None:
    """sync_brain returns early when project_root is None."""
    from arqux.sync import sync_brain

    # Should not raise — fail-silent
    sync_brain(None, "test.event")


def test_sync_brain_no_brain(tmp_path) -> None:
    """sync_brain skips when brain.cortex does not exist."""
    from arqux.sync import sync_brain

    # Should not raise, just log and return
    sync_brain(tmp_path, "test.event")


def test_sync_brain_with_focus(tmp_path) -> None:
    """sync_brain accepts focus parameter without error."""
    from arqux.sync import sync_brain

    sync_brain(tmp_path, "test.event", focus="testing")


def test_sync_brain_with_detail(tmp_path) -> None:
    """sync_brain accepts detail parameter without error."""
    from arqux.sync import sync_brain

    sync_brain(tmp_path, "test.event", detail="some details")


# ---------------------------------------------------------------------------
# _count_blueprints
# ---------------------------------------------------------------------------


def test_count_blueprints_empty(tmp_path) -> None:
    """_count_blueprints returns all zeros for empty directory."""
    from arqux.sync import _count_blueprints

    counts = _count_blueprints(tmp_path)
    assert counts["done"] == 0
    assert counts["draft"] == 0


def test_count_blueprints_with_files(tmp_path) -> None:
    """_count_blueprints counts blueprints by status."""
    from arqux.sync import _count_blueprints

    cycles_dir = tmp_path / ".arqux" / "cycles"
    cycles_dir.mkdir(parents=True, exist_ok=True)
    (cycles_dir / "BLP-001.md").write_text(
        '---\ncycle_id: "CYCLE-01"\nstatus: "done"\n---\n', encoding="utf-8"
    )
    (cycles_dir / "BLP-002.md").write_text(
        '---\ncycle_id: "CYCLE-01"\nstatus: "draft"\n---\n', encoding="utf-8"
    )

    counts = _count_blueprints(tmp_path)
    assert counts["done"] == 1
    assert counts["draft"] == 1
