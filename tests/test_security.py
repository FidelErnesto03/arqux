"""Tests for arqux.security — HMAC identity, cortex integrity, secret store.

Covers:
    - generate_secret
    - sign_request / verify_request (happy path + tamper detection)
    - AgentIdentity.from_env
    - hash_cortex / inject_hash_header / verify_cortex
    - save_agent_secret / _load_agent_secret
"""

from __future__ import annotations

import os
import time

import pytest

# ---------------------------------------------------------------------------
# generate_secret
# ---------------------------------------------------------------------------


def test_generate_secret_length() -> None:
    """generate_secret returns a hex string of expected length."""
    from arqux.security import generate_secret

    s = generate_secret()
    # 32 bytes = 64 hex chars
    assert len(s) == 64
    int(s, 16)  # must be valid hex


def test_generate_secret_custom_bytes() -> None:
    """generate_secret respects num_bytes parameter."""
    from arqux.security import generate_secret

    s = generate_secret(num_bytes=16)
    assert len(s) == 32


# ---------------------------------------------------------------------------
# sign_request / verify_request — happy path
# ---------------------------------------------------------------------------


def test_sign_request_returns_hex() -> None:
    """sign_request returns a hex-encoded HMAC-SHA256 string."""
    from arqux.security import AgentIdentity, sign_request

    agent = AgentIdentity(agent_id="jarvis", secret="test-secret-key")
    sig = sign_request(agent, "identity.record", b'{"lesson":"test"}')
    assert isinstance(sig, str)
    assert len(sig) == 64
    int(sig, 16)


def test_verify_request_happy_path(monkeypatch) -> None:
    """verify_request returns True for a valid signature."""
    from arqux.security import AgentIdentity, sign_request, verify_request

    secret = "verify-secret-123"
    monkeypatch.setenv("ARQUX_AGENT_SECRET", secret)
    agent = AgentIdentity(agent_id="jarvis", secret=secret)
    ts = int(time.time())
    payload = b'{"lesson":"test"}'
    sig = sign_request(agent, "identity.record", payload, timestamp=ts)

    result = verify_request(
        agent_id="jarvis",
        handler="identity.record",
        payload=payload,
        signature=sig,
        timestamp=ts,
        secret_store=None,
    )
    assert result is True


def test_verify_request_with_string_payload(monkeypatch) -> None:
    """verify_request works with string payloads (auto-encoded to UTF-8)."""
    from arqux.security import AgentIdentity, sign_request, verify_request

    secret = "string-secret"
    monkeypatch.setenv("ARQUX_AGENT_SECRET", secret)
    agent = AgentIdentity(agent_id="jarvis", secret=secret)
    ts = int(time.time())
    sig = sign_request(agent, "handler.test", "string-payload", timestamp=ts)

    result = verify_request(
        agent_id="jarvis",
        handler="handler.test",
        payload="string-payload",
        signature=sig,
        timestamp=ts,
    )
    assert result is True


# ---------------------------------------------------------------------------
# sign_request / verify_request — tamper detection
# ---------------------------------------------------------------------------


def test_verify_tampered_payload(monkeypatch) -> None:
    """verify_request raises IdentityVerificationError when payload is tampered."""
    from arqux.security import (
        AgentIdentity,
        IdentityVerificationError,
        sign_request,
        verify_request,
    )

    secret = "tamper-secret"
    monkeypatch.setenv("ARQUX_AGENT_SECRET", secret)
    agent = AgentIdentity(agent_id="jarvis", secret=secret)
    ts = int(time.time())
    sig = sign_request(agent, "identity.record", b"original", timestamp=ts)

    with pytest.raises(IdentityVerificationError, match="HMAC signature mismatch"):
        verify_request(
            agent_id="jarvis",
            handler="identity.record",
            payload=b"tampered",
            signature=sig,
            timestamp=ts,
        )


