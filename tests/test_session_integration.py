"""Full integration test for arqux.handlers.session — with meta-brain."""

from __future__ import annotations

from pathlib import Path

import pytest

META_BRAIN = """\
$0

# Sigil | Name | Type | Risk | Cognitive Layer | Description
# DOM   | dom   | attrs| M    | Semantic       | Project domain
# ARQX  | artifact|attrs| B   | Semantic       | Metadata

$0.1: ARQUX METADATA

ARQX:artifact{level:"3", name:"meta-brain", usage:"state", kind:"native"}

$2: PROJECTS

DOM:test-project{name:"test-project", path:".", domain:"test"}
"""

BRAIN = """\
$0

# Sigil | Name | Type | Risk | Cognitive Layer | Description
# AUD   | aud   | attrs| M    | Semantic       | Audit pulse
# FCS   | focus | attrs| H    | Working        | Focus
# OBJ   | objective|attrs| H  | Working        | Objectives
# KNW   | knw   | attrs| M    | Semantic       | Knowledge

$0.1: ARQUX METADATA

ARQX:artifact{level:"0", name:"brain", usage:"state", kind:"native"}

$2: FOCUS

FCS:current{what:"test", priority:"medium", status:"current"}

$3: OBJECTIVES

OBJ:_{goal:"test session", status:"current", success:"pending"}

$6: PULSE
"""


@pytest.fixture
def ws_root(tmp_path: Path) -> Path:
    """Full workspace: meta-brain + project brain + arqux dirs."""
    arqux = tmp_path / ".arqux"
    arqux.mkdir(exist_ok=True)
    (arqux / "meta-brain.cortex").write_text(META_BRAIN, encoding="utf-8")
    (arqux / "brain.cortex").write_text(BRAIN, encoding="utf-8")
    # Create project dir
    proj = tmp_path / "test-project"
    proj_arqux = proj / ".arqux"
    proj_arqux.mkdir(parents=True, exist_ok=True)
    (proj_arqux / "brain.cortex").write_text(BRAIN, encoding="utf-8")
    return tmp_path


@pytest.fixture
def ctx() -> object:
    from arqux.permissions import PermissionContext
    return PermissionContext(agent_id="jarvis", role="executor")


class TestSessionIntegration:
    """Test session handlers against a real workspace."""

    def test_session_close(self, ws_root, ctx) -> None:
        from arqux.handlers.session import close
        r = close(summary="test", blps="", tasks="", decisions="", gaps="", path=str(ws_root), ctx=ctx)
        assert "OUT-WORK" in r.to_text()

    def test_session_close_and_resume(self, ws_root, ctx) -> None:
        from arqux.handlers.session import close, resume
        close(summary="resume test", blps="", tasks="", decisions="", gaps="", path=str(ws_root), ctx=ctx)
        r = resume(path=str(ws_root), ctx=ctx)
        text = r.to_text()
        assert "OUT-WORK" in text
        assert "resume test" in text

    def test_session_status_after_close(self, ws_root, ctx) -> None:
        from arqux.handlers.session import close, status
        close(summary="status check", blps="BLP-X", tasks="T-001", decisions="", gaps="", path=str(ws_root), ctx=ctx)
        r = status(path=str(ws_root), ctx=ctx)
        text = r.to_text()
        assert "OUT-WORK" in text
        # status ses data should be present
        assert "status check" in text or "BLP-X" in text or "T-001" in text

    def test_context_set_and_get(self, ws_root, ctx) -> None:
        from arqux.handlers.session import context_get, context_set
        r_set = context_set(project="test-project", scope="BLP-005", blp="BLP-005", path=str(ws_root), ctx=ctx)
        assert "OUT-WORK" in r_set.to_text(), f"context_set failed: {r_set.to_text()}"
        r_get = context_get(path=str(ws_root))
        assert "OUT-WORK" in r_get.to_text(), f"context_get failed: {r_get.to_text()}"

    def test_context_get_without_project(self, ws_root, ctx) -> None:
        from arqux.handlers.session import context_get
        r = context_get(path=str(ws_root))
        text = r.to_text()
        # Should either return project info or error gracefully
        assert len(text) > 0


class TestSessionCloseErrors:
    """Edge cases for session.close."""

    def test_close_nonexistent_project(self, ctx) -> None:
        from arqux.handlers.session import close
        r = close(summary="x", blps="", tasks="", decisions="", gaps="", path="/nonexistent", ctx=ctx)
        assert "OUT-ERROR" in r.to_text()

    def test_close_large_payload(self, ws_root, ctx) -> None:
        from arqux.handlers.session import close
        big = "x" * 2500
        r = close(summary=big, blps="", tasks="", decisions="", gaps="", path=str(ws_root), ctx=ctx)
        assert "SES_TOO_LARGE" in r.to_text()
