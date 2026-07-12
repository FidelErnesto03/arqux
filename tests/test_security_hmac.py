"""Tests for arqux.security — HMAC agent identity (focused suite).

Covers edge cases not in test_security.py:
    - Empty / unicode / large payloads
    - Multi-agent scenarios
    - Explicit secret_store parameter in verify_request
    - Full lifecycle: create → save → verify
    - AgentIdentity repr / equality
"""

from __future__ import annotations

import os
import time

import pytest

# ---------------------------------------------------------------------------
# sign_request — edge cases
# ---------------------------------------------------------------------------


def test_sign_request_empty_payload() -> None:
    """sign_request works with empty bytes payload."""
    from arqux.security import AgentIdentity, sign_request

    agent = AgentIdentity(agent_id="jarvis", secret="s3kr3t")
    sig = sign_request(agent, "handler.empty", b"")
    assert isinstance(sig, str)
    assert len(sig) == 64


def test_sign_request_empty_string_payload() -> None:
    """sign_request works with empty string payload."""
    from arqux.security import AgentIdentity, sign_request

    agent = AgentIdentity(agent_id="jarvis", secret="s3kr3t")
    sig = sign_request(agent, "handler.empty", "")
    assert isinstance(sig, str)
    assert len(sig) == 64


def test_sign_request_unicode_payload() -> None:
    """sign_request handles unicode payloads correctly."""
    from arqux.security import AgentIdentity, sign_request

    agent = AgentIdentity(agent_id="jarvis", secret="s3kr3t")
    sig = sign_request(agent, "handler.unicode", "ñóś öñë üñí¢ödê 🔐")
    assert isinstance(sig, str)
    assert len(sig) == 64


def test_sign_request_json_payload() -> None:
    """sign_request handles JSON-like string payloads."""
    from arqux.security import AgentIdentity, sign_request

    agent = AgentIdentity(agent_id="jarvis", secret="s3kr3t")
    payload = '{"agent": "jarvis", "handler": "identity.record", "ts": 1234567890}'
    sig = sign_request(agent, "handler.json", payload)
    assert isinstance(sig, str)
    assert len(sig) == 64


def test_sign_request_large_payload() -> None:
    """sign_request handles a 1MB payload without issues."""
    from arqux.security import AgentIdentity, sign_request

    agent = AgentIdentity(agent_id="jarvis", secret="s3kr3t")
    payload = b"x" * (1024 * 1024)
    sig = sign_request(agent, "handler.large", payload)
    assert isinstance(sig, str)
    assert len(sig) == 64


# ---------------------------------------------------------------------------
# verify_request — edge cases
# ---------------------------------------------------------------------------


def test_verify_request_explicit_secret_store(tmp_path, monkeypatch) -> None:
    """verify_request loads secret from explicit secret_store path."""
    from arqux.security import (
        AgentIdentity,
        save_agent_secret,
        sign_request,
        verify_request,
    )

    secret = "store-secret"
    save_agent_secret(agent_id="store-agent", secret=secret, secret_store=tmp_path)
    agent = AgentIdentity(agent_id="store-agent", secret=secret)
    ts = int(time.time())
    sig = sign_request(agent, "handler.test", b"payload", timestamp=ts)

    result = verify_request(
        agent_id="store-agent",
        handler="handler.test",
        payload=b"payload",
        signature=sig,
        timestamp=ts,
        secret_store=tmp_path,
    )
    assert result is True


def test_verify_request_env_fallback(monkeypatch) -> None:
    """verify_request falls back to ARQUX_AGENT_SECRET when no store."""
    from arqux.security import AgentIdentity, sign_request, verify_request

    secret = "env-fallback"
    monkeypatch.setenv("ARQUX_AGENT_SECRET", secret)
    agent = AgentIdentity(agent_id="env-agent", secret=secret)
    ts = int(time.time())
    sig = sign_request(agent, "handler.env", b"payload", timestamp=ts)

    result = verify_request(
        agent_id="env-agent",
        handler="handler.env",
        payload=b"payload",
        signature=sig,
        timestamp=ts,
    )
    assert result is True