def test_verify_tampered_handler(monkeypatch) -> None:
    """verify_request raises IdentityVerificationError when handler differs."""
    from arqux.security import (
        AgentIdentity,
        IdentityVerificationError,
        sign_request,
        verify_request,
    )

    secret = "handler-secret"
    monkeypatch.setenv("ARQUX_AGENT_SECRET", secret)
    agent = AgentIdentity(agent_id="jarvis", secret=secret)
    ts = int(time.time())
    sig = sign_request(agent, "identity.record", b"payload", timestamp=ts)

    with pytest.raises(IdentityVerificationError, match="HMAC signature mismatch"):
        verify_request(
            agent_id="jarvis",
            handler="other.handler",
            payload=b"payload",
            signature=sig,
            timestamp=ts,
        )


def test_verify_expired_timestamp() -> None:
    """verify_request raises IdentityVerificationError when timestamp exceeds skew."""
    from arqux.security import (
        AgentIdentity,
        IdentityVerificationError,
        sign_request,
        verify_request,
    )

    agent = AgentIdentity(agent_id="jarvis", secret="skew-secret")
    old_ts = int(time.time()) - 600  # 10 minutes ago > 300s max_skew
    sig = sign_request(agent, "identity.record", b"payload", timestamp=old_ts)

    with pytest.raises(IdentityVerificationError, match="timestamp skew"):
        verify_request(
            agent_id="jarvis",
            handler="identity.record",
            payload=b"payload",
            signature=sig,
            timestamp=old_ts,
        )


# ---------------------------------------------------------------------------
# AgentIdentity.from_env
# ---------------------------------------------------------------------------


def test_agent_identity_from_env_no_id() -> None:
    """AgentIdentity.from_env returns None when ARQUX_AGENT_ID is not set."""
    from arqux.security import AgentIdentity

    os.environ.pop("ARQUX_AGENT_ID", None)
    result = AgentIdentity.from_env()
    assert result is None


def test_agent_identity_from_env_with_id(monkeypatch) -> None:
    """AgentIdentity.from_env returns identity when env vars are set."""
    from arqux.security import AgentIdentity

    monkeypatch.setenv("ARQUX_AGENT_ID", "test-agent")
    monkeypatch.setenv("ARQUX_AGENT_SECRET", "test-secret-from-env")
    identity = AgentIdentity.from_env()
    assert identity is not None
    assert identity.agent_id == "test-agent"
    assert identity.secret == "test-secret-from-env"


def test_agent_identity_from_env_explicit_id(monkeypatch) -> None:
    """AgentIdentity.from_env accepts explicit agent_id parameter."""
    from arqux.security import AgentIdentity

    monkeypatch.setenv("ARQUX_AGENT_SECRET", "explicit-secret")
    identity = AgentIdentity.from_env(agent_id="explicit-agent")
    assert identity is not None
    assert identity.agent_id == "explicit-agent"


# ---------------------------------------------------------------------------
# hash_cortex / inject_hash_header / verify_cortex
# ---------------------------------------------------------------------------


def test_hash_cortex_deterministic() -> None:
    """hash_cortex returns the same SHA-256 hash for the same content."""
    from arqux.security import hash_cortex

    content = b"$0: test section\nbody here"
    h1 = hash_cortex(content)
    h2 = hash_cortex(content)
    assert h1 == h2
    assert len(h1) == 64


def test_hash_cortex_strips_integrity_header() -> None:
    """hash_cortex ignores existing $INTEGRITY headers when computing hash."""
    from arqux.security import hash_cortex, inject_hash_header

    content = b"$0: real content\nbody"
    expected_hash = hash_cortex(content)
    content_with_header = inject_hash_header(content, expected_hash)
    # Re-hashing should produce the same hash (header stripped)
    assert hash_cortex(content_with_header) == expected_hash


def test_inject_hash_header() -> None:
    """inject_hash_header prepends $INTEGRITY header."""
    from arqux.security import HASH_HEADER_PREFIX, inject_hash_header

    content = "$0: section\ndata"
    result = inject_hash_header(content)
    assert result.startswith(HASH_HEADER_PREFIX)
    assert "sha256:" in result.split("\n")[0]


