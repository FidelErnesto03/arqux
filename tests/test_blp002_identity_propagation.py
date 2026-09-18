"""Regression tests for BLP-002 identity propagation and attribution."""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.cortex.learning import record_lesson_handler
from arqux.handlers.session import bootstrap
from arqux.permissions import PermissionContext


def _workspace(tmp_path: Path, agent: str = "jarvis") -> Path:
    arqux = tmp_path / ".arqux"
    (arqux / "identities").mkdir(parents=True)
    (arqux / "brain.cortex").write_text("$0\n$6: PULSE\n", encoding="utf-8")
    (arqux / "identities" / f"{agent}.cortex").write_text(
        f"$0\n$1: IDENTITY\nIDN:{agent}{{name:\"{agent}\"}}\n",
        encoding="utf-8",
    )
    return tmp_path


def test_bootstrap_rejects_presentation_identity_mismatch(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    ctx = PermissionContext(agent_id="alfred", role="governor")

    result = bootstrap(path=str(root), agent_id="jarvis", ctx=ctx)

    assert result.profile == "OUT-ERROR"
    assert result.fields["code"] == "IDENTITY_MISMATCH"


def test_bootstrap_uses_authenticated_identity_case_insensitively(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    ctx = PermissionContext(agent_id="jarvis", role="executor")

    result = bootstrap(path=str(root), agent_id="JARVIS", ctx=ctx)

    assert result.profile == "OUT-WORK"
    assert result.fields["agent_id"] == "jarvis"
    assert "IDN:jarvis" in result.fields["cortex_context"]["identity"]


def test_identity_record_rejects_cross_agent_attribution(tmp_path: Path) -> None:
    root = _workspace(tmp_path, agent="alfred")
    ctx = PermissionContext(agent_id="Alfred", role="governor")

    result = record_lesson_handler(
        lesson="identity attribution must be canonical",
        kind="process",
        cause="BLP-002",
        prevention="Use the authenticated identity as the only target.",
        agent_id="jarvis",
        path=str(root),
        ctx=ctx,
    )

    assert result.profile == "OUT-ERROR"
    assert result.fields["code"] == "IDENTITY_MISMATCH"


def test_identity_record_resolves_case_insensitive_filename(tmp_path: Path) -> None:
    root = _workspace(tmp_path, agent="alfred")
    ctx = PermissionContext(agent_id="Alfred", role="governor")

    result = record_lesson_handler(
        lesson="identity filename lookup is canonical",
        kind="process",
        cause="BLP-002",
        prevention="Casefold agent IDs before resolving identity files.",
        agent_id="ALFRED",
        path=str(root),
        ctx=ctx,
    )

    assert result.profile == "OUT-WORK"
    assert result.fields["agent"] == "alfred"
