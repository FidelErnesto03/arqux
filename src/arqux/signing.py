"""REQ-12: real Ed25519 signing for evidence bundles and policy releases.

Pure-Python Ed25519 (RFC 8032) — no third-party crypto dependency, which
keeps ArqUX installable in air-gapped environments. Correctness is pinned
by RFC 8032 test vectors in ``tests/test_req_m3.py``.

Signs the *canonical bytes* of a document excluding its own ``SIG:`` lines,
so a signature entry can live inside the signed file: altering any other
attribute breaks ``ERR_INVALID_SIGNATURE`` on verify.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

# --- Ed25519 core (RFC 8032, public-domain reference math) ------------------

_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _Q - 2, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q:
        x = (x * _I) % _Q
    if x % 2:
        x = _Q - x
    return x


_B = (_xrecover(4 * pow(5, _Q - 2, _Q) % _Q), 4 * pow(5, _Q - 2, _Q) % _Q)
_IDENTITY = (0, 1)


def _edwards(p: tuple[int, int], q_: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = p
    x2, y2 = q_
    denom = pow(1 + _D * x1 * x2 * y1 * y2, _Q - 2, _Q)
    x3 = ((x1 * y2 + x2 * y1) * denom) % _Q
    denom = pow(1 - _D * x1 * x2 * y1 * y2, _Q - 2, _Q)
    y3 = ((y1 * y2 + x1 * x2) * denom) % _Q
    return x3, y3


def _scalarmult(p: tuple[int, int], e: int) -> tuple[int, int]:
    result = _IDENTITY
    addend = p
    while e:
        if e & 1:
            result = _edwards(result, addend)
        addend = _edwards(addend, addend)
        e >>= 1
    return result


def _hint(m: bytes) -> int:
    return int.from_bytes(hashlib.sha512(m).digest(), "little")


def _encode_point(p: tuple[int, int]) -> bytes:
    x, y = p
    return y.to_bytes(32, "little")[:-1] + bytes([y.to_bytes(32, "little")[-1] & 0x7F | (x & 1) << 7])


def _decode_point(s: bytes) -> tuple[int, int]:
    y = int.from_bytes(s, "little") & ((1 << 255) - 1)
    x = _xrecover(y)
    if x & 1 != s[31] >> 7:
        x = _Q - x
    p = (x, y)
    if not _isoncurve(p):
        raise ValueError("point not on curve")
    return p


def _isoncurve(p: tuple[int, int]) -> bool:
    x, y = p
    return (-x * x + y * y - 1 - _D * x * x * y * y) % _Q == 0


def _clamp(h: bytes) -> int:
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a


def public_key(seed: bytes) -> bytes:
    """32-byte public key for a 32-byte private seed."""
    h = hashlib.sha512(seed).digest()
    a = _clamp(h)
    return _encode_point(_scalarmult(_B, a))


def sign(seed: bytes, message: bytes) -> bytes:
    """64-byte Ed25519 signature."""
    h = hashlib.sha512(seed).digest()
    a = _clamp(h)
    pub = _encode_point(_scalarmult(_B, a))
    r = _hint(h[32:] + message) % _L
    r_point = _encode_point(_scalarmult(_B, r))
    s = (r + _hint(r_point + pub + message) * a) % _L
    return r_point + s.to_bytes(32, "little")


def verify(public: bytes, message: bytes, signature: bytes) -> bool:
    """True iff *signature* is a valid Ed25519 signature of *message*."""
    if len(signature) != 64 or len(public) != 32:
        return False
    try:
        a = _decode_point(public)
        r = _decode_point(signature[:32])
    except ValueError:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False
    h = _hint(signature[:32] + public + message)
    # [S]B == R + [H(R,A,m)]A — cofactorless verification per RFC 8032
    return _scalarmult(_B, s) == _edwards(r, _scalarmult(a, h))


# --- key files + signed documents -------------------------------------------

_SIG_LINE_RX = re.compile(r"^SIG:signature\{[^}]*\}\s*$", re.M)


def generate_keypair(key_path: Path) -> dict:
    """Create a keypair file: hex seed + hex public key (0600)."""
    seed = os.urandom(32)
    pub = public_key(seed)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(
        f"seed:{seed.hex()}\npublic:{pub.hex()}\n", encoding="utf-8"
    )
    key_path.chmod(0o600)
    return {"key_id": pub.hex()[:16], "public": pub.hex()}


def load_keypair(key_path: Path) -> tuple[bytes, bytes]:
    data = dict(
        line.split(":", 1)
        for line in key_path.read_text(encoding="utf-8").splitlines()
        if ":" in line
    )
    return bytes.fromhex(data["seed"]), bytes.fromhex(data["public"])


def canonical_signed_text(text: str) -> bytes:
    """Document bytes the signature covers.

    SIG:signature lines are stripped and trailing whitespace normalized to a
    single newline, so the signature is stable regardless of how the sig
    entry was appended.
    """
    return (_SIG_LINE_RX.sub("", text).rstrip("\n") + "\n").encode("utf-8")


_SIG_CONTRACT = (
    'SIG:sig_contract{type:"attrs", weight:"H", focus:"value", '
    'fields:"algo:text|key_id:text|payload_sha256:text|sig:text", '
    'desc:"Ed25519 signature over the document payload", open:true}'
)


def sign_document(path: Path, key_path: Path) -> dict:
    """Append/update the SIG:signature entry in a .cortex document."""
    seed, pub = load_keypair(key_path)
    text = path.read_text(encoding="utf-8")
    base_text = _SIG_LINE_RX.sub("", text)
    # Declared-sigil invariant: a signed document stays self-contained —
    # inject the SIG contract into $0 when missing.
    if "SIG:" not in base_text:
        base_text = re.sub(
            r"^(\$0:format\{[^}]*\}\s*)$",
            r"\1\n" + _SIG_CONTRACT,
            base_text,
            count=1,
            flags=re.M,
        )
    base = canonical_signed_text(base_text)
    digest = hashlib.sha256(base).hexdigest()
    sig = sign(seed, base).hex()
    sig_line = (
        f'SIG:signature{{algo:"ed25519", key_id:"{pub.hex()[:16]}", '
        f'payload_sha256:"{digest}", sig:"{sig}"}}'
    )
    path.write_text(base_text.rstrip("\n") + "\n\n" + sig_line + "\n",
                    encoding="utf-8")
    return {"key_id": pub.hex()[:16], "payload_sha256": digest, "sig": sig}


def verify_document(path: Path, public_hex: str | None = None) -> dict:
    """Verify the SIG:signature entry; returns the verdict dict."""
    text = path.read_text(encoding="utf-8")
    m = re.search(
        r'SIG:\w+\{[^}]*key_id:"([0-9a-f]+)"[^}]*sig:"([0-9a-f]{128})"', text
    )
    if not m:
        return {"valid": False, "error": "ERR_NO_SIGNATURE",
                "detail": "no SIG:signature entry found"}
    key_id, sig_hex = m.groups()
    if public_hex and not public_hex.startswith(key_id):
        return {"valid": False, "error": "ERR_KEY_MISMATCH",
                "detail": f"document signed by {key_id}, verifier holds {public_hex[:16]}"}
    try:
        pub = bytes.fromhex(public_hex) if public_hex else bytes.fromhex(
            _lookup_public_key(key_id, path.parent)
        )
    except (ValueError, FileNotFoundError) as exc:
        return {"valid": False, "error": "ERR_KEY_NOT_FOUND",
                "detail": f"cannot resolve public key {key_id}: {exc}"}
    ok = verify(pub, canonical_signed_text(text), bytes.fromhex(sig_hex))
    return ({"valid": True, "key_id": key_id}
            if ok else
            {"valid": False, "error": "ERR_INVALID_SIGNATURE",
             "detail": f"signature does not match document payload (key {key_id})"})


def _lookup_public_key(key_id: str, near: Path) -> str:
    """Find the public key for *key_id* in .arqux/keys/ near the document."""
    for root in [near / ".arqux" / "keys", near.parent / ".arqux" / "keys"]:
        if not root.is_dir():
            continue
        for f in root.iterdir():
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.startswith("public:") and line[7:].startswith(key_id):
                    return line[7:]
    raise FileNotFoundError(f"no public key matching {key_id}")


__all__ = [
    "canonical_signed_text",
    "generate_keypair",
    "load_keypair",
    "public_key",
    "sign",
    "sign_document",
    "verify",
    "verify_document",
]