def test_verify_cortex_ok(tmp_path) -> None:
    """verify_cortex returns True for a file with matching integrity hash."""
    from arqux.security import inject_hash_header, verify_cortex

    content = "$0: valid content\nbody"
    hashed = inject_hash_header(content)
    f = tmp_path / "valid.cortex"
    f.write_text(hashed, encoding="utf-8")
    assert verify_cortex(f) is True


def test_verify_cortex_tampered(tmp_path) -> None:
    """verify_cortex raises TamperError when file content is modified after hashing."""
    from arqux.security import TamperError, inject_hash_header, verify_cortex

    content = "$0: original\nbody"
    hashed = inject_hash_header(content)
    f = tmp_path / "tampered.cortex"
    f.write_text(hashed, encoding="utf-8")
    # Tamper: append extra content
    f.write_text(hashed + "\nTAMPERED", encoding="utf-8")
    with pytest.raises(TamperError):
        verify_cortex(f)


def test_verify_cortex_missing_header_strict(tmp_path) -> None:
    """verify_cortex raises TamperError in strict mode when header is missing."""
    from arqux.security import TamperError, verify_cortex

    f = tmp_path / "noheader.cortex"
    f.write_text("$0: content\nbody", encoding="utf-8")
    with pytest.raises(TamperError, match="missing"):
        verify_cortex(f, strict=True)


def test_verify_cortex_missing_header_legacy(tmp_path) -> None:
    """verify_cortex returns True in legacy mode (strict=False) without header."""
    from arqux.security import verify_cortex

    f = tmp_path / "legacy.cortex"
    f.write_text("$0: content\nbody", encoding="utf-8")
    assert verify_cortex(f, strict=False) is True


def test_verify_cortex_nonexistent() -> None:
    """verify_cortex raises FileNotFoundError for missing file."""
    from arqux.security import verify_cortex

    with pytest.raises(FileNotFoundError):
        verify_cortex("/nonexistent/path.cortex")


# ---------------------------------------------------------------------------
# save_agent_secret / _load_agent_secret
# ---------------------------------------------------------------------------


def test_save_agent_secret(tmp_path) -> None:
    """save_agent_secret creates a file with mode 0600."""
    from arqux.security import save_agent_secret

    secret_path = save_agent_secret(
        agent_id="test-agent",
        secret="my-secret-value",
        secret_store=tmp_path,
    )
    assert secret_path.exists()
    assert secret_path.read_text(encoding="utf-8").strip() == "my-secret-value"
    mode = secret_path.stat().st_mode & 0o777
    assert mode == 0o600


def test_save_then_load_agent_secret(tmp_path) -> None:
    """save_agent_secret followed by _load_agent_secret round-trips correctly."""
    from arqux.security import _load_agent_secret, save_agent_secret

    save_agent_secret(
        agent_id="round-trip",
        secret="round-trip-secret",
        secret_store=tmp_path,
    )
    loaded = _load_agent_secret(agent_id="round-trip", secret_store=tmp_path)
    assert loaded == "round-trip-secret"


def test_load_agent_secret_missing_file(tmp_path) -> None:
    """_load_agent_secret returns empty string when file does not exist."""
    from arqux.security import _load_agent_secret

    loaded = _load_agent_secret(agent_id="nonexistent", secret_store=tmp_path)
    assert loaded == ""


def test_load_agent_secret_no_agent_id(tmp_path) -> None:
    """_load_agent_secret returns empty string when agent_id is None and env unset."""
    from arqux.security import _load_agent_secret

    os.environ.pop("ARQUX_AGENT_ID", None)
    loaded = _load_agent_secret(agent_id=None, secret_store=tmp_path)
    assert loaded == ""


