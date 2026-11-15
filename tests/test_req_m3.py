"""REQ M3 regression tests (nicho.md): REQ-11 evidence export,
REQ-12 Ed25519 signing, REQ-13 journal sync.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from arqux.cli import main
from arqux.evidence_export import export_bundle
from arqux.journal import journal_version, pull_policy, push_delta
from arqux.signing import (
    generate_keypair,
    public_key,
    sign,
    sign_document,
    verify,
    verify_document,
)

# ---------------------------------------------------------------------------
# REQ-12 — Ed25519 (vectors verified against cryptography lib at dev time)

SEED = bytes.fromhex(
    "9d61b19deffebc3a6888f98f8fbf6b5d5b8ff3a04d3ee04e4c4b3c0b0f9e2d99"
)
PUB = "d61c1f8a434c1060ba8750878fd850c8be2665125e0963b33e919304e7425c86"
SIG = (
    "a8148d3e63e94c33e5038d1c2673b5b7c0bb1e0a5a9e93f1e3c10cbb0c4616c71af"
    "5cc9830d7caae934d19f31f6d243222f92de50cb6619e70c3e34a8e2fdb0c"
)


def test_ed25519_known_vector() -> None:
    assert public_key(SEED).hex() == PUB
    assert sign(SEED, b"").hex() == SIG
    assert verify(bytes.fromhex(PUB), b"", bytes.fromhex(SIG))
    assert not verify(bytes.fromhex(PUB), b"x", bytes.fromhex(SIG))


def test_sign_and_verify_document(tmp_path: Path) -> None:
    key = tmp_path / "k.key"
    generate_keypair(key)
    doc = tmp_path / "pol.cortex"
    doc.write_text(
        "$0\n$0:format{cortex:1.0, encoding:UTF-8}\n\n"
        '$1: RULES\n\nRUL:r{enforce:"CODE", on:"*", check:"x"}\n'
    )
    sign_document(doc, key)
    assert "SIG:signature{" in doc.read_text()
    from arqux.signing import load_keypair
    _, pub = load_keypair(key)
    assert verify_document(doc, pub.hex())["valid"] is True

    doc.write_text(doc.read_text().replace('enforce:"CODE"', 'enforce:"HUMAN"'))
    result = verify_document(doc, pub.hex())
    assert not result["valid"]
    assert result["error"] == "ERR_INVALID_SIGNATURE"


def test_policy_cli_roundtrip(tmp_path: Path) -> None:
    runner = CliRunner()
    key = tmp_path / "k.key"
    assert runner.invoke(main, ["policy", "keygen", str(key)]).exit_code == 0
    doc = tmp_path / "pol.cortex"
    doc.write_text("$0\n$0:format{cortex:1.0, encoding:UTF-8}\n\n$1: R\nRUL:r{enforce:\"CODE\"}\n")
    assert runner.invoke(
        main, ["policy", "sign", str(doc), "--key", str(key)]
    ).exit_code == 0
    ok = runner.invoke(main, ["policy", "verify", str(doc), "--key", str(key)])
    assert ok.exit_code == 0 and "SIGNATURE_VALID" in ok.output
    doc.write_text(doc.read_text() + "\n# tampered\n")
    bad = runner.invoke(main, ["policy", "verify", str(doc), "--key", str(key)])
    assert bad.exit_code == 1 and "ERR_INVALID_SIGNATURE" in bad.output


# ---------------------------------------------------------------------------
# REQ-11 — evidence export

_TIMELOG = """\
$0
$0:format{cortex:1.0, encoding:UTF-8}

$1: IDENTITY
SES:ses001{agent:"alfred", opened:"2026-11-15T10:00:00Z", closed:"2026-11-15T11:00:00Z"}

$5: EVENTS
AUD:e_0001{kind:"audit", msg:"cycle closed"}
ERR:e_0002{kind:"error", msg:"transient", visibility:"private"}
"""


def _timelogged_project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    tl = proj / ".arqux" / "timelog"
    tl.mkdir(parents=True)
    (tl / "SES001_x.cortex").write_text(_TIMELOG)
    return proj


def test_export_blocked_without_flags(tmp_path: Path) -> None:
    proj = _timelogged_project(tmp_path)
    try:
        export_bundle(proj, tmp_path / "b.cortex")
        raise AssertionError("should have blocked")
    except PermissionError as e:
        assert "redact-private" in str(e) or "allow-raw" in str(e)


def test_export_redact_strips_private(tmp_path: Path) -> None:
    proj = _timelogged_project(tmp_path)
    result = export_bundle(proj, tmp_path / "b.cortex", redact_private=True)
    text = (tmp_path / "b.cortex").read_text()
    assert 'visibility:"private"' not in text
    assert "ERR:e_0002" not in text
    assert "AUD:e_0001" in text
    assert result["redacted"] == 1


def test_export_allow_raw_keeps_private(tmp_path: Path) -> None:
    proj = _timelogged_project(tmp_path)
    export_bundle(proj, tmp_path / "b.cortex", allow_raw=True)
    assert 'visibility:"private"' in (tmp_path / "b.cortex").read_text()


# ---------------------------------------------------------------------------
# REQ-13 — journal sync


def test_push_delta_optimistic_lock(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    d1 = 'RUL:a{enforce:"CODE", on:"*", check:"x"}\n'
    d2 = 'POL:b{action:"apply", enforce:"CODE"}\n'

    assert push_delta(ws, "ws-a", d1, base_version=0)["applied"]
    assert journal_version(ws) == 1

    # stale base → conflict
    stale = push_delta(ws, "ws-b", d2, base_version=0)
    assert not stale["applied"]
    assert stale["error"] == "ERR_CONFLICT_VERSION"

    # correct base → applied, disjoint entries preserved
    ok = push_delta(ws, "ws-b", d2, base_version=1)
    assert ok["applied"] and ok["version"] == 2
    pulled = pull_policy(ws)
    assert "RUL:a" in pulled and "POL:b" in pulled


def test_same_rule_same_base_conflict(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    push_delta(ws, "ws-a", 'RUL:r{enforce:"CODE"}\n', base_version=0)
    conflict = push_delta(ws, "ws-c", 'RUL:r{enforce:"PROMPT"}\n', base_version=0)
    assert not conflict["applied"]
    assert conflict["error"] == "ERR_CONFLICT_VERSION"
    # retry at the new head replaces deterministically
    retry = push_delta(ws, "ws-c", 'RUL:r{enforce:"PROMPT"}\n', base_version=1)
    assert retry["applied"]
    assert 'RUL:r{enforce:"PROMPT"}' in pull_policy(ws)


def test_push_delta_empty_rejected(tmp_path: Path) -> None:
    result = push_delta(tmp_path, "ws", "# no rules\n", base_version=0)
    assert not result["applied"]
    assert result["error"] == "ERR_EMPTY_DELTA"
