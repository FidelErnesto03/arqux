"""T-027: governed issue.* handlers + brain-validator scoping.

Covers:
- issue.create / issue.list / issue.read / issue.update lifecycle with
  PULSE traceability
- Separation of responsibilities: status=verified requires audit_ref
  (the validator profile is the auditor — Heimdall)
- Brain-validator scoping: brain-level validation (E024/E032) no longer
  fires on non-brain .cortex files (issue files, etc.)
"""

from __future__ import annotations

from pathlib import Path

from arqux.core.state import crud_update
from arqux.handlers.issue import create_issue, list_issues, read_issue, update_issue
from arqux.permissions import PermissionContext

OUT_ERROR = "OUT-ERROR"
OUT_WORK = "OUT-WORK"

GOV = PermissionContext(agent_id="alfred", role="governor")


def _is_error(out) -> bool:
    return out.profile == OUT_ERROR


# ---------------------------------------------------------------------------
# issue.create
# ---------------------------------------------------------------------------


def test_issue_create_writes_file_and_pulse(arqux_env) -> None:
    out = create_issue("high", "Selector underscore destroys entries", path=str(arqux_env.proj_root), ctx=GOV)
    assert not _is_error(out), out
    issue_file = Path(out.fields["file"])
    assert issue_file.exists()
    text = issue_file.read_text(encoding="utf-8")
    assert "# Severity: high | Status: open" in text
    assert "## PROBLEM" in text
    assert out.fields["event_id"]  # PULSE event recorded


def test_issue_create_invalid_severity_rejected(arqux_env) -> None:
    out = create_issue("catastrophic", "bad severity", path=str(arqux_env.proj_root), ctx=GOV)
    assert _is_error(out)
    assert "INVALID_ARGS" in out.message or "severity" in out.message


def test_issue_create_empty_desc_rejected(arqux_env) -> None:
    out = create_issue("low", "   ", path=str(arqux_env.proj_root), ctx=GOV)
    assert _is_error(out)


def test_issue_create_dedupes_filename(arqux_env) -> None:
    a = create_issue("low", "Same description twice", path=str(arqux_env.proj_root), ctx=GOV)
    b = create_issue("low", "Same description twice", path=str(arqux_env.proj_root), ctx=GOV)
    assert not _is_error(a) and not _is_error(b)
    assert a.fields["file"] != b.fields["file"]


# ---------------------------------------------------------------------------
# issue.list / issue.read
# ---------------------------------------------------------------------------


def test_issue_list_and_filter(arqux_env) -> None:
    create_issue("low", "Issue alpha", path=str(arqux_env.proj_root), ctx=GOV)
    create_issue("high", "Issue beta", path=str(arqux_env.proj_root), ctx=GOV)

    out = list_issues(path=str(arqux_env.proj_root), ctx=GOV)
    assert not _is_error(out)
    assert out.fields["total"] == 2

    out_open = list_issues(status="open", path=str(arqux_env.proj_root), ctx=GOV)
    assert out_open.fields["total"] == 2

    out_triaged = list_issues(status="triaged", path=str(arqux_env.proj_root), ctx=GOV)
    assert out_triaged.fields["total"] == 0


def test_issue_read_returns_content(arqux_env) -> None:
    created = create_issue("medium", "Readable issue", path=str(arqux_env.proj_root), ctx=GOV)
    out = read_issue(created.fields["issue_id"], path=str(arqux_env.proj_root), ctx=GOV)
    assert not _is_error(out)
    assert "Readable issue" in out.fields["content"]


def test_issue_read_unknown_id(arqux_env) -> None:
    out = read_issue("2099-01-01-nope", path=str(arqux_env.proj_root), ctx=GOV)
    assert _is_error(out)


# ---------------------------------------------------------------------------
# issue.update — lifecycle + auditor endorsement
# ---------------------------------------------------------------------------


def test_issue_update_status_transitions(arqux_env) -> None:
    created = create_issue("medium", "Lifecycle issue", path=str(arqux_env.proj_root), ctx=GOV)
    issue_id = created.fields["issue_id"]

    out = update_issue(issue_id, status="triaged", path=str(arqux_env.proj_root), ctx=GOV)
    assert not _is_error(out), out
    assert out.fields["previous_status"] == "open"

    out = update_issue(issue_id, status="fixed", note="fix applied", path=str(arqux_env.proj_root), ctx=GOV)
    assert not _is_error(out), out

    text = Path(created.fields["file"]).read_text(encoding="utf-8")
    assert "# Severity: medium | Status: fixed" in text
    assert "## UPDATE" in text and "fix applied" in text


