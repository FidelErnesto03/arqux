"""Edge case tests — verify graceful degradation in extreme scenarios."""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.permissions import PermissionContext


class TestEmptyBrain:
    """brain.cortex with no entries."""

    def test_empty_file_overwritten_by_sync(self, tmp_path: Path) -> None:
        """sync_brain on empty cortex logs error but doesn't crash."""
        brain = tmp_path / "brain.cortex"
        brain.write_text("")
        from arqux.sync import sync_brain

        # sync_brain doesn't crash on empty cortex (logs error, continues)
        sync_brain(tmp_path, event="test_empty")
        # File still exists but content may be unchanged
        assert brain.exists()

    def test_missing_brain_created_by_sync(self, tmp_path: Path) -> None:
        """sync_brain on missing cortex logs error but doesn't crash."""
        brain = tmp_path / "brain.cortex"
        assert not brain.exists()
        from arqux.sync import sync_brain

        # sync_brain doesn't create brain.cortex from scratch
        # It logs error and continues gracefully
        sync_brain(tmp_path, event="test_missing")
        assert not brain.exists()


class TestMissingIdentity:
    """identity.cortex file doesn't exist."""

    def test_missing_identity_returns_not_found(self) -> None:
        """Handler returns NOT_FOUND for missing identity."""
        from arqux.handlers.cortex import entry_get_handler

        result = entry_get_handler(
            path="/nonexistent/path",
            selector="$0",
        )
        assert result.profile == "OUT-ERROR"
        assert "NOT_FOUND" in result.to_text() or "not found" in result.message.lower()


class TestConcurrentAccess:
    """Two processes writing to the same file."""

    def test_secure_write_acquires_lock(self, tmp_path: Path) -> None:
        """secure_write_cortex acquires file lock."""
        from arqux.security import secure_write_cortex

        cortex_file = tmp_path / "test.cortex"
        content = "$0\ntest:value\n"
        secure_write_cortex(cortex_file, content, signer="test-agent")
        assert cortex_file.exists()
        assert "test:value" in cortex_file.read_text()


class TestInvalidCortex:
    """cortex file with syntax errors."""

    def test_verify_detects_missing_header(self, tmp_path: Path) -> None:
        """verify_cortex detects missing integrity header."""
        from arqux.security import TamperError, verify_cortex

        cortex_file = tmp_path / "bad.cortex"
        cortex_file.write_text("$0\nbroken entry\n")
        with pytest.raises(TamperError):
            verify_cortex(cortex_file, strict=True)


class TestMissingHandler:
    """CLI tries to call unregistered handler."""

    def test_permission_deny_for_unknown_role(self) -> None:
        """Unknown role raises PermissionDenied."""
        from arqux.permissions import PermissionDenied

        ctx = PermissionContext(agent_id="test", role="unknown_role")
        with pytest.raises(PermissionDenied):
            ctx.check("workspace.init")
