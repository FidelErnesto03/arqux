"""Regression tests for T-012 — evidence.list offset pagination.

Covers the ``offset`` parameter on evidence.list: paging through the
brain PULSE trail without overlap, the pagination state fields
(total, returned, offset, next_offset), unchanged defaults
(limit=100, offset=0) and INVALID_ARGS on bad input. Also covers the
``offset``/``limit=None`` support threaded through
read_pulse_from_brain.
"""

from __future__ import annotations

from pathlib import Path

from arqux.handlers import cycle, evidence, project, task, workspace
from arqux.pulse import read_pulse_from_brain


def _proj_with_evidence(workspace_root: Path, governor_ctx, executor_ctx, n: int) -> Path:
    """Init a governed project with one task and *n* evidence events."""
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir))
    cycle.create_cycle(name="C", path=str(project_dir), ctx=governor_ctx)
    task.create_task(obj="Do thing", assignee="test-executor", path=str(project_dir), ctx=governor_ctx)
    for i in range(n):
        evidence.record_evidence(
            task_id="T-001",
            kind="note",
            payload=f"p{i}",
            path=str(project_dir),
            ctx=executor_ctx,
        )
    return project_dir


def test_evidence_list_paginates_across_pages_without_overlap(
    workspace_root: Path, governor_ctx, executor_ctx,
) -> None:
    project_dir = _proj_with_evidence(workspace_root, governor_ctx, executor_ctx, 5)

    page1 = evidence.list_evidence(
        task_id="T-001", limit=2, path=str(project_dir), ctx=executor_ctx,
    )
    assert page1.profile == "OUT-WORK"
    assert page1.fields["total"] == 5
    assert page1.fields["returned"] == 2
    assert page1.fields["offset"] == 0
    assert page1.fields["next_offset"] == 2
    assert page1.fields["events"] == ["E-0001", "E-0002"]

    page2 = evidence.list_evidence(
        task_id="T-001", limit=2, offset=page1.fields["next_offset"],
        path=str(project_dir), ctx=executor_ctx,
    )
    assert page2.fields["total"] == 5
    assert page2.fields["returned"] == 2
    assert page2.fields["offset"] == 2
    assert page2.fields["next_offset"] == 4
    assert page2.fields["events"] == ["E-0003", "E-0004"]

    page3 = evidence.list_evidence(
        task_id="T-001", limit=2, offset=page2.fields["next_offset"],
        path=str(project_dir), ctx=executor_ctx,
    )
    assert page3.fields["total"] == 5
    assert page3.fields["returned"] == 1
    assert page3.fields["offset"] == 4
    assert page3.fields["next_offset"] is None
    assert page3.fields["events"] == ["E-0005"]

    seen = page1.fields["events"] + page2.fields["events"] + page3.fields["events"]
    assert len(seen) == len(set(seen)) == 5


def test_evidence_list_default_unchanged(
    workspace_root: Path, governor_ctx, executor_ctx,
) -> None:
    """Defaults (limit=100, offset=0) return the whole trail as before."""
    project_dir = _proj_with_evidence(workspace_root, governor_ctx, executor_ctx, 3)
    result = evidence.list_evidence(
        task_id="T-001", path=str(project_dir), ctx=executor_ctx,
    )
    assert result.profile == "OUT-WORK"
    assert result.fields["total"] == 3
    assert result.fields["returned"] == 3
    assert result.fields["offset"] == 0
    assert result.fields["next_offset"] is None
    assert result.fields["events"] == ["E-0001", "E-0002", "E-0003"]
    assert "events=3" in result.to_text()
    assert "brain PULSE" in result.to_text()


def test_evidence_list_invalid_offset_and_limit(
    workspace_root: Path, governor_ctx, executor_ctx,
) -> None:
    project_dir = _proj_with_evidence(workspace_root, governor_ctx, executor_ctx, 1)
    for kwargs in ({"offset": -1}, {"limit": 0}, {"offset": "x"}, {"limit": "many"}):
        out = evidence.list_evidence(
            task_id="T-001", path=str(project_dir), ctx=executor_ctx, **kwargs,
        )
        assert out.profile == "OUT-ERROR"
        assert out.fields.get("code") == "INVALID_ARGS"


def test_evidence_list_offset_beyond_total(
    workspace_root: Path, governor_ctx, executor_ctx,
) -> None:
    project_dir = _proj_with_evidence(workspace_root, governor_ctx, executor_ctx, 2)
    out = evidence.list_evidence(
        task_id="T-001", offset=10, path=str(project_dir), ctx=executor_ctx,
    )
    assert out.profile == "OUT-WORK"
    assert out.fields["total"] == 2
    assert out.fields["returned"] == 0
    assert out.fields["offset"] == 10
    assert out.fields["next_offset"] is None
    assert out.fields["events"] == []


def test_read_pulse_from_brain_offset(
    workspace_root: Path, governor_ctx, executor_ctx,
) -> None:
    """read_pulse_from_brain honors offset and unbounded limit."""
    project_dir = _proj_with_evidence(workspace_root, governor_ctx, executor_ctx, 5)

    tail = read_pulse_from_brain(project_dir, limit=None, offset=2)
    assert [e["id"] for e in tail] == ["E-0003", "E-0004", "E-0005"]

    page = read_pulse_from_brain(project_dir, limit=2, offset=1)
    assert [e["id"] for e in page] == ["E-0002", "E-0003"]

    first = read_pulse_from_brain(project_dir, limit=2)
    assert [e["id"] for e in first] == ["E-0001", "E-0002"]
