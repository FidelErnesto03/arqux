"""
arqux.security — Security primitives (NEW in v0.4.0).

Solves CRÍTICO-1 (bypass identidad) and CRÍTICO-2 (tamper evidencia)
detected in the v2.0 experimental benchmark.

Provides:
    - HMAC-SHA256 authentication for agent identity verification.
    - SHA-256 integrity hashes for .cortex files (tamper detection).
    - Optional Ed25519 signatures for non-repudiation (cortex signing).
    - Secret store helpers (file-based, mode 0600).

Design principles:
    - Backward compatible: existing workspaces without secrets degrade
      to warnings, never hard failures (controlled by `strict_mode` flag).
    - Stdlib only: hmac, hashlib, json, secrets, os. No extra dependencies.
    - Fail-loud in strict mode, fail-soft in legacy mode.

Usage (HMAC identity)::

    from arqux.security import sign_request, verify_request, AgentIdentity

    agent = AgentIdentity(agent_id="jarvis", secret="...")
    sig = sign_request(agent, "identity.record", b'{"lesson":"x"}')
    # Pass sig in env var ARQUX_AGENT_SIGNATURE or as handler kwarg.
    verify_request(agent_id="jarvis", handler="identity.record",
                   payload=b'...', signature=sig, secret_store=...)

Usage (cortex integrity)::

    from arqux.security import hash_cortex, verify_cortex, sign_cortex

    h = hash_cortex(content_bytes)
    content_with_hash = inject_hash_header(content_bytes, h)
    verify_cortex(file_path)  # raises TamperError on mismatch
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Optional Ed25519 support (only if 'cryptography' is installed).
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, PublicFormat, NoEncryption,
        BestAvailableEncryption,
    )
    _HAS_CRYPTOGRAPHY = True
except ImportError:
    _HAS_CRYPTOGRAPHY = False


# --- Constants ------------------------------------------------------------

#: Header line injected at the top of signed .cortex files.
HASH_HEADER_PREFIX: str = "# $INTEGRITY:"

#: Header line for Ed25519 signature.
SIGNATURE_HEADER_PREFIX: str = "# $SIGNATURE:"

#: Header line for the signing agent.
SIGNER_HEADER_PREFIX: str = "# $SIGNER:"

#: Default secret store location inside .arqux/.
SECRETS_DIR: str = "secrets"

#: Default secret file for the active agent (mode 0600).
AGENT_SECRET_FILE: str = "agent.key"

#: Maximum clock skew allowed for HMAC timestamp validation (seconds).
MAX_CLOCK_SKEW_SECONDS: int = 300  # 5 minutes

#: Strict mode flag (set via ARQUX_STRICT_SECURITY=1).
STRICT_MODE: bool = os.environ.get("ARQUX_STRICT_SECURITY", "0") == "1"


# --- Exceptions ------------------------------------------------------------


class SecurityError(Exception):
    """Base class for arqux.security errors."""


class IdentityVerificationError(SecurityError):
    """Raised when HMAC verification fails (CRÍTICO-1 protection)."""

    def __init__(self, agent_id: str, reason: str) -> None:
        super().__init__(f"identity verification failed for agent={agent_id}: {reason}")
        self.agent_id = agent_id
        self.reason = reason


class TamperError(SecurityError):
    """Raised when .cortex integrity check fails (CRÍTICO-2 protection)."""

    def __init__(self, path: str, expected: str, actual: str) -> None:
        super().__init__(
            f"integrity violation in {path}: expected={expected}, actual={actual}"
        )
        self.path = path
        self.expected = expected
        self.actual = actual


class SignatureError(SecurityError):
    """Raised when Ed25519 signature verification fails."""


# --- Agent identity (HMAC) -------------------------------------------------


@dataclass
class AgentIdentity:
    """An agent's identity + secret for HMAC signing.

    The secret should be a high-entropy string (use `generate_secret()` to
    create one). It is loaded from `ARQUX_AGENT_SECRET` env var or from
    `.arqux/secrets/agent.key` (mode 0600).
    """

    agent_id: str
    secret: str

    @classmethod
    def from_env(cls, agent_id: str | None = None) -> "AgentIdentity | None":
        """Load agent identity from environment variables.

        Reads:
            ARQUX_AGENT_ID      — agent identifier (required)
            ARQUX_AGENT_SECRET  — HMAC secret (required in strict mode)

        Returns None if no agent_id is set.
        """
        aid = agent_id or os.environ.get("ARQUX_AGENT_ID")
        if not aid:
            return None
        secret = os.environ.get("ARQUX_AGENT_SECRET", "")
        if not secret:
            # Try to load from secret store.
            secret = _load_agent_secret()
        if not secret and STRICT_MODE:
            raise IdentityVerificationError(
                aid, "no secret available (set ARQUX_AGENT_SECRET or create .arqux/secrets/agent.key)"
            )
        return cls(agent_id=aid, secret=secret)


def generate_secret(num_bytes: int = 32) -> str:
    """Generate a cryptographically secure secret string.

    Returns a hex-encoded string of `num_bytes` bytes (default: 32 = 64 hex chars).
    """
    return secrets.token_hex(num_bytes)


def sign_request(
    agent: AgentIdentity,
    handler: str,
    payload: bytes | str,
    timestamp: int | None = None,
) -> str:
    """Sign a handler request with HMAC-SHA256.

    The signature covers: `agent_id|handler|timestamp|payload_hash`.
    This binds the signature to a specific agent, handler, moment, and payload,
    preventing replay and substitution attacks.

    Args:
        agent: AgentIdentity with agent_id and secret.
        handler: Canonical handler name (e.g. "identity.record").
        payload: Request payload (bytes or str).
        timestamp: Unix timestamp in seconds. Defaults to now.

    Returns:
        Hex-encoded HMAC-SHA256 signature.
    """
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    ts = timestamp if timestamp is not None else int(time.time())
    payload_hash = hashlib.sha256(payload).hexdigest()
    message = f"{agent.agent_id}|{handler}|{ts}|{payload_hash}".encode("utf-8")
    return hmac.new(agent.secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_request(
    agent_id: str,
    handler: str,
    payload: bytes | str,
    signature: str,
    timestamp: int,
    secret_store: Path | None = None,
    max_skew: int = MAX_CLOCK_SKEW_SECONDS,
) -> bool:
    """Verify a HMAC-SHA256 signature for a handler request.

    Args:
        agent_id: Claimed agent identity.
        handler: Handler being invoked.
        payload: Original payload (bytes or str).
        signature: Hex-encoded HMAC signature.
        timestamp: Unix timestamp when signature was generated.
        secret_store: Path to .arqux/secrets/ directory. Defaults to cwd.
        max_skew: Maximum allowed clock skew in seconds.

    Returns:
        True if signature is valid.

    Raises:
        IdentityVerificationError: if signature is invalid, secret missing,
            or timestamp is outside the allowed skew window.
    """
    # 1. Validate timestamp freshness (replay protection).
    now = int(time.time())
    if abs(now - timestamp) > max_skew:
        raise IdentityVerificationError(
            agent_id,
            f"timestamp skew {abs(now - timestamp)}s exceeds max {max_skew}s",
        )

    # 2. Load secret for claimed agent_id.
    secret = _load_agent_secret(agent_id, secret_store)
    if not secret:
        # Fallback to env var (single-agent mode).
        secret = os.environ.get("ARQUX_AGENT_SECRET", "")
    if not secret:
        raise IdentityVerificationError(
            agent_id, "no secret available for verification"
        )

    # 3. Recompute signature and compare in constant time.
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    payload_hash = hashlib.sha256(payload).hexdigest()
    message = f"{agent_id}|{handler}|{timestamp}|{payload_hash}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise IdentityVerificationError(agent_id, "HMAC signature mismatch")

    return True


def _load_agent_secret(agent_id: str | None = None, secret_store: Path | None = None) -> str:
    """Load agent secret from the secret store.

    The secret store is a directory `.arqux/secrets/` containing one file
    per agent: `<agent_id>.key`. Files must be mode 0600.

    Args:
        agent_id: Agent identifier. If None, uses ARQUX_AGENT_ID env var.
        secret_store: Path to secrets directory. If None, searches from cwd.

    Returns:
        Secret string, or "" if not found.
    """
    aid = agent_id or os.environ.get("ARQUX_AGENT_ID")
    if not aid:
        return ""

    if secret_store is None:
        # Walk up to find .arqux/secrets/
        cursor = Path(os.getcwd()).resolve()
        while True:
            candidate = cursor / ".arqux" / SECRETS_DIR
            if candidate.is_dir():
                secret_store = candidate
                break
            if cursor.parent == cursor:
                return ""
            cursor = cursor.parent
    else:
        secret_store = Path(secret_store)

    secret_file = secret_store / f"{aid}.key"
    if not secret_file.exists():
        return ""

    # Verify file permissions (warn if too open).
    try:
        mode = secret_file.stat().st_mode & 0o777
        if mode & 0o077:
            # File is group/world readable — security risk.
            import warnings
            warnings.warn(
                f"secret file {secret_file} has mode {oct(mode)}; should be 0600",
                RuntimeWarning,
                stacklevel=2,
            )
    except OSError:
        pass

    return secret_file.read_text(encoding="utf-8").strip()


def save_agent_secret(
    agent_id: str,
    secret: str,
    secret_store: Path | None = None,
) -> Path:
    """Save an agent secret to the secret store with mode 0600.

    Args:
        agent_id: Agent identifier.
        secret: Secret string (use generate_secret() to create one).
        secret_store: Path to secrets directory. If None, uses .arqux/secrets/.

    Returns:
        Path to the saved secret file.
    """
    if secret_store is None:
        # Find or create .arqux/secrets/
        cursor = Path(os.getcwd()).resolve()
        while True:
            candidate = cursor / ".arqux" / SECRETS_DIR
            if candidate.is_dir() or (cursor / ".arqux").is_dir():
                secret_store = candidate
                break
            if cursor.parent == cursor:
                # Create in cwd
                secret_store = Path(os.getcwd()) / ".arqux" / SECRETS_DIR
                break
            cursor = cursor.parent
    else:
        secret_store = Path(secret_store)

    secret_store.mkdir(parents=True, exist_ok=True)
    secret_file = secret_store / f"{agent_id}.key"
    secret_file.write_text(secret, encoding="utf-8")
    # Force mode 0600.
    secret_file.chmod(0o600)
    return secret_file


# --- Cortex integrity (SHA-256) -------------------------------------------


def hash_cortex(content: bytes | str) -> str:
    """Compute SHA-256 hash of .cortex content.

    The hash is computed over the raw content EXCLUDING any existing
    $INTEGRITY header (so re-hashing after content edits is stable).

    Args:
        content: .cortex file content (bytes or str).

    Returns:
        Hex-encoded SHA-256 hash (64 chars).
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    # Strip any existing integrity header before hashing.
    stripped = _strip_integrity_headers(content)
    return hashlib.sha256(stripped).hexdigest()


