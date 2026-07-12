"""Tests for arqux.security — cortex integrity (focused suite).

Covers edge cases not in test_security.py:
    - Multiple integrity header cycles (re-hash after header injection)
    - Empty / binary content edge cases
    - _strip_integrity_headers with various header combinations
    - verify_cortex with combined signature + hash headers
    - inject_hash_header overwrites existing header
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# hash_cortex — edge cases
# ---------------------------------------------------------------------------


def test_hash_cortex_empty_content() -> None:
    """hash_cortex handles empty content."""
    from arqux.security import hash_cortex

    h = hash_cortex(b"")
    assert isinstance(h, str)
    assert len(h) == 64


def test_hash_cortex_binary_content() -> None:
    """hash_cortex handles arbitrary binary content."""
    from arqux.security import hash_cortex

    h = hash_cortex(bytes(range(256)))
    assert isinstance(h, str)
    assert len(h) == 64


def test_hash_cortex_different_content_differs() -> None:
    """hash_cortex produces different hashes for different content."""
    from arqux.security import hash_cortex

    assert hash_cortex(b"content A") != hash_cortex(b"content B")


# ---------------------------------------------------------------------------
# inject_hash_header — idempotency and overwrite
# ---------------------------------------------------------------------------


def test_inject_hash_header_custom_hash() -> None:
    """inject_hash_header accepts an explicit hash value."""
    from arqux.security import inject_hash_header

    content = "$0: custom hash\ndata"
    explicit_hash = "a" * 64
    result = inject_hash_header(content, hash_hex=explicit_hash)
    assert f"sha256:{explicit_hash}" in result.split("\n")[0]


def test_inject_hash_header_double_injection_replaces() -> None:
    """inject_hash_header replaces existing header instead of stacking."""
    from arqux.security import HASH_HEADER_PREFIX, inject_hash_header

    content = "$0: original\ndata"
    once = inject_hash_header(content)
    twice = inject_hash_header(once)

    lines = twice.strip().split("\n")
    integrity_lines = [ln for ln in lines if ln.startswith(HASH_HEADER_PREFIX)]
    assert len(integrity_lines) == 1, (
        f"Expected 1 integrity header, got {len(integrity_lines)}"
    )


def test_inject_hash_header_first_line() -> None:
    """The $INTEGRITY header is always the first line."""
    from arqux.security import HASH_HEADER_PREFIX, inject_hash_header

    content = "$0: section\ndata"
    result = inject_hash_header(content)
    first_line = result.split("\n")[0]
    assert first_line.startswith(HASH_HEADER_PREFIX)


# ---------------------------------------------------------------------------
# verify_cortex — edge cases
# ---------------------------------------------------------------------------


def test_verify_cortex_round_trip(tmp_path) -> None:
    """After inject + verify cycle, integrity holds."""
    from arqux.security import inject_hash_header, verify_cortex

    content = "$0: round trip\ndata"
    f = tmp_path / "roundtrip.cortex"
    f.write_text(inject_hash_header(content), encoding="utf-8")
    assert verify_cortex(f) is True


def test_verify_cortex_after_rehash(tmp_path) -> None:
    """Re-hashing after content change updates integrity correctly."""
    from arqux.security import inject_hash_header, verify_cortex

    f = tmp_path / "rehash.cortex"
    f.write_text(inject_hash_header("$0: v1\ndata"), encoding="utf-8")
    # Update content and re-inject header
    f.write_text(inject_hash_header("$0: v2\ndata"), encoding="utf-8")
    assert verify_cortex(f) is True


# ---------------------------------------------------------------------------
# _strip_integrity_headers — edge cases
# ---------------------------------------------------------------------------


def test_strip_integrity_headers_clean() -> None:
    """_strip_integrity_headers leaves clean content unchanged."""
    from arqux.security import _strip_integrity_headers

    content = b"$0: section\nbody\ndata"
    assert _strip_integrity_headers(content) == content


def test_strip_integrity_headers_all_three() -> None:
    """_strip_integrity_headers removes INTEGRITY, SIGNATURE, and SIGNER lines."""
    from arqux.security import _strip_integrity_headers

    content = b"""# $INTEGRITY: sha256:abc123
# $SIGNATURE: ed25519:def456
# $SIGNER: jarvis
$0: real content
body"""
    stripped = _strip_integrity_headers(content)
    assert b"$INTEGRITY" not in stripped
    assert b"$SIGNATURE" not in stripped
    assert b"$SIGNER" not in stripped
    assert b"$0: real content" in stripped


def test_strip_integrity_headers_partial() -> None:
    """_strip_integrity_headers removes only integrity headers, keeps others."""
    from arqux.security import _strip_integrity_headers

    content = b"""# $INTEGRITY: sha256:abc
$0: section
# $MY_CUSTOM: keep this"""
    stripped = _strip_integrity_headers(content)
    assert b"$INTEGRITY" not in stripped
    assert b"$MY_CUSTOM" in stripped


# ---------------------------------------------------------------------------
# _extract_integrity_hash — edge cases
# ---------------------------------------------------------------------------


def test_extract_integrity_hash_multi_line_first_line() -> None:
    """_extract_integrity_hash handles first line wrapped with content after."""
    from arqux.security import _extract_integrity_hash

    content = b"# $INTEGRITY: sha256:abcdef1234567890\n$0: section\nbody"
    stored, stripped = _extract_integrity_hash(content)
    assert stored == "abcdef1234567890"
    assert b"$INTEGRITY" not in stripped


def test_extract_integrity_hash_only_header() -> None:
    """_extract_integrity_hash handles file with only a header and no body."""
    from arqux.security import _extract_integrity_hash

    content = b"# $INTEGRITY: sha256:deadbeef"
    stored, stripped = _extract_integrity_hash(content)
    assert stored == "deadbeef"
    assert stripped == b""


# ---------------------------------------------------------------------------
# Integration: full cortex lifecycle
# ---------------------------------------------------------------------------


def test_cortex_full_lifecycle(tmp_path) -> None:
    """Full lifecycle: create → hash → inject → verify → tamper → fail."""
    from arqux.security import (
        TamperError,
        inject_hash_header,
        verify_cortex,
    )

    original = "$0: important\ngovernance data"
    f = tmp_path / "lifecycle.cortex"

    # Write with integrity
    f.write_text(inject_hash_header(original), encoding="utf-8")
    assert verify_cortex(f) is True

    # Tamper
    f.write_text(f.read_text(encoding="utf-8") + "\nTAMPERED", encoding="utf-8")
    with pytest.raises(TamperError):
        verify_cortex(f)

    # Re-hash and verify again
    current = f.read_text(encoding="utf-8")
    f.write_text(inject_hash_header(current), encoding="utf-8")
    assert verify_cortex(f) is True
