"""El puntero de la ejecución manda sobre la ranura compartida.

El 2026-10-28 otro cliente reescribió ``.arqux/context.cortex`` apuntando a
Manhattan mientras esta ejecución trabajaba en ARQUX: un checkpoint sin ``path``
resolvió el proyecto por esa ranura y escribió el estado de trabajo en el brain
equivocado. El puntero por ejecución (``.arqux/contexts/<exec>.cortex``) tiene
que ganar.
"""

from __future__ import annotations

import hashlib

import pytest

from arqux.core.state import find_project_root


def _pointer(project_root) -> str:
    return f'$1: CURRENT\nCTX:x{{project_root:"{project_root}"}}\n'


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    (ws / ".arqux").mkdir(parents=True)
    (ws / ".arqux" / "meta-brain.cortex").write_text("$0\n", encoding="utf-8")
    for name in ("PROJECT-A", "PROJECT-B"):
        (ws / name / ".arqux").mkdir(parents=True)
        (ws / name / ".arqux" / "brain.cortex").write_text("$0\n", encoding="utf-8")

    key = "exec-20261028"
    readable = key
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    (ws / ".arqux" / "contexts").mkdir()
    (ws / ".arqux" / "contexts" / f"{readable}-{digest}.cortex").write_text(
        _pointer(ws / "PROJECT-B"), encoding="utf-8")
    (ws / ".arqux" / "context.cortex").write_text(
        _pointer(ws / "PROJECT-A"), encoding="utf-8")

    monkeypatch.setattr("arqux.execution.authoritative_execution_key", lambda: key)
    monkeypatch.chdir(ws)
    return ws


def test_the_execution_pointer_wins(workspace):
    assert find_project_root(start=None) == workspace / "PROJECT-B" / ".arqux"


def test_the_shared_slot_is_still_the_fallback(workspace):
    for stale in (workspace / ".arqux" / "contexts").iterdir():
        stale.unlink()
    assert find_project_root(start=None) == workspace / "PROJECT-A" / ".arqux"


def test_without_any_pointer_there_is_no_project(tmp_path, monkeypatch):
    ws = tmp_path / "empty"
    (ws / ".arqux").mkdir(parents=True)
    (ws / ".arqux" / "meta-brain.cortex").write_text("$0\n", encoding="utf-8")
    monkeypatch.setattr("arqux.execution.authoritative_execution_key", lambda: "")
    monkeypatch.chdir(ws)
    assert find_project_root(start=None) is None