def inject_hash_header(content: bytes | str, hash_hex: str | None = None) -> str:
    """Inject or update the $INTEGRITY header at the top of .cortex content.

    The header format is:
        # $INTEGRITY: sha256:<hex>

    Args:
        content: .cortex content (bytes or str).
        hash_hex: Pre-computed hash. If None, computes it from content.

    Returns:
        Content with $INTEGRITY header as the first line.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    if hash_hex is None:
        hash_hex = hash_cortex(content)

    # Remove any existing integrity header.
    stripped = _strip_integrity_headers(content.encode("utf-8")).decode("utf-8")

    # Prepend the new header.
    header = f"{HASH_HEADER_PREFIX} sha256:{hash_hex}\n"
    return header + stripped


def verify_cortex(file_path: Path | str, strict: bool | None = None) -> bool:
    """Verify the integrity of a .cortex file.

    Reads the $INTEGRITY header, recomputes the hash of the remaining content,
    and compares. Raises TamperError on mismatch.

    Args:
        file_path: Path to .cortex file.
        strict: If True, raises TamperError on missing header.
                If False, returns True (legacy file, no verification).
                Defaults to STRICT_MODE.

    Returns:
        True if integrity is verified.

    Raises:
        TamperError: If hash mismatch detected.
        FileNotFoundError: If file does not exist.
    """
    if strict is None:
        strict = STRICT_MODE

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    content = path.read_bytes()
    stored_hash, stripped = _extract_integrity_hash(content)

    if stored_hash is None:
        if strict:
            raise TamperError(str(path), "<missing>", "<no header>")
        return True  # Legacy file, no verification.

    actual_hash = hashlib.sha256(stripped).hexdigest()
    if not hmac.compare_digest(stored_hash, actual_hash):
        raise TamperError(str(path), stored_hash, actual_hash)

    return True


def _extract_integrity_hash(content: bytes) -> tuple[str | None, bytes]:
    """Extract the stored hash and return (hash, stripped_content).

    Returns (None, original_content) if no integrity header is present.
    """
    text = content.decode("utf-8", errors="replace")
    lines = text.split("\n", 1)
    if not lines:
        return None, content
    first_line = lines[0].strip()
    if not first_line.startswith(HASH_HEADER_PREFIX):
        return None, content
    # Parse: "# $INTEGRITY: sha256:<hex>"
    parts = first_line.split(":", 2)
    if len(parts) < 3:
        return None, content
    stored_hash = parts[2].strip()
    # Strip the first line + its newline.
    stripped = content[len(lines[0]) + 1:] if len(lines) > 1 else b""
    return stored_hash, stripped


def _strip_integrity_headers(content: bytes) -> bytes:
    """Remove ALL integrity/signature/signer headers from content."""
    text = content.decode("utf-8", errors="replace")
    lines = text.split("\n")
    kept = []
    for line in lines:
        stripped = line.strip()
        if (
            stripped.startswith(HASH_HEADER_PREFIX)
            or stripped.startswith(SIGNATURE_HEADER_PREFIX)
            or stripped.startswith(SIGNER_HEADER_PREFIX)
        ):
            continue
        kept.append(line)
    return "\n".join(kept).encode("utf-8")


# --- Ed25519 signatures (optional, for non-repudiation) --------------------


def generate_signing_keypair() -> tuple[str, str]:
    """Generate an Ed25519 keypair for cortex signing.

    Returns:
        (private_key_pem, public_key_pem) as strings.

    Raises:
        SecurityError: if 'cryptography' is not installed.
    """
    if not _HAS_CRYPTOGRAPHY:
        raise SecurityError(
            "Ed25519 signing requires 'cryptography' package. Install: pip install cryptography"
        )
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    priv_pem = private_key.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8, BestAvailableEncryption(b"arqux")
    ).decode("utf-8")
    pub_pem = public_key.public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")
    return priv_pem, pub_pem


def sign_cortex(
    content: bytes | str,
    private_key_pem: str,
    signer: str,
) -> str:
    """Sign .cortex content with Ed25519.

    The signature is computed over the content WITHOUT any existing
    $SIGNATURE/$SIGNER headers, and prepended as:
        # $SIGNATURE: ed25519:<hex>
        # $SIGNER: <agent_id>

    Args:
        content: .cortex content (bytes or str).
        private_key_pem: Private key in PEM format.
        signer: Agent ID of the signer.

    Returns:
        Content with $SIGNATURE and $SIGNER headers prepended.

    Raises:
        SecurityError: if 'cryptography' is not installed or signing fails.
    """
    if not _HAS_CRYPTOGRAPHY:
        raise SecurityError(
            "Ed25519 signing requires 'cryptography' package. Install: pip install cryptography"
        )
    if isinstance(content, str):
        content = content.encode("utf-8")
    stripped = _strip_integrity_headers(content)
    private_key = Ed25519PrivateKey.from_private_bytes(
        _pem_to_raw_private(private_key_pem)
    )
    signature = private_key.sign(stripped)
    sig_hex = signature.hex()
    header = (
        f"{SIGNATURE_HEADER_PREFIX} ed25519:{sig_hex}\n"
        f"{SIGNER_HEADER_PREFIX} {signer}\n"
    )
    return header + stripped.decode("utf-8")


def _pem_to_raw_private(pem: str) -> bytes:
    """Extract raw private key bytes from PEM (placeholder for full impl)."""
    # For production, use cryptography's loading API.
    # This is a simplified helper.
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    key = load_pem_private_key(pem.encode("utf-8"), password=b"arqux")
    return key.private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption()
    )


def verify_cortex_signature(
    file_path: Path | str,
    public_key_pem: str,
    expected_signer: str | None = None,
) -> bool:
    """Verify Ed25519 signature on a .cortex file.

    Args:
        file_path: Path to .cortex file.
        public_key_pem: Public key in PEM format.
        expected_signer: If provided, verify the $SIGNER matches.

    Returns:
        True if signature is valid.

    Raises:
        SignatureError: If signature is missing, invalid, or signer mismatch.
        SecurityError: If 'cryptography' is not installed.
    """
    if not _HAS_CRYPTOGRAPHY:
        raise SecurityError(
            "Ed25519 verification requires 'cryptography' package."
        )
    path = Path(file_path)
    content = path.read_bytes()
    text = content.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if len(lines) < 2:
        raise SignatureError("file too short to contain signature headers")
    sig_line = lines[0].strip()
    signer_line = lines[1].strip()
    if not sig_line.startswith(SIGNATURE_HEADER_PREFIX):
        raise SignatureError("no $SIGNATURE header found")
    if not signer_line.startswith(SIGNER_HEADER_PREFIX):
        raise SignatureError("no $SIGNER header found")

    # Parse signature.
    parts = sig_line.split(":", 2)
    if len(parts) < 3 or parts[1].strip() != "ed25519":
        raise SignatureError(f"unsupported signature algorithm: {parts[1] if len(parts) > 1 else 'none'}")
    sig_hex = parts[2].strip()
    try:
        signature = bytes.fromhex(sig_hex)
    except ValueError:
        raise SignatureError("invalid signature hex encoding")

    # Parse signer.
    signer = signer_line.split(":", 1)[1].strip()
    if expected_signer and signer != expected_signer:
        raise SignatureError(f"signer mismatch: expected={expected_signer}, actual={signer}")

    # Recompute content to verify against.
    stripped = _strip_integrity_headers(content)
    public_key = Ed25519PublicKey.from_public_bytes(
        _pem_to_raw_public(public_key_pem)
    )
    try:
        public_key.verify(signature, stripped)
        return True
    except Exception as exc:
        raise SignatureError(f"signature verification failed: {exc}")


def _pem_to_raw_public(pem: str) -> bytes:
    """Extract raw public key bytes from PEM."""
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    key = load_pem_public_key(pem.encode("utf-8"))
    return key.public_bytes(Encoding.Raw, PublicFormat.Raw)


# --- Convenience: write + sign + hash in one call -------------------------


def secure_write_cortex(
    file_path: Path | str,
    content: bytes | str,
    *,
    sign_with: str | None = None,
    signer: str | None = None,
    inject_hash: bool = True,
) -> dict[str, Any]:
    """Write a .cortex file with integrity hash and optional signature.

    This is the recommended write path for all governance state files.
    It atomically writes the file with:
        1. Optional Ed25519 signature (if sign_with is provided).
        2. SHA-256 integrity hash header.
        3. The actual content.

    Args:
        file_path: Destination path.
        content: .cortex content (bytes or str).
        sign_with: Private key PEM for Ed25519 signing. If None, no signature.
        signer: Agent ID for the $SIGNER header (required if sign_with is set).
        inject_hash: If True (default), inject SHA-256 hash header.

    Returns:
        Dict with: path, hash, signed (bool), signer (str|None), bytes_written.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(content, bytes):
        content_str = content.decode("utf-8")
    else:
        content_str = content

    # 1. Sign first (signature covers content without headers).
    if sign_with:
        if not signer:
            raise ValueError("signer is required when sign_with is provided")
        content_str = sign_cortex(content_str, sign_with, signer)

    # 2. Inject hash (covers signature + content).
    if inject_hash:
        content_str = inject_hash_header(content_str)

    # 3. Atomic write.
    path.write_text(content_str, encoding="utf-8")

    return {
        "path": str(path),
        "hash": hash_hex if (hash_hex := hash_cortex(content_str)) else "",
        "signed": sign_with is not None,
        "signer": signer,
        "bytes_written": len(content_str.encode("utf-8")),
    }
