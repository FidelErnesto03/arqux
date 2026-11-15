"""Tests for the `protocol` module."""

from __future__ import annotations

import os
from pathlib import Path

from arqux.constants import PRODUCT_NAME_UPPER
from arqux.handlers import protocol, workspace


def test_protocol_adopt_sets_env_vars(workspace_root: Path, governor_ctx) -> None:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    result = protocol.adopt(agent_id="new-agent", role="executor", path=str(workspace_root))
    assert os.environ.get(f"{PRODUCT_NAME_UPPER}_AGENT_ID") == "new-agent"
    assert os.environ.get(f"{PRODUCT_NAME_UPPER}_AGENT_ROLE") == "executor"
    assert "protocol.adopt ok" in result.to_text()


def test_protocol_release_clears_env_vars(workspace_root: Path, governor_ctx) -> None:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    protocol.adopt(agent_id="tmp", role="executor", path=str(workspace_root))
    protocol.release(agent_id="tmp", path=str(workspace_root))
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


def _meta_brain(tmp_path: Path) -> Path:
    """Minimal canonical meta-brain with a REGISTRY section."""
    meta = tmp_path / "meta-brain.cortex"
    meta.write_text(
        "$0\n\n$0:format{cortex:1.0, encoding:UTF-8}\n\n"
        "IDN:idn_contract{type:\"attrs\", weight:\"B\", focus:\"value\", "
        "fields:\"value:any?\", desc:\"id\", open:true}\n\n"
        "$1: IDENTITY\n\n"
        'ARQX:artifact{level:3, name:"meta-brain", usage:"brain", '
        'kind:"native", version:"0"}\n\n'
        "$10: REGISTRY\n",
        encoding="utf-8",
    )
    return meta


def test_register_agent_writes_to_meta_brain_registry(tmp_path: Path) -> None:
    """Agent registration lands in meta-brain $10 REGISTRY — never in a
    resurrected agents.cortex file."""
    from arqux.handlers.protocol import _register_agent

    meta = _meta_brain(tmp_path)
    _register_agent(meta, "jarvis", "executor")
    _register_agent(meta, "heimdall", "auditor")
    content = meta.read_text(encoding="utf-8")
    assert 'IDN:jarvis{' in content and 'role:"executor"' in content
    assert 'IDN:heimdall{' in content and 'role:"auditor"' in content
    registry = content.split("$10: REGISTRY", 1)[1]
    assert "IDN:jarvis" in registry
    assert not (tmp_path / "agents.cortex").exists()


def test_register_agent_is_idempotent(tmp_path: Path) -> None:
    """Re-adopting the same agent updates role, never duplicates."""
    from arqux.handlers.protocol import _register_agent

    meta = _meta_brain(tmp_path)
    _register_agent(meta, "jarvis", "executor")
    _register_agent(meta, "jarvis", "governor")
    content = meta.read_text(encoding="utf-8")
    assert content.count("IDN:jarvis") == 1
    assert 'role:"governor"' in content


def test_unregister_agent_removes_registry_entry(tmp_path: Path) -> None:
    """Release deletes the IDN entry; a second release is a no-op."""
    from arqux.handlers.protocol import _register_agent, _unregister_agent

    meta = _meta_brain(tmp_path)
    _register_agent(meta, "jarvis", "executor")
    _unregister_agent(meta, "jarvis")
    assert "IDN:jarvis" not in meta.read_text(encoding="utf-8")
    _unregister_agent(meta, "jarvis")  # idempotent
