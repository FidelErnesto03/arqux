"""CYCLE-12 / BLP-028 — una entrada llamada ``_`` se puede reparar.

El builder legacy del brain creó entradas cuyo *nombre* es ``_``. El guard de
T-022 rechaza ``_`` como selector porque fue un wildcard heredado, así que el
sistema se negaba a tocar las entradas que él mismo había escrito: no se podían
corregir ni borrar. Con ``force=True`` el selector llega a la entrada exacta;
sin force, el rechazo se mantiene.
"""

from __future__ import annotations

import pytest

from arqux.state import crud_delete, crud_list, crud_update

BRAIN = """$0

$1: LESSONS

LNG:_{type:contextual, cause:"", lesson:"-"}
"""


def _brain(tmp_path) -> str:
    path = tmp_path / "notes.cortex"
    path.write_text(BRAIN, encoding="utf-8")
    return str(path)


def test_update_requires_force(tmp_path):
    path = _brain(tmp_path)
    with pytest.raises(ValueError, match="deprecated and rejected"):
        crud_update(path, "$1/LNG:_", set_={"lesson": "reparada"})

    crud_update(path, "$1/LNG:_", set_={"lesson": "reparada"}, force=True)
    entry = crud_list(path, sigil="LNG")["entries"][0]
    assert entry["value"]["lesson"] == "reparada"


def test_delete_requires_force(tmp_path):
    path = _brain(tmp_path)
    with pytest.raises(ValueError, match="deprecated and rejected"):
        crud_delete(path, "$1/LNG:_")

    crud_delete(path, "$1/LNG:_", force=True)
    assert crud_list(path, sigil="LNG")["entries"] == []


def test_a_named_entry_is_still_reachable_without_force(tmp_path):
    path = tmp_path / "notes.cortex"
    path.write_text(
        '$0\n\n$1: LESSONS\n\nLNG:lesson{type:contextual, cause:"", lesson:"-", prevention:"x"}\n',
        encoding="utf-8",
    )
    crud_update(str(path), "$1/LNG:lesson", set_={"lesson": "sin force"})
    entry = crud_list(str(path), sigil="LNG")["entries"][0]
    assert entry["value"]["lesson"] == "sin force"
