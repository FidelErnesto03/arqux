"""Ergonomics capabilities (gaps 2.6, 2.9, 2.12/U4) — required (BLP-006)."""

from __future__ import annotations


def test_cross_corpus_query_exists():
    from arqux.handlers import REGISTRY

    names = set(REGISTRY)
    assert any("corpus" in name for name in names), sorted(names)[:30]


def test_public_emit_helper_is_exported():
    from arqux.cortex import emit_ideatic  # noqa: F401

    assert callable(emit_ideatic)


def test_migration_reports_content_repairs():
    from arqux.cortex import migration

    assert hasattr(migration, "plan_repairs")
    plan = migration.plan_repairs(__file__)
    assert isinstance(plan, dict) and "repairs" in plan and "repair_count" in plan
