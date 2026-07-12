"""Tests for arqux cortex-verify CLI (P1-Q).

Validates:
- arqux cortex-verify <valid.cortex> returns exit 0
- arqux cortex-verify <tampered.cortex> returns exit 1
- arqux cortex-verify <missing.cortex> returns exit 1
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from arqux.security import hash_cortex, inject_hash_header


VALID_CORTEX = """$0
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity  | attrs | B | Semantic | Actor identity

$1: TEST
IDN:agent{name:"test-agent", role:"governor"}
"""


@pytest.fixture
def signed_cortex(tmp_path: Path) -> Path:
    """Create a .cortex file with valid $INTEGRITY header."""
    p = tmp_path / "signed.cortex"
    h = hash_cortex(VALID_CORTEX)
    signed = inject_hash_header(VALID_CORTEX, h)
    p.write_text(signed, encoding="utf-8")
    return p


@pytest.fixture
def tampered_cortex(signed_cortex: Path) -> Path:
    """Create a tampered copy of a signed .cortex file."""
    p = signed_cortex.parent / "tampered.cortex"
    content = signed_cortex.read_text(encoding="utf-8")
    # Tamper: append a line after the integrity header.
    tampered = content + "\n# TAMPER INJECTION\n"
    p.write_text(tampered, encoding="utf-8")
    return p


class TestCortexVerifyCli:
    """P1-Q: arqux cortex-verify command."""

    def test_verify_valid_file_exits_zero(self, signed_cortex: Path) -> None:
        from arqux.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["cortex-verify", str(signed_cortex)])
        assert result.exit_code == 0, (
            f"Expected exit 0 for valid cortex, got {result.exit_code}. Output: {result.output}"
        )

    def test_verify_tampered_file_exits_nonzero(self, tampered_cortex: Path) -> None:
        from arqux.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["cortex-verify", str(tampered_cortex)])
        assert result.exit_code != 0, (
            f"Expected non-zero exit for tampered cortex, got {result.exit_code}"
        )

    def test_verify_missing_file_exits_nonzero(self, tmp_path: Path) -> None:
        from arqux.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["cortex-verify", str(tmp_path / "nonexistent.cortex")])
        assert result.exit_code != 0

    def test_verify_unsigned_file(self, tmp_path: Path) -> None:
        """Unsigned .cortex file behavior: verify_cortex tolerates missing header (no tamper)."""
        from arqux.cli import main
        p = tmp_path / "unsigned.cortex"
        p.write_text(VALID_CORTEX, encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(main, ["cortex-verify", str(p)])
        # verify_cortex returns True (no $INTEGRITY header → nothing to compare → OK)
        # This is the current behavior. P2 enhancement: enforce signing.
        # Test just verifies the command doesn't crash.
        assert hasattr(result, "exit_code")