def test_verify_request_no_secret_raises() -> None:
    """verify_request raises when no secret is available at all."""
    from arqux.security import IdentityVerificationError, verify_request

    # Ensure no env secret
    os.environ.pop("ARQUX_AGENT_SECRET", None)

    with pytest.raises(IdentityVerificationError, match="no secret available"):
        verify_request(
            agent_id="no-secret-agent",
            handler="handler.test",
            payload=b"payload",
            signature="x" * 64,
            timestamp=int(time.time()),
        )


# ---------------------------------------------------------------------------
# Multi-agent scenarios
# ---------------------------------------------------------------------------


def test_two_agents_sign_and_verify(tmp_path) -> None:
    """Two different agents sign requests independently — each verifies."""
    from arqux.security import (
        AgentIdentity,
        save_agent_secret,
        sign_request,
        verify_request,
    )

    save_agent_secret("alice", "alice-secret", secret_store=tmp_path)
    save_agent_secret("bob", "bob-secret", secret_store=tmp_path)

    ts = int(time.time())

    for agent_id, secret_str in [("alice", "alice-secret"), ("bob", "bob-secret")]:
        agent = AgentIdentity(agent_id=agent_id, secret=secret_str)
        sig = sign_request(agent, f"handler.{agent_id}", b"payload", timestamp=ts)
        assert verify_request(
            agent_id=agent_id,
            handler=f"handler.{agent_id}",
            payload=b"payload",
            signature=sig,
            timestamp=ts,
            secret_store=tmp_path,
        ) is True


def test_two_agents_cross_verify_fails(tmp_path) -> None:
    """bob's signature should not verify for alice's identity."""
    from arqux.security import (
        AgentIdentity,
        IdentityVerificationError,
        save_agent_secret,
        sign_request,
        verify_request,
    )

    save_agent_secret("alice", "alice-secret", secret_store=tmp_path)
    save_agent_secret("bob", "bob-secret", secret_store=tmp_path)

    ts = int(time.time())
    bob = AgentIdentity(agent_id="bob", secret="bob-secret")
    bob_sig = sign_request(bob, "handler.shared", b"payload", timestamp=ts)

    with pytest.raises(IdentityVerificationError, match="HMAC signature mismatch"):
        verify_request(
            agent_id="alice",
            handler="handler.shared",
            payload=b"payload",
            signature=bob_sig,
            timestamp=ts,
            secret_store=tmp_path,
        )


# ---------------------------------------------------------------------------
# AgentIdentity
# ---------------------------------------------------------------------------


def test_agent_identity_repr() -> None:
    """AgentIdentity repr includes agent_id."""
    from arqux.security import AgentIdentity

    agent = AgentIdentity(agent_id="test-agent", secret="hunter2")
    rep = repr(agent)
    assert "test-agent" in rep


def test_agent_identity_equality() -> None:
    """Two identities with same agent_id and secret are equal."""
    from arqux.security import AgentIdentity

    a = AgentIdentity(agent_id="jarvis", secret="x" * 64)
    b = AgentIdentity(agent_id="jarvis", secret="x" * 64)
    assert a == b


def test_agent_identity_inequality() -> None:
    """Two identities with different secrets are not equal."""
    from arqux.security import AgentIdentity

    a = AgentIdentity(agent_id="jarvis", secret="a" * 64)
    b = AgentIdentity(agent_id="jarvis", secret="b" * 64)
    assert a != b


# ---------------------------------------------------------------------------
# AgentIdentity.from_env edge cases
# ---------------------------------------------------------------------------


def test_agent_identity_from_env_empty_secret_strict(monkeypatch) -> None:
    """from_env raises in strict mode with empty secret and no store."""
    from arqux.security import AgentIdentity, IdentityVerificationError

    monkeypatch.setenv("ARQUX_AGENT_ID", "strict-agent")
    monkeypatch.setenv("ARQUX_AGENT_SECRET", "")
    monkeypatch.setattr("arqux.security.STRICT_MODE", True)
    with pytest.raises(IdentityVerificationError, match="no secret available"):
        AgentIdentity.from_env()


# ---------------------------------------------------------------------------
# Constant-time comparison guarantee
# ---------------------------------------------------------------------------


def test_hmac_compare_digest_used() -> None:
    """verify_request uses hmac.compare_digest for constant-time comparison."""
    import inspect

    from arqux.security import verify_request

    source = inspect.getsource(verify_request)
    assert "hmac.compare_digest" in source
