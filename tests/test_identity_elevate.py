"""Tests for identity.elevate — brain $8 LNG → agent contract (AXM/LIM).

Architect rule 2026-11-15: brain.cortex $8 is the ONLY lesson surface.
Behavioral knowledge reaches an identity contract ONLY through this governed
elevation path (dry-run preview → confirm_hash → verified write).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.constants import ARQUX_DIR
from arqux.core.learning._identity_elevate import elevate_lesson_to_identity
from arqux.handlers.identity.elevate import elevate as elevate_handler
from arqux.permissions import (
    ROLE_AUDITOR,
    ROLE_EXECUTOR,
    ROLE_GOVERNOR,
    PermissionContext,
    PermissionDenied,
)

_BRAIN = (
    "$0\n\n"
    "$2: FOCUS\n"
    'FCS:current{what:"tests", priority:"high", survive:"work", status:"current"}\n\n'
    'OBJ:current{goal:"tests pass", success:"green", survive:"work", status:"current"}\n\n'
    "$8: LESSONS\n"
    'LNG:verify_write{type:behavioral, cause:"handler reported ok while artifact was unchanged", '
    'lesson:"After any governed mutation, verify the artifact state actually changed as claimed", '
    'prevention:"Re-read the target section and compare expected vs actual ids", agent:"alfred"}\n'
    'LNG:hard_limit{type:behavioral, cause:"scope creep", '
    'lesson:"Never write outside the declared section", '
    'prevention:"Bound every writer to an explicit selector", agent:"alfred"}\n'
)

_IDENTITY = (
    "$0\nGSIG:IDN:identity|attrs|B|Semantic|Actor identity\n\n"
    "$1: IDENTITY\nIDN:alfred{agent:\"alfred\"}\n\n"
    "$2: AXIOMS\n\n$3: LIMITS\n"
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    (proj / ARQUX_DIR / "identities").mkdir(parents=True)
    (proj / ARQUX_DIR / "brain.cortex").write_text(_BRAIN, encoding="utf-8")
    (proj / ARQUX_DIR / "identities" / "alfred.cortex").write_text(
        _IDENTITY, encoding="utf-8",
    )
    return proj


def _identity_file(project: Path) -> Path:
    return project / ARQUX_DIR / "identities" / "alfred.cortex"


# --- Core: elevate_lesson_to_identity ----------------------------------------


class TestCoreElevation:
    def test_dry_run_returns_proposal_and_hash(self, project: Path) -> None:
        before = _identity_file(project).read_bytes()
        result = elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM", dry_run=True,
        )
        assert result["mode"] == "dry_run"
        proposal = result["proposal"]
        assert proposal["sigil"] == "AXM"
        assert proposal["name"] == "verify_write"
        assert proposal["agent"] == "alfred"
        assert "verify the artifact" in proposal["body"]
        assert result["preview_hash"]
        assert _identity_file(project).read_bytes() == before

    def test_apply_without_confirm_hash_rejected(self, project: Path) -> None:
        result = elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM", dry_run=False,
        )
        assert "error" in result
        assert result["preview_hash"]
        assert "AXM:verify_write" not in _identity_file(project).read_text()

    def test_apply_with_wrong_hash_rejected(self, project: Path) -> None:
        result = elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM",
            dry_run=False, confirm_hash="deadbeef",
        )
        assert "error" in result
        assert "AXM:verify_write" not in _identity_file(project).read_text()

    def test_apply_with_correct_hash_writes_axm(self, project: Path) -> None:
        preview = elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM", dry_run=True,
        )
        result = elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM",
            dry_run=False, confirm_hash=preview["preview_hash"],
        )
        assert result["mode"] == "applied"
        assert result["verified"] is True
        text = _identity_file(project).read_text()
        assert "AXM:verify_write{" in text
        assert 'source_lesson:"verify_write"' in text
        assert 'evidence_ref:"brain:$8/LNG:verify_write"' in text

    def test_apply_limit_writes_lim(self, project: Path) -> None:
        preview = elevate_lesson_to_identity(
            project, "hard_limit", "alfred", "LIMIT", dry_run=True,
        )
        assert preview["proposal"]["sigil"] == "LIM"
        result = elevate_lesson_to_identity(
            project, "hard_limit", "alfred", "LIMIT",
            dry_run=False, confirm_hash=preview["preview_hash"],
        )
        assert result["mode"] == "applied"
        text = _identity_file(project).read_text()
        assert "LIM:hard_limit{" in text

    def test_second_apply_is_idempotent(self, project: Path) -> None:
        preview = elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM", dry_run=True,
        )
        elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM",
            dry_run=False, confirm_hash=preview["preview_hash"],
        )
        second = elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM",
            dry_run=False, confirm_hash=preview["preview_hash"],
        )
        assert second.get("skip") is True
        text = _identity_file(project).read_text()
        assert text.count("AXM:verify_write{") == 1

    def test_wrong_hash_on_applied_is_error_not_skip(self, project: Path) -> None:
        """confirm_hash is validated BEFORE the idempotent skip.

        A wrong hash on an already-applied elevation used to report
        "skip" — silently endorsing an unreviewed approval.
        """
        preview = elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM", dry_run=True,
        )
        elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM",
            dry_run=False, confirm_hash=preview["preview_hash"],
        )
        result = elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM",
            dry_run=False, confirm_hash="deadbeef",
        )
        assert "error" in result
        assert result.get("skip") is not True
        assert "preview approval required" in result["error"]

    def test_missing_hash_on_applied_is_error_not_skip(self, project: Path) -> None:
        """apply with no confirm_hash on an applied lesson must also error."""
        preview = elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM", dry_run=True,
        )
        elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM",
            dry_run=False, confirm_hash=preview["preview_hash"],
        )
        result = elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM", dry_run=False,
        )
        assert "error" in result
        assert result.get("skip") is not True

    def test_lesson_not_found(self, project: Path) -> None:
        result = elevate_lesson_to_identity(
            project, "no_such_lesson", "alfred", "AXIOM", dry_run=True,
        )
        assert result["code"] == "NOT_FOUND"

    def test_invalid_contract_type(self, project: Path) -> None:
        result = elevate_lesson_to_identity(
            project, "verify_write", "alfred", "KNW", dry_run=True,
        )
        assert result["code"] == "INVALID_CONTRACT_TYPE"

    def test_agent_not_found(self, project: Path) -> None:
        result = elevate_lesson_to_identity(
            project, "verify_write", "noagent", "AXIOM", dry_run=True,
        )
        assert result["code"] == "NOT_FOUND"

    def test_lesson_fields_survive_escaping(self, project: Path) -> None:
        """A body containing quotes/newlines must round-trip as valid CORTEX."""
        brain = project / ARQUX_DIR / "brain.cortex"
        brain.write_text(
            _BRAIN + 'LNG:quoted{type:rule, cause:"c", '
            'lesson:"say \\"yes\\" then stop", '
            'prevention:"p", agent:"alfred"}\n',
            encoding="utf-8",
        )
        preview = elevate_lesson_to_identity(
            project, "quoted", "alfred", "AXIOM", dry_run=True,
        )
        result = elevate_lesson_to_identity(
            project, "quoted", "alfred", "AXIOM",
            dry_run=False, confirm_hash=preview["preview_hash"],
        )
        assert result["mode"] == "applied"
        # The written file must still parse as CORTEX.
        from arqux.cortex.reader import cortex_to_dict

        doc = cortex_to_dict(_identity_file(project).read_text())
        names = [
            e["name"]
            for s in doc["sections"]
            for e in s.get("entries", [])
            if e.get("sigil") == "AXM"
        ]
        assert "quoted" in names

    def test_source_lesson_not_deleted(self, project: Path) -> None:
        """Elevation must not remove the source LNG from brain $8."""
        preview = elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM", dry_run=True,
        )
        elevate_lesson_to_identity(
            project, "verify_write", "alfred", "AXIOM",
            dry_run=False, confirm_hash=preview["preview_hash"],
        )
        brain = (project / ARQUX_DIR / "brain.cortex").read_text()
        assert "LNG:verify_write{" in brain


# --- Handler: identity.elevate -----------------------------------------------


class TestHandler:
    def test_handler_dry_run(self, project: Path) -> None:
        result = elevate_handler(
            lesson_id="verify_write", agent="alfred",
            contract_type="AXIOM", path=str(project),
        )
        assert result.profile == "OUT-WORK"
        assert result.fields["mode"] == "dry_run"
        assert result.fields["preview_hash"]

    def test_handler_apply_round_trip(self, project: Path) -> None:
        preview = elevate_handler(
            lesson_id="verify_write", agent="alfred",
            contract_type="AXIOM", path=str(project),
        )
        applied = elevate_handler(
            lesson_id="verify_write", agent="alfred",
            contract_type="AXIOM", path=str(project),
            apply=True, confirm_hash=preview.fields["preview_hash"],
        )
        assert applied.profile == "OUT-WORK"
        assert applied.fields["mode"] == "applied"
        assert applied.fields["verified"] is True

    def test_handler_apply_needs_hash(self, project: Path) -> None:
        result = elevate_handler(
            lesson_id="verify_write", agent="alfred",
            contract_type="AXIOM", path=str(project), apply=True,
        )
        assert result.profile == "OUT-ERROR"

    def test_handler_error_propagates(self, project: Path) -> None:
        result = elevate_handler(
            lesson_id="missing", agent="alfred",
            contract_type="AXIOM", path=str(project),
        )
        assert result.profile == "OUT-ERROR"
        assert result.fields.get("code") == "NOT_FOUND"


# --- Permissions -------------------------------------------------------------


class TestPermissions:
    """identity.elevate is CONDITIONAL_MUTATING: auditors preview, never apply."""

    def test_auditor_can_preview(self) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        ctx.check("identity.elevate")
        ctx.check("identity.elevate", apply=False)
        assert ctx.can("identity.elevate") is True

    def test_auditor_cannot_apply(self) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        with pytest.raises(PermissionDenied, match="mutating invocation"):
            ctx.check("identity.elevate", apply=True)
        assert ctx.can("identity.elevate", apply=True) is False

    def test_executor_can_apply(self) -> None:
        ctx = PermissionContext(agent_id="jarvis", role=ROLE_EXECUTOR)
        ctx.check("identity.elevate", apply=True)

    def test_governor_can_apply(self) -> None:
        ctx = PermissionContext(agent_id="alfred", role=ROLE_GOVERNOR)
        ctx.check("identity.elevate", apply=True)


# --- IdentityManager writer hardening ----------------------------------------


class TestWriterHardening:
    """elevate_to_identity: atomic write + dup guard + post-write verify."""

    def test_duplicate_injection_prevented(self, project: Path) -> None:
        from arqux.identity import IdentityManager

        im = IdentityManager(
            identities_dir=project / ARQUX_DIR / "identities"
        )
        first = im.elevate_to_identity(
            agent="alfred", lesson_id="dup_check",
            contract_type="AXIOM", pattern="p",
        )
        assert first["written"] is True
        second = im.elevate_to_identity(
            agent="alfred", lesson_id="dup_check",
            contract_type="AXIOM", pattern="p",
        )
        assert second["written"] is False
        assert second["already_present"] is True
        text = _identity_file(project).read_text()
        assert text.count("AXM:dup_check{") == 1

    def test_backup_created(self, project: Path) -> None:
        from arqux.identity import IdentityManager

        im = IdentityManager(
            identities_dir=project / ARQUX_DIR / "identities"
        )
        im.elevate_to_identity(
            agent="alfred", lesson_id="bak_check",
            contract_type="AXIOM", pattern="p",
        )
        assert (project / ARQUX_DIR / "identities" / "alfred.cortex.bak").exists()

    def test_body_escaping_produces_valid_entry(self, project: Path) -> None:
        from arqux.cortex.reader import cortex_to_dict
        from arqux.identity import IdentityManager

        im = IdentityManager(
            identities_dir=project / ARQUX_DIR / "identities"
        )
        im.elevate_to_identity(
            agent="alfred", lesson_id="escaped",
            contract_type="AXIOM",
            pattern='body with "quotes" and\nnewline',
        )
        doc = cortex_to_dict(_identity_file(project).read_text())
        bodies = [
            (e.get("attrs") or {}).get("body", "")
            for s in doc["sections"]
            for e in s.get("entries", [])
            if e.get("sigil") == "AXM" and e.get("name") == "escaped"
        ]
        assert bodies and "quotes" in bodies[0]