def test_agent_identity_from_env_strict_no_secret(monkeypatch) -> None:
    """AgentIdentity.from_env raises in strict mode when no secret is available."""
    from arqux.security import AgentIdentity, IdentityVerificationError

    monkeypatch.setenv("ARQUX_AGENT_ID", "strict-agent")
    monkeypatch.delenv("ARQUX_AGENT_SECRET", raising=False)
    monkeypatch.setattr("arqux.security.STRICT_MODE", True)
    with pytest.raises(IdentityVerificationError, match="no secret available"):
        AgentIdentity.from_env()


def test_save_agent_secret_walk_up(tmp_path) -> None:
    """save_agent_secret finds .arqux/ in parent and saves there."""
    from arqux.security import save_agent_secret

    # Create .arqux/secrets/ in parent
    parent = tmp_path / "parent"
    parent.mkdir()
    arqux_dir = parent / ".arqux" / "secrets"
    arqux_dir.mkdir(parents=True)

    # Save from child directory
    child = parent / "child"
    child.mkdir()

    secret_path = save_agent_secret(
        agent_id="walk-up-agent",
        secret="walk-up-secret",
        secret_store=arqux_dir,
    )
    assert secret_path.exists()
    assert secret_path.read_text(encoding="utf-8").strip() == "walk-up-secret"


def test_load_agent_secret_bad_permissions(tmp_path) -> None:
    """_load_agent_secret warns when file has open permissions."""
    from arqux.security import _load_agent_secret, save_agent_secret

    secret_path = save_agent_secret(
        agent_id="bad-perms",
        secret="bad-perms-secret",
        secret_store=tmp_path,
    )
    # Make file group-readable (bad permissions)
    secret_path.chmod(0o640)
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        loaded = _load_agent_secret(agent_id="bad-perms", secret_store=tmp_path)
        assert loaded == "bad-perms-secret"
        assert any("mode" in str(warning.message) for warning in w)


def test_extract_integrity_hash_no_header() -> None:
    """_extract_integrity_hash returns (None, original) when no header present."""
    from arqux.security import _extract_integrity_hash

    content = b"$0: regular content\nbody"
    stored_hash, stripped = _extract_integrity_hash(content)
    assert stored_hash is None
    assert stripped == content


def test_extract_integrity_hash_malformed() -> None:
    """_extract_integrity_hash returns (None, original) for malformed header."""
    from arqux.security import _extract_integrity_hash

    # Header with too few colons
    content = b"# $INTEGRITY: sha256\nrest of content"
    stored_hash, stripped = _extract_integrity_hash(content)
    assert stored_hash is None


def test_secure_write_cortex(tmp_path) -> None:
    """secure_write_cortex writes file with integrity hash."""
    from arqux.security import secure_write_cortex, verify_cortex

    f = tmp_path / "secure.cortex"
    result = secure_write_cortex(f, "$0: test\nbody")
    assert f.exists()
    assert result["signed"] is False
    assert result["hash"] != ""
    assert verify_cortex(f) is True


def test_secure_write_cortex_no_hash(tmp_path) -> None:
    """secure_write_cortex skips hash injection when inject_hash=False."""
    from arqux.security import secure_write_cortex

    f = tmp_path / "nohash.cortex"
    secure_write_cortex(f, "$0: test\nbody", inject_hash=False)
    content = f.read_text(encoding="utf-8")
    assert "$INTEGRITY" not in content


def test_secure_write_cortex_sign_requires_signer(tmp_path) -> None:
    """secure_write_cortex raises ValueError when sign_with set but no signer."""
    from arqux.security import generate_signing_keypair, secure_write_cortex

    priv, _ = generate_signing_keypair()
    f = tmp_path / "nosigner.cortex"
    with pytest.raises(ValueError, match="signer is required"):
        secure_write_cortex(f, "content", sign_with=priv)


