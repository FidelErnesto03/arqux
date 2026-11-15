"""Regression tests for LNG entry naming (BUG-1 follow-up).

The entry name used to be the first word of the lesson prose, so
``alfred.cortex`` accumulated ``LNG:al`` x10, ``LNG:en`` x9, ``LNG:el`` x9 and
51 E008 duplicate entries. Entry identity must not come from prose.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from arqux.handlers import cortex as cortex_handlers
from arqux.handlers.cortex.learning import (
    _derive_lesson_name,
    _ensure_lessons_section,
    _lessons_section_for,
)
from arqux.permissions import PermissionContext


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """Project root with brain.cortex ($8) + workspace identities dir.

    Architect rule 2026-11-15: lessons are filed ONLY in brain.cortex $8;
    identity files are never written by ``identity.record``.
    """
    d = tmp_path / ".arqux" / "identities"
    d.mkdir(parents=True)
    (d / "test-agent.cortex").write_text(
        "$0\n\n"
        "# -- $0: GLOSSARY --\n\n"
        "$1: IDENTITY\n\n"
        'IDN:test-agent{name:"TestAgent", role:"executor"}\n\n'
        "$5: LIMITS\n\n"
        "$6: BEHAVIORAL LESSONS\n\n"
    )
    (tmp_path / ".arqux" / "brain.cortex").write_text(
        "$0\n\n"
        "$2: FOCUS\n"
        'FCS:current{what:"tests", priority:"high", survive:"work", status:"current"}\n\n'
        'OBJ:current{goal:"tests pass", success:"green", survive:"work", status:"current"}\n\n'
        "$8: LESSONS\n\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def ctx() -> PermissionContext:
    return PermissionContext(agent_id="test-agent", role="executor")


def _names(path: Path) -> list[str]:
    text = (path / ".arqux" / "brain.cortex").read_text()
    # Skip the $0 glossary block — executable declarations like
    # ``LNG:lesson{...}`` are contracts, not lesson entries.
    for hdr in re.finditer(r"(?m)^\$(\d+)", text):
        if hdr.group(1) != "0":
            text = text[hdr.start():]
            break
    return re.findall(r"^LNG:([A-Za-z0-9_]+)", text, re.M)


class TestDeriveLessonName:
    """Unit level: the naming rule itself."""

    def test_free_first_word_is_used(self) -> None:
        assert _derive_lesson_name("Antes de asumir...", set()) == "antes"

    def test_explicit_name_wins(self) -> None:
        assert _derive_lesson_name("Al handler...", {"al"}, "mi_regla") == "mi_regla"

    def test_explicit_name_is_not_truncated(self) -> None:
        """Explicit names are honoured in full — the 30-char cap only
        applies to auto-derived names (silent-truncation fix)."""
        long_name = "regla_de_verificacion_posterior_a_escritura"  # 44 chars
        assert len(long_name) > 30
        assert _derive_lesson_name("Al handler...", set(), long_name) == long_name

    def test_explicit_name_still_slugified(self) -> None:
        """Explicit intent wins on length, not on charset: names are still
        normalized to a valid CORTEX entry name."""
        assert (
            _derive_lesson_name("Al handler...", set(), "Mi Regla Larga!")
            == "mi_regla_larga"
        )

    def test_derived_name_stays_capped(self) -> None:
        """The 30-char cap still applies to names derived from prose."""
        lesson = "Supercalifragilisticoespialidosamente larga leccion..."
        name = _derive_lesson_name(lesson, set())
        assert len(name) <= 30

    def test_explicit_long_name_lands_in_brain(
        self, workspace_root: Path, ctx: PermissionContext
    ) -> None:
        long_name = "verificacion_de_artefactos_despues_de_cada_escritura"
        assert len(long_name) > 30
        cortex_handlers.record_lesson_handler(
            lesson="Al escribir...", kind="rule", cause="c", prevention="p",
            name=long_name, path=str(workspace_root), ctx=ctx,
        )
        assert long_name in _names(workspace_root)

    def test_collision_is_disambiguated(self) -> None:
        n1 = _derive_lesson_name("Al primer caso...", {"al"})
        n2 = _derive_lesson_name("Al segundo caso...", {"al"})
        assert n1 != n2
        assert n1.startswith("al_") and n2.startswith("al_")

    def test_same_lesson_is_idempotent(self) -> None:
        """Re-recording the same lesson must not grow a new suffix."""
        lesson = "Al repetir la leccion..."
        first = _derive_lesson_name(lesson, {"al"})
        second = _derive_lesson_name(lesson, {"al", first})
        assert first == second

    def test_articles_no_longer_collide(self) -> None:
        """The exact distribution found in the real identity file."""
        taken: set[str] = set()
        lessons = [
            "Al escribir un artefacto...", "Al reescribir una seccion...",
            "En un handler...", "En la sesion...", "En migracion...",
            "El selector usaba...", "El campo es opcional...", "El contrato manda...",
        ]
        names = []
        for lesson in lessons:
            n = _derive_lesson_name(lesson, taken)
            names.append(n)
            taken.add(n)
        assert len(set(names)) == len(lessons)


class TestRecordLessonIntegration:
    """Handler level: two same-article lessons land as two distinct entries."""

    def test_two_articles_do_not_collide(
        self, workspace_root: Path, ctx: PermissionContext
    ) -> None:
        for lesson in (
            "Al escribir un artefacto se pierde estructura",
            "Al reescribir una seccion se duplica el header",
        ):
            cortex_handlers.record_lesson_handler(
                lesson=lesson, kind="rule", cause="c", prevention="p",
                path=str(workspace_root), ctx=ctx,
            )
        names = _names(workspace_root)
        assert len(names) == 2, names
        assert len(set(names)) == 2, names

    def test_explicit_name_is_honoured(
        self, workspace_root: Path, ctx: PermissionContext
    ) -> None:
        cortex_handlers.record_lesson_handler(
            lesson="Al escribir...", kind="rule", cause="c", prevention="p",
            name="escritura_estructura", path=str(workspace_root), ctx=ctx,
        )
        assert "escritura_estructura" in _names(workspace_root)


def test_lessons_land_in_brain_and_identity_untouched(
    workspace_root: Path, ctx: PermissionContext
) -> None:
    """identity.record files lessons in brain $8 — never in the identity.

    Architect rule 2026-11-15: brain.cortex is the ONLY lesson surface.
    The identity file must remain byte-identical after recording.
    """
    identity_file = (
        workspace_root / ".arqux" / "identities" / "test-agent.cortex"
    )
    before = identity_file.read_text()
    cortex_handlers.record_lesson_handler(
        lesson="Al escribir un artefacto...", kind="rule", cause="c",
        prevention="p", path=str(workspace_root), ctx=ctx,
    )
    assert identity_file.read_text() == before, (
        "identity file was mutated by identity.record"
    )
    brain = (workspace_root / ".arqux" / "brain.cortex").read_text()
    assert "LNG:" in brain.split("$8:")[1]


# --- Lessons section resolution ---------------------------------------------
#
# Identity files do not share a section layout. In this workspace governor
# keeps lessons in $5, alfred/jarvis in $6, heimdall/seshat use $6 for
# EXPERTISE, and auditor/executor have no lessons section at all. Hardcoding an
# id files lessons under DESCRIPTION or EXPERTISE.


class TestLessonsSectionResolution:
    def _write(self, root: Path, headers: str) -> Path:
        d = root / ".arqux" / "identities"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "test-agent.cortex"
        f.write_text(f"$0\n\n# -- $0: GLOSSARY --\n\n{headers}")
        return f

    def test_six_lesson_layout(self, tmp_path: Path) -> None:
        """alfred / jarvis shape."""
        f = self._write(tmp_path, "$5: LIMITS\n\n$6: BEHAVIORAL LESSONS\n\n$7: DESCRIPTION\n\n")
        assert _lessons_section_for(f) == "$6"

    def test_five_lesson_layout(self, tmp_path: Path) -> None:
        """governor shape — lessons live in $5, not $6."""
        f = self._write(tmp_path, "$5: BEHAVIORAL LESSONS\n\n$6: DESCRIPTION\n\n")
        assert _lessons_section_for(f) == "$5"

    def test_expertise_in_six_is_not_hijacked(self, tmp_path: Path) -> None:
        """heimdall / seshat shape — $6 is EXPERTISE, so allocate a new id."""
        f = self._write(tmp_path, "$5: LIMITS\n\n$6: EXPERTISE\n\n$7: DESCRIPTION\n\n")
        assert _lessons_section_for(f) is None
        assert _ensure_lessons_section(f) == "$8"

    def test_created_section_is_titled_and_reused(self, tmp_path: Path) -> None:
        """A created section must carry the title, or every call allocates a new one."""
        f = self._write(tmp_path, "$5: LIMITS\n\n$6: EXPERTISE\n\n$7: DESCRIPTION\n\n")
        first = _ensure_lessons_section(f)
        second = _ensure_lessons_section(f)
        assert first == second == "$8"
        assert "BEHAVIORAL LESSONS" in f.read_text()

    def test_no_lessons_section_allocates_free_id(self, tmp_path: Path) -> None:
        """auditor / executor shape — no lessons section exists."""
        f = self._write(tmp_path, "$4: LIMITS\n\n$5: DESCRIPTION\n\n")
        assert _lessons_section_for(f) is None
        assert _ensure_lessons_section(f) == "$6"

    def test_identity_file_stays_clean_end_to_end(
        self, workspace_root: Path, ctx: PermissionContext
    ) -> None:
        """Even with an EXPERTISE section present, identity.record writes
        only to brain $8 — the identity file is never touched."""
        f = workspace_root / ".arqux" / "identities" / "test-agent.cortex"
        f.write_text(
            "$0\n\n# -- $0: GLOSSARY --\n\n$5: LIMITS\n\n$6: EXPERTISE\n\n$7: DESCRIPTION\n\n"
        )
        before = f.read_text()
        cortex_handlers.record_lesson_handler(
            lesson="Al escribir un artefacto...", kind="rule", cause="c",
            prevention="p", path=str(workspace_root), ctx=ctx,
        )
        assert f.read_text() == before
        brain = (workspace_root / ".arqux" / "brain.cortex").read_text()
        assert "LNG:" in brain.split("$8:")[1]
