"""Tests for the `protocol` module."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

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


def test_register_agent_writes_canonical_metadata(tmp_path: Path) -> None:
    """agents.cortex carries $19 ARQX:artifact + arqx_contract declaration.

    The auto-generated glossary declaration must be named ``arqx_contract``
    (canon) — never ``ARQX:artifact``, which would collide with the metadata
    entry's own address.
    """
    from arqux.handlers.protocol import _register_agent

    agents = tmp_path / "agents.cortex"
    _register_agent(agents, "jarvis", "executor")
    _register_agent(agents, "heimdall", "auditor")
    content = agents.read_text(encoding="utf-8")
    assert "$19: ARQUX METADATA" in content
    assert "ARQX:arqx_contract{" in content
    # The only ARQX:artifact is the metadata entry in $19 — no glossary
    # declaration minted under the colliding ``artifact`` name.
    assert content.count("ARQX:artifact{") == 1


def test_register_agent_coalesces_legacy_01_metadata(tmp_path: Path) -> None:
    """A pre-existing ``$0.1`` metadata section must not duplicate.

    The writer merges ``$0.1`` into ``$19`` at emit time; the upsert must
    coalesce in the model first or the emitted doc carries two
    ``$19:ARQX:artifact`` addresses (I006_DUPLICATE_IDEA_ADDRESS).
    """
    pytest.importorskip("codec_cortex.dispatcher")
    from arqux.cortex.model import parse_native
    from arqux.handlers.protocol import _register_agent

    agents = tmp_path / "agents.cortex"
    agents.write_text(
        "$0\n\n$0.1: ARQUX METADATA\n\n"
        'ARQX:artifact{level:0, name:"agents", usage:"state", kind:"native"}\n\n'
        "$1: AGENTS\n\nIDN:old{role:\"x\"}\n",
        encoding="utf-8",
    )
    _register_agent(agents, "jarvis", "executor")
    content = agents.read_text(encoding="utf-8")
    assert content.count("ARQX:artifact{") == 1
    parse_native(content)  # must not raise (strict v1 grammar)
