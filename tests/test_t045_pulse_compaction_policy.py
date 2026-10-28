"""CYCLE-12 / BLP-027 — la compactación del PULSE es una decisión, no un efecto.

El cierre de SES015 (2026-10-28) convirtió cinco checkpoints —cada uno con su
``fcs``, ``obj`` y ``tasks``— en ``summary: "checkpoint:5"`` sin que nadie lo
pidiera. El cierre ya no compacta: informa cuántos eventos deja y cómo
consolidarlos. La compactación explícita sigue viva y sigue siendo segura.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.execution import mint_execution_key
from arqux.handlers.session import close
from arqux.permissions import PermissionContext
from arqux.pulse import compact_session_pulse, record_pulse
from arqux.session_identity import open_session
from arqux.state import crud_read


@pytest.fixture
def session(arqux_env):
    env = arqux_env
    env.key = mint_execution_key()
    env.session = open_session(env.proj_root, agent="test-governor", project="test-proj",
                               execution=env.key)
    env.sid = env.session["session_id"]
    env.ctx = PermissionContext(agent_id="test-governor", role="governor",
                                execution_key=env.key)
    return env


def _brain(env) -> Path:
    return env.proj_root / ".arqux" / "brain.cortex"


def _seed_pulses(env, count=6):
    for i in range(count):
        record_pulse(env.proj_root, task_id="-", kind="checkpoint",
                     agent="test-governor", payload=f"turno {i}", ses_ref=env.sid)


def _close(env, summary="cierre de prueba"):
    return close(summary=summary, session_ref=env.sid,
                 path=str(env.proj_root), ctx=env.ctx)


class TestCloseDoesNotCompact:
    def test_close_leaves_the_trail_untouched(self, session):
        _seed_pulses(session)
        out = _close(session)

        assert out.profile == "OUT-WORK", out
        assert out.fields["pulse_events"] >= 6
        assert "compact" not in out.fields

        consolidated = crud_read(_brain(session), f"$7/LNG:session_{session.sid}")
        assert consolidated["entries"] == []

    def test_close_tells_how_to_consolidate(self, session):
        _seed_pulses(session)
        out = _close(session)

        hint = out.fields["hint"]
        assert "session.pulse.compact" in hint
        assert session.sid in hint
        assert out.fields["event_id"] in hint

    def test_close_without_events_reports_zero(self, session):
        out = _close(session)
        assert out.fields["pulse_events"] == 0
        assert "hint" not in out.fields


class TestExplicitCompactionStillWorks:
    def test_compaction_consolidates_and_is_idempotent(self, session):
        _seed_pulses(session)
        out = _close(session)
        event_id = out.fields["event_id"]

        first = compact_session_pulse(session.proj_root, session_id=event_id,
                                      agent_id="test-governor", ses_ref=session.sid)
        assert first["compacted"] is True
        assert first["pruned"] >= 6

        consolidated = crud_read(_brain(session), f"$7/LNG:session_{session.sid}")
        assert consolidated["entries"], "la compactación explícita debe dejar la LNG"

        second = compact_session_pulse(session.proj_root, session_id=event_id,
                                       agent_id="test-governor", ses_ref=session.sid)
        assert second.get("skip") is True


class TestCompactorUsesTheAtomicWriter:
    def test_no_write_text_on_the_brain(self, session, monkeypatch):
        _seed_pulses(session)
        out = _close(session)
        event_id = out.fields["event_id"]

        brain = _brain(session)
        # Brain without the LNG declaration: the branch that used to rewrite the
        # file with write_text.
        text = brain.read_text(encoding="utf-8")
        stripped = "\n".join(line for line in text.splitlines()
                             if not line.startswith("# LNG |"))
        assert stripped != text
        brain.write_text(stripped, encoding="utf-8")

        original = Path.write_text

        def guard(self, *args, **kwargs):
            if self.name == "brain.cortex":
                raise AssertionError("el compactador escribió el brain con write_text")
            return original(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", guard)
        result = compact_session_pulse(session.proj_root, session_id=event_id,
                                       agent_id="test-governor", ses_ref=session.sid)
        monkeypatch.undo()

        assert result["compacted"] is True
        assert crud_read(brain, f"$7/LNG:session_{session.sid}")["entries"]
