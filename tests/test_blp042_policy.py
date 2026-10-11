"""Tests for BLP-042: CODEC-CORTEX writer policy enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.handlers import cortex as cortex_handlers
from arqux.permissions import PermissionContext

#: Attributes of a CODEC-CORTEX glossary declaration. An entry carrying all of
#: them is a declaration of the sigil, not a recorded instance of it.
_DECLARATION_FIELDS = frozenset({"type", "weight", "focus", "desc"})

# --- Fixtures ---------------------------------------------------------------

@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """Create a minimal workspace with .arqux/identities/."""
    d = tmp_path / ".arqux" / "identities"
    d.mkdir(parents=True)
    agent_file = d / "test-agent.cortex"
    agent_file.write_text(
        "$0\n\n"
        "# -- $0: GLOSSARY --\n"
        "# Sigil | Name | Type | Risk | Layer | Description\n"
        "# LNG   | lesson     | attrs      | M | Episodic       | Lesson\n"
        "# OBJ   | objective  | attrs      | H | Working        | Objective\n\n"
        "$0.1: ARQUX METADATA\n\n"
        "ARQX:artifact{level:1, name:\"test-agent\", usage:\"identity\", kind:\"native\", agent:\"test-agent\"}\n\n"
        "$1: IDENTITY\n\n"
        "IDN:test-agent{name:\"TestAgent\", role:\"executor\"}\n\n"
        "$2: FOCUS\n\n"
        "FCS:default{what:\"Test\", priority:\"low\", status:\"current\", survive:\"min\"}\n\n"
        "$3: OBJECTIVES\n\n"
        "OBJ:main{goal:\"Test\", status:\"current\", survive:\"min\"}\n\n"
        "$5: BEHAVIORAL LESSONS\n\n"
    )
    return tmp_path


@pytest.fixture
def ctx() -> PermissionContext:
    return PermissionContext(agent_id="test-agent", role="executor")


# --- Tests ------------------------------------------------------------------


class TestRecordLessonPrevention:
    """BLP-042: identity.record writes LNG with prevention field."""

    def test_record_with_prevention(self, workspace_root: Path, ctx: PermissionContext) -> None:
        """LNG entry includes prevention when parameter is provided."""
        result = cortex_handlers.record_lesson_handler(
            lesson="Test prevention field",
            kind="process",
            cause="Testing prevention parameter",
            prevention="Always include prevention in LNG entries",
            agent_id="test-agent",
            path=str(workspace_root),
            ctx=ctx,
        )
        # On success, profile should not be OUT-ERROR
        assert result.profile != "OUT-ERROR", f"Handler returned error: {result.message}"

        # Read back and verify LNG contains prevention
        identity_file = workspace_root / ".arqux" / "identities" / "test-agent.cortex"
        content = identity_file.read_text(encoding="utf-8")
        assert "prevention" in content, "prevention field missing from identity file"
        assert "Always include prevention in LNG entries" in content

    def test_record_without_prevention(self, workspace_root: Path, ctx: PermissionContext) -> None:
        """LNG entry accepts empty prevention string (falls back to empty)."""
        result = cortex_handlers.record_lesson_handler(
            lesson="Test without prevention",
            kind="behavioral",
            cause="Testing empty prevention",
            prevention="",
            agent_id="test-agent",
            path=str(workspace_root),
            ctx=ctx,
        )
        assert result.profile != "OUT-ERROR", f"Handler returned error: {result.message}"

        # Should still have prevention in the entry (empty string is acceptable)
        identity_file = workspace_root / ".arqux" / "identities" / "test-agent.cortex"
        content = identity_file.read_text(encoding="utf-8")
        assert "prevention" in content, "prevention field should exist even if empty"

    def test_no_direct_write_bypass(self, workspace_root: Path, ctx: PermissionContext) -> None:
        """The handler uses crud_add (CODEC-CORTEX), not direct string append."""
        result = cortex_handlers.record_lesson_handler(
            lesson="No bypass test",
            kind="process",
            cause="Testing that no bypass occurs",
            prevention="CODEC-CORTEX only",
            agent_id="test-agent",
            path=str(workspace_root),
            ctx=ctx,
        )
        assert result.profile != "OUT-ERROR", f"Handler returned error: {result.message}"

        # Verify the file can be parsed by CODEC-CORTEX with proper LNG structure
        identity_file = workspace_root / ".arqux" / "identities" / "test-agent.cortex"
        from cortex.core.parser import parse_cortex
        doc = parse_cortex(identity_file.read_text(encoding="utf-8"), path=str(identity_file))

        # Find the LNG entry and verify all required fields.
        #
        # Only OPERATIONAL lessons are checked. The identity file also carries
        # the glossary declaration `LNG:lesson{type,weight,focus,desc}` in $0,
        # which is metadata, not a lesson — asserting that it carries a
        # `prevention` field is meaningless, and it made this test fail for a
        # reason unrelated to what it claims to verify.
        lng_found = False
        for sec in doc.sections:
            for entry in sec.entries:
                if entry.sigil != "LNG":
                    continue
                if sec.id == "$0" or set(entry.value or {}) >= _DECLARATION_FIELDS:
                    continue  # glossary declaration
                lng_found = True
                assert isinstance(entry.value, dict), "LNG value should be a dict"
                assert "prevention" in entry.value, "LNG must have prevention field"
                assert "type" in entry.value, "LNG must have type field"
                assert "cause" in entry.value, "LNG must have cause field"
                assert "lesson" in entry.value, "LNG must have lesson field"
        assert lng_found, "No operational LNG entry found in identity file"
