"""Brain integrity: no write path may degrade canonical entries.

Issue 2026-10-26 (blocking): the project brain lost five complete lessons and
degraded five more while work was in progress. The corruption signature was
unmistakable:

* lessons renamed to a slug of their first words, truncated to 20 characters
  (``LNG:__for_low_risk__expl``), with ``cause:""`` and no ``prevention``;
* empty entries named ``_``;
* every risk replaced by an identical ``RSK:risk{description:-, mitigation:""}``;
* one lesson stored as serialized text inside another lesson's ``lesson`` field.

Those shapes are produced by ``formats.brain_from_model``, the legacy builder
that turns a free-text ``sections`` dict into CORTEX. Reaching it therefore
means the canonical brain was flattened to text lines and rebuilt — a lossy
round trip. These tests pin every write path that can reach it.
"""

from __future__ import annotations

import re

import pytest

from arqux.state import crud_add, crud_list, read_brain, write_brain_sections

LESSON = {
    "type": "process",
    "lesson": "Operar sobre el flujo vigente y no sobre suposiciones",
    "cause": "Se realinearon items por operar sobre un flujo no vigente",
    "prevention": "Confirmar el flujo antes de ejecutar",
    "status": "current",
}
RISK = {
    "description": "ORA-04031 agota el pool compartido en produccion",
    "mitigation": "Reducir el pool y monitorear",
    "severity": "high",
}


def _brain_path(env):
    return env.proj_root / ".arqux" / "brain.cortex"


def _seed(env):
    path = _brain_path(env)
    crud_add(path, "$7", "LNG", "flujo_vigente_no_suposiciones", dict(LESSON),
             create_section=True, force=True)
    crud_add(path, "$9", "RSK", "ora_04031", dict(RISK),
             create_section=True, force=True)
    return path


def _entries(path, sigil):
    return {e["name"]: e["value"] for e in crud_list(path, sigil=sigil)["entries"]}


def _assert_intact(path):
    lessons = _entries(path, "LNG")
    assert "flujo_vigente_no_suposiciones" in lessons, lessons.keys()
    lesson = lessons["flujo_vigente_no_suposiciones"]
    assert lesson["cause"] == LESSON["cause"]
    assert lesson["prevention"] == LESSON["prevention"]
    assert lesson["type"] == LESSON["type"]

    risks = _entries(path, "RSK")
    assert "ora_04031" in risks, risks.keys()
    assert risks["ora_04031"]["mitigation"] == RISK["mitigation"]
    assert risks["ora_04031"]["severity"] == RISK["severity"]

    assert not [n for n in list(lessons) + list(risks) if n in ("", "_")]


def test_legacy_rewrite_is_refused_for_a_canonical_brain(arqux_env):
    path = _seed(arqux_env)

    frontmatter, sections, _ = read_brain(arqux_env.proj_root)
    with pytest.raises(ValueError, match="legacy sections model"):
        write_brain_sections(arqux_env.proj_root, frontmatter, sections)

    _assert_intact(path)


def test_session_release_preserves_canonical_entries(arqux_env):
    from arqux.sessions import add_session_to_brain, remove_session_from_brain

    path = _seed(arqux_env)
    add_session_to_brain(arqux_env.proj_root, "test-governor", "governor")
    remove_session_from_brain(arqux_env.proj_root, "test-governor")

    _assert_intact(path)


def test_checkpoint_preserves_canonical_entries(arqux_env):
    from arqux.handlers.cortex.checkpoint import checkpoint_handler

    path = _seed(arqux_env)
    checkpoint_handler(
        content="fcs:arreglar el brain; obj:no perder lecciones; tasks:none",
        path=str(arqux_env.proj_root),
    )

    _assert_intact(path)


def test_cycle_close_preserves_entries_and_writes_structured_lessons(arqux_env):
    from arqux.handlers.cycle import close_cycle
    from arqux.state import cycle_dir

    path = _seed(arqux_env)
    tasks_dir = cycle_dir(arqux_env.proj_root / ".arqux", arqux_env.cycle_id) / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "T-001.cortex").write_text(
        '---\nid: "T-001"\nstatus: done\n---\n', encoding="utf-8"
    )

    result = close_cycle(
        arqux_env.cycle_id, summary="cierre de prueba",
        path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
    )
    assert result.profile == "OUT-WORK"

    _assert_intact(path)
    lessons = _entries(path, "LNG")
    generated = [v for k, v in lessons.items() if k.endswith("_completion")]
    assert generated, lessons.keys()
    assert generated[0]["cause"] and generated[0]["prevention"]
    assert generated[0]["type"] == "process"


def test_legacy_builder_never_creates_empty_or_duplicate_names():
    from arqux.formats import brain_from_model

    text = brain_from_model(
        {"level": 2, "name": "brain", "brain_version": "1"},
        {
            "LESSONS": "-\n- ORA-04031 agota el pool\n- ORA-04031 agota el pool",
            "RISKS": "-\n- Riesgo de migracion\n- Riesgo de migracion",
        },
    )

    assert "LNG:_{" not in text
    assert "RSK:risk{" not in text
    lessons = re.findall(r"^LNG:([A-Za-z0-9_]+)\{", text, re.M)
    risks = re.findall(r"^RSK:([A-Za-z0-9_]+)\{", text, re.M)
    assert len(lessons) == len(set(lessons)) == 2, lessons
    assert len(risks) == len(set(risks)) == 2, risks
