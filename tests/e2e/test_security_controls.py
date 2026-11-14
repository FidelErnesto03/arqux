"""Security-controls suite — lesson `dos_controles_de_seguridad_distintos`
(BLP-005 CYCLE-13: an allow-list without root confinement let a declared
action write anywhere and destroy the repo README).

The two controls are independent and BOTH are mandatory:

- what may run  → ``ALLOWED_ACTIONS`` (deny by default)
- where it may write → ``_resolve_within`` (root confinement)

An undeclared action must never fall back to a simulated success.
"""

from __future__ import annotations

import pytest

from arqux.handlers.execution import (
    ExecutionError,
    declared_actions,
    execute_action,
)


def test_undeclared_action_is_denied(tmp_path, governor_ctx):
    with pytest.raises(ExecutionError) as excinfo:
        execute_action("rm_rf_everything", {"path": "x"}, ctx=governor_ctx,
                       root=tmp_path)
    assert excinfo.value.code == "not_declared"
    assert "write_file" in str(excinfo.value), "error must list allowed actions"


def test_declared_action_outside_root_is_denied(tmp_path, governor_ctx):
    """The confinement control is independent from the allow-list."""
    escape = tmp_path.parent / "escape-proof.txt"
    with pytest.raises(ExecutionError) as excinfo:
        execute_action(
            "write_file",
            {"path": str(escape), "content": "escaped"},
            ctx=governor_ctx,
            root=tmp_path,
        )
    assert excinfo.value.code == "outside_root"
    assert not escape.exists()


def test_declared_action_inside_root_succeeds(tmp_path, governor_ctx):
    target = tmp_path / "inside.txt"
    result = execute_action(
        "write_file",
        {"path": str(target), "content": "ok"},
        ctx=governor_ctx,
        root=tmp_path,
    )
    assert result.ok is True
    assert target.read_text(encoding="utf-8") == "ok"
    assert result.artifact_sha256


def test_forbidden_role_cannot_execute(tmp_path, auditor_ctx):
    with pytest.raises(ExecutionError) as excinfo:
        execute_action(
            "write_file",
            {"path": str(tmp_path / "x.txt"), "content": "no"},
            ctx=auditor_ctx,
            root=tmp_path,
        )
    assert excinfo.value.code == "forbidden_role"


def test_allow_list_is_small_and_explicit():
    actions = declared_actions()
    assert "write_file" in actions
    assert "rm_rf_everything" not in actions
