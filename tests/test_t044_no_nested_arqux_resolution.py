"""CYCLE-12 / BLP-029 — el brain nunca se resuelve dentro de otro ``.arqux``.

El doctor reportaba ``nested .arqux`` como FAIL. El árbol
``.arqux/.arqux/brain.cortex.lock`` no era residuo viejo: se recreaba. El
fallback de resolución del brain añadía ``.arqux`` a una ruta que ya era un
``.arqux``.
"""

from __future__ import annotations

from arqux.pulse import _brain_cortex_path
from arqux.session_identity import brain_lock_path, brain_path


def test_brain_path_does_not_nest_an_arqux_directory(tmp_path):
    arqux_dir = tmp_path / ".arqux"
    arqux_dir.mkdir()

    resolved = brain_path(arqux_dir)
    assert resolved == arqux_dir / "brain.cortex"
    assert resolved.parent.parent == tmp_path


def test_brain_lock_path_does_not_nest(tmp_path):
    arqux_dir = tmp_path / ".arqux"
    arqux_dir.mkdir()

    lock = brain_lock_path(arqux_dir)
    assert lock == arqux_dir / "brain.cortex.lock"
    assert ".arqux/.arqux" not in str(lock)


def test_pulse_brain_path_does_not_nest(tmp_path):
    arqux_dir = tmp_path / ".arqux"
    arqux_dir.mkdir()

    assert _brain_cortex_path(arqux_dir) == arqux_dir / "brain.cortex"


def test_a_project_root_still_resolves_to_its_arqux(tmp_path):
    project = tmp_path / "proj"
    (project / ".arqux").mkdir(parents=True)
    (project / ".arqux" / "brain.cortex").write_text("$0\n", encoding="utf-8")

    assert brain_path(project) == project / ".arqux" / "brain.cortex"
