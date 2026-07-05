"""Tests for the `protocol` module."""

from __future__ import annotations

import os
from pathlib import Path

from arqux.constants import PRODUCT_NAME_UPPER
from arqux.handlers import protocol, workspace


def test_protocol_adopt_sets_env_vars(workspace_root: Path, governor_ctx) -> None:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    result = protocol.adopt(agent_id="new-agent", role="executor")
    assert os.environ.get(f"{PRODUCT_NAME_UPPER}_AGENT_ID") == "new-agent"
    assert os.environ.get(f"{PRODUCT_NAME_UPPER}_AGENT_ROLE") == "executor"
    assert "protocol.adopt ok" in result.to_text()


def test_protocol_release_clears_env_vars(workspace_root: Path, governor_ctx) -> None:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    protocol.adopt(agent_id="tmp", role="executor")
    protocol.release(agent_id="tmp")
    assert os.environ.get(f"{PRODUCT_NAME_UPPER}_AGENT_ID") is None
    assert os.environ.get(f"{PRODUCT_NAME_UPPER}_AGENT_ROLE") is None


def test_protocol_pause_sets_suspended_flag() -> None:
    result = protocol.pause()
    assert protocol.is_suspended() is True
    assert "suspended=true" in result.to_text()
    protocol.resume()  # cleanup


def test_protocol_resume_clears_suspended_flag() -> None:
    protocol.pause()
    result = protocol.resume()
    assert protocol.is_suspended() is False
    assert "suspended=false" in result.to_text()


def test_protocol_adopt_rejects_invalid_role() -> None:
    result = protocol.adopt(agent_id="x", role="superuser")
    assert "INVALID_ARGUMENT" in result.to_text()
