"""Documented ergonomics gaps — 2.6 (no cross-corpus query) and 2.12 (codec
usability backlog: U4 emit helper, U7 conditional comments, U10 stdin check).

These are xfail tests ON PURPOSE: they assert the desired capability. When a
gap is closed the test starts failing as XPASS, which is the signal to flip it
into a hard requirement instead of letting a backlog item rot.

`strict=False` keeps an unimplemented gap from breaking CI while still
reporting it.
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="gap 2.6: selectors address one file, not the corpus", strict=False)
def test_cross_corpus_query_exists():
    from arqux.handlers import REGISTRY

    names = set(REGISTRY)
    assert any("corpus" in name for name in names), sorted(names)[:30]


@pytest.mark.xfail(reason="gap 2.12/U4: no public ideatic emit helper", strict=False)
def test_public_emit_helper_is_exported():
    from arqux.cortex import emit_ideatic  # noqa: F401


@pytest.mark.xfail(reason="gap 2.9: migration does not repair content", strict=False)
def test_migration_reports_content_repairs():
    from arqux.cortex import migration

    assert hasattr(migration, "plan_repairs")