def test_issue_update_verified_requires_audit_ref(arqux_env) -> None:
    """Separation of responsibilities: verified needs the auditor's endorsement."""
    created = create_issue("high", "Endorsement issue", path=str(arqux_env.proj_root), ctx=GOV)
    issue_id = created.fields["issue_id"]

    out = update_issue(issue_id, status="verified", path=str(arqux_env.proj_root), ctx=GOV)
    assert _is_error(out)
    assert "audit_ref" in out.message

    # Status unchanged after the rejected transition.
    text = Path(created.fields["file"]).read_text(encoding="utf-8")
    assert "Status: open" in text


def test_issue_update_verified_with_audit_ref(arqux_env) -> None:
    """verified is accepted when audit_ref resolves to a real PULSE event."""
    from arqux.pulse import append_pulse_to_brain, next_pulse_event_id

    root = arqux_env.proj_root / ".arqux"
    event_id = next_pulse_event_id(root)
    append_pulse_to_brain(
        root, event_id=event_id, task_id="-", kind="note",
        agent="heimdall", payload="audit verdict: APPROVED",
    )

    created = create_issue("high", "Endorsed issue", path=str(arqux_env.proj_root), ctx=GOV)
    issue_id = created.fields["issue_id"]

    out = update_issue(
        issue_id, status="verified", audit_ref=event_id,
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    assert not _is_error(out), out
    assert out.fields["audit_ref"] == event_id

    text = Path(created.fields["file"]).read_text(encoding="utf-8")
    assert "Status: verified" in text


def test_issue_update_verified_with_unresolvable_audit_ref_rejected(arqux_env) -> None:
    """The endorsement must point at a real PULSE event (audit F-1)."""
    created = create_issue("high", "Ghost endorsement", path=str(arqux_env.proj_root), ctx=GOV)

    out = update_issue(
        created.fields["issue_id"], status="verified", audit_ref="E-9999",
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    assert _is_error(out)
    assert "does not resolve" in out.message
    text = Path(created.fields["file"]).read_text(encoding="utf-8")
    assert "Status: open" in text


def test_issue_update_invalid_status_rejected(arqux_env) -> None:
    created = create_issue("low", "Invalid status issue", path=str(arqux_env.proj_root), ctx=GOV)
    out = update_issue(
        created.fields["issue_id"], status="closed",
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    assert _is_error(out)


def test_issue_update_unknown_issue(arqux_env) -> None:
    out = update_issue("2099-01-01-ghost", status="triaged", path=str(arqux_env.proj_root), ctx=GOV)
    assert _is_error(out)


# ---------------------------------------------------------------------------
# Brain-validator scoping (T-027): E024/E032 no longer fire on non-brains
# ---------------------------------------------------------------------------


def _write_issue_like_cortex(path: Path) -> None:
    """A non-brain .cortex with brain-incomplete critical sigils."""
    path.write_text(
        "$0\n"
        "\n"
        "# -- ISSUE GLOSSARY --\n"
        "\n"
        "\n"
        "$1: ISSUE RECORD\n"
        "\n"
        'IDN:issue{severity:"high", status:"open"}\n'
        "\n"
        'WRK:problem{desc:"incomplete critical sigil on purpose"}\n'
        "\n",
        encoding="utf-8",
    )


def test_crud_update_on_non_brain_skips_brain_validation(arqux_env, tmp_path) -> None:
    """The brain validator must not block mutations on non-brain artifacts."""
    target = tmp_path / "2026-09-30-some-issue.issue.cortex"
    _write_issue_like_cortex(target)

    result = crud_update(
        str(target), "$1/IDN:issue",
        set_={"status": "triaged"},
    )
    assert "error" not in result, result
    assert "E024" not in str(result.get("diagnostics", ""))


def test_crud_update_on_brain_still_validates(arqux_env, tmp_path) -> None:
    """Brain files keep brain-level validation (scoped, not removed)."""
    brain = tmp_path / "brain.cortex"
    brain.write_text(
        "$0\n"
        "\n"
        "# -- BRAIN GLOSSARY --\n"
        "\n"
        "\n"
        "$1: IDENTITY\n"
        "\n"
        'WRK:current{fcs:"x"}\n'
        "\n",
        encoding="utf-8",
    )

    result = crud_update(str(brain), "$1/WRK:current", set_={"fcs": "y"})
    # Brain validation runs: incomplete critical sigils are flagged (or the
    # mutation is allowed only with force). Either way it must NOT be a
    # silent unvalidated write.
    has_validation_error = "error" in result or result.get("diagnostics")
    assert has_validation_error or "Validation failed" in str(result), result
