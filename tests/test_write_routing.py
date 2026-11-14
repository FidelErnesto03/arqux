"""T-003 — a write must never land in a foreign project.

Two incidents on 2026-11-14, both returning `ok`:

1. 14 ``blueprint.update`` calls with ``cycle=CYCLE-16`` wrote into CYCLE-14,
   corrupting two ``done`` blueprints of a closed cycle.
2. ``task.create`` wrote T-009 into ``CODEC-CORTEX/.arqux/cycles/CYCLE-03`` —
   another project — while the handler reported success.

Mechanism: ``find_project_root`` falls back to ``.arqux/context.cortex``, a
single workspace slot any execution can overwrite. That is fine for reading and
dangerous for writing.

``find_write_project_root`` is the contract this suite pins: a write resolves
only from an explicit path, the cwd walk-up, or THIS execution's pointer. When
it cannot be sure it returns ``None`` so the caller fails loudly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from arqux.core.state._project import find_project_root, find_write_project_root


def _make_project(root: Path, name: str) -> Path:
    """Create a minimal project with a brain; return the project root."""
    project = root / name
    (project / ".arqux").mkdir(parents=True)
    (project / ".arqux" / "brain.cortex").write_text(
        '$0\n\n$1: IDENTITY\n\nIDN:x{name:"x"}\n', encoding="utf-8"
    )
    return project


def _make_workspace(tmp_path: Path, pointed_at: Path | None) -> Path:
    """Create a workspace with a global context pointer to ``pointed_at``."""
    ws = tmp_path / "ws"
    (ws / ".arqux").mkdir(parents=True)
    (ws / ".arqux" / "meta-brain.cortex").write_text("$0\n", encoding="utf-8")
    if pointed_at is not None:
        (ws / ".arqux" / "context.cortex").write_text(
            f'$0\n\nCTX:c{{project:"otro", project_root:"{pointed_at}"}}\n',
            encoding="utf-8",
        )
    return ws


def test_write_ignores_the_shared_pointer(tmp_path: Path, monkeypatch) -> None:
    """A stale global pointer must not decide where a write goes.

    This is incident 2: the shared slot pointed at a different project and
    ``task.create`` wrote a task there.
    """
    foreign = _make_project(tmp_path, "CODEC-CORTEX")
    ws = _make_workspace(tmp_path, pointed_at=foreign)

    neutral = tmp_path / "neutral"
    neutral.mkdir()
    monkeypatch.chdir(neutral)
    monkeypatch.setattr(
        "arqux.core.state._project.find_workspace_root", lambda *a, **k: ws / ".arqux"
    )

    # Reading may still answer from the shared slot…
    assert find_project_root(None) == foreign / ".arqux"

    # …writing must not.
    assert find_write_project_root(None) is None


def test_write_resolves_from_explicit_path(tmp_path: Path) -> None:
    """An explicit path is unambiguous and always wins."""
    project = _make_project(tmp_path, "ARQUX")
    assert find_write_project_root(project) == project / ".arqux"


def test_write_resolves_from_cwd_walk_up(tmp_path: Path, monkeypatch) -> None:
    """Running inside a project resolves without any pointer at all."""
    project = _make_project(tmp_path, "ARQUX")
    nested = project / "src" / "deep"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert find_write_project_root(None) == project / ".arqux"


def test_write_never_returns_a_project_outside_the_given_path(
    tmp_path: Path, monkeypatch
) -> None:
    """Incident 1: a cycle-qualified write must not escape to another project.

    The caller passed CYCLE-16; the handler resolved CYCLE-14 through the shared
    pointer. With the write resolver, an unrelated cwd yields no project.
    """
    foreign = _make_project(tmp_path, "ARQUX")
    _make_workspace(tmp_path, pointed_at=foreign)

    neutral = tmp_path / "elsewhere"
    neutral.mkdir()
    monkeypatch.chdir(neutral)

    resolved = find_write_project_root(None)
    # Either no project, or the cwd's own — never the foreign one via the slot.
    assert resolved is None or str(resolved).startswith(str(neutral))


@pytest.mark.parametrize("stem", ["task", "blueprint", "cycle"])
def test_handlers_do_not_call_find_project_root_for_writes(stem: str) -> None:
    """The write handlers must use the write resolver, not the read one."""
    path = Path(__file__).resolve().parent.parent / "src" / "arqux" / "handlers" / f"{stem}.py"
    if not path.exists():
        pytest.skip(f"{stem}.py not present")
    source = path.read_text(encoding="utf-8")
    # The import of find_project_root is allowed only if unused afterwards.
    body = source.split("def ", 1)[-1]
    assert "find_project_root(start=" not in body, (
        f"{stem}.py still resolves writes through find_project_root(start=…): "
        "a stale workspace pointer can redirect them to another project"
    )