def test_generate_signing_keypair() -> None:
    """generate_signing_keypair returns PEM private and public keys."""
    from arqux.security import generate_signing_keypair

    priv, pub = generate_signing_keypair()
    assert "BEGIN PRIVATE KEY" in priv or "BEGIN ENCRYPTED PRIVATE KEY" in priv
    assert "BEGIN PUBLIC KEY" in pub


def test_sign_cortex_and_verify() -> None:
    """sign_cortex produces content with $SIGNATURE and $SIGNER headers."""
    from arqux.security import _HAS_CRYPTOGRAPHY, generate_signing_keypair, sign_cortex

    if not _HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography package not installed")

    priv, pub = generate_signing_keypair()
    content = "$0: sign me\nbody"
    signed = sign_cortex(content, priv, "test-signer")
    assert "$SIGNATURE" in signed
    assert "$SIGNER" in signed
    assert "test-signer" in signed


def test_verify_cortex_signature_ok(tmp_path) -> None:
    """verify_cortex_signature returns True for a properly signed file."""
    from arqux.security import (
        _HAS_CRYPTOGRAPHY,
        generate_signing_keypair,
        sign_cortex,
        verify_cortex_signature,
    )

    if not _HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography package not installed")

    priv, pub = generate_signing_keypair()
    content = "$0: signed content\nbody"
    signed = sign_cortex(content, priv, "verify-agent")

    f = tmp_path / "signed.cortex"
    f.write_text(signed, encoding="utf-8")
    assert verify_cortex_signature(f, pub, expected_signer="verify-agent") is True


def test_verify_cortex_signature_wrong_signer(tmp_path) -> None:
    """verify_cortex_signature raises SignatureError when signer mismatches."""
    from arqux.security import (
        _HAS_CRYPTOGRAPHY,
        SignatureError,
        generate_signing_keypair,
        sign_cortex,
        verify_cortex_signature,
    )

    if not _HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography package not installed")

    priv, pub = generate_signing_keypair()
    signed = sign_cortex("content", priv, "actual-signer")
    f = tmp_path / "wrong.cortex"
    f.write_text(signed, encoding="utf-8")

    with pytest.raises(SignatureError, match="signer mismatch"):
        verify_cortex_signature(f, pub, expected_signer="expected-signer")


def test_verify_cortex_signature_no_header(tmp_path) -> None:
    """verify_cortex_signature raises SignatureError when headers are missing."""
    from arqux.security import (
        _HAS_CRYPTOGRAPHY,
        SignatureError,
        generate_signing_keypair,
        verify_cortex_signature,
    )

    if not _HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography package not installed")

    _, pub = generate_signing_keypair()
    f = tmp_path / "unsigned.cortex"
    f.write_text("$0: no signature\nbody", encoding="utf-8")

    with pytest.raises(SignatureError, match="no \\$SIGNATURE header"):
        verify_cortex_signature(f, pub)


def test_verify_cortex_signature_too_short(tmp_path) -> None:
    """verify_cortex_signature raises SignatureError for file too short."""
    from arqux.security import (
        _HAS_CRYPTOGRAPHY,
        SignatureError,
        generate_signing_keypair,
        verify_cortex_signature,
    )

    if not _HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography package not installed")

    _, pub = generate_signing_keypair()
    f = tmp_path / "short.cortex"
    f.write_text("x", encoding="utf-8")

    with pytest.raises(SignatureError, match="too short"):
        verify_cortex_signature(f, pub)


def test_secure_write_cortex_signed(tmp_path) -> None:
    """secure_write_cortex with sign_with produces signed + hashed file."""
    from arqux.security import (
        _HAS_CRYPTOGRAPHY,
        generate_signing_keypair,
        secure_write_cortex,
        verify_cortex,
    )

    if not _HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography package not installed")

    priv, _ = generate_signing_keypair()
    f = tmp_path / "signed_write.cortex"
    result = secure_write_cortex(f, "$0: sign this\nbody", sign_with=priv, signer="signer-id")
    assert result["signed"] is True
    assert result["signer"] == "signer-id"
    assert verify_cortex(f) is True
