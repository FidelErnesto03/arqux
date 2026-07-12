"""Tests for codec-cortex 0.5.0 template validation — BC-5 fix.

Validates that every .cortex template shipped with ArqUX passes the strict
schema validation introduced in codec-cortex 0.5.0:

  - W001_MISSING_FIELDS: every entry must have `name` attr
  - W002_INVALID_STATUS: status must be canonical or declared in $0
  - E032_CRITICAL_SIGIL_INCOMPLETE: critical sigils (KNW, LIM, LNG, AXM,
    DESC) must have all required fields
  - E023_LEVEL1_LIVE_STATE: identity/skill files (level 1) must NOT
    contain live-state sigils (FCS, WRK, runtime-LNG)
  - I001_UNDECLARED_SIGIL / I002_UNDECLARED_TYPE: sigils/types not in $0
    are auto-added with needs_review (info, not error)

This test suite is part of the ArqUX × codec-cortex 0.5.0 compatibility
patch. It MUST pass before publishing ArqUX with codec-cortex 0.5.0+.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.handlers.cortex import verify_handler
from arqux.permissions import PermissionContext

# --- Fixtures ---------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = REPO_ROOT / "src" / "arqux" / "templates"
IDENTITIES_DIR = REPO_ROOT / "src" / "arqux" / "identities"


ALL_TEMPLATES = [
    "src/arqux/templates/meta-brain.cortex",
    "src/arqux/templates/learn-policies.cortex",
    # NOTE: brain.cortex is a markdown template (YAML frontmatter + prose),
    # not a real .cortex file. verify_handler returns valid=None for it,
    # which is expected. We skip it from strict validation.
    # "src/arqux/templates/brain.cortex",
    "src/arqux/UPGRADE.cortex",
]

ALL_IDENTITIES = [
    "src/arqux/identities/jarvis.cortex",
    "src/arqux/identities/governor.cortex",
    "src/arqux/identities/auditor.cortex",
    "src/arqux/identities/executor.cortex",
    "src/arqux/identities/alfred.cortex",
    "src/arqux/identities/heimdall.cortex",
    "src/arqux/identities/seshat.cortex",
]


@pytest.fixture
def governor_ctx() -> PermissionContext:
    return PermissionContext(agent_id="test-governor", role="governor")


def _verify_template(template_rel: str, governor_ctx: PermissionContext):
    """Run verify_handler on a template and return the result."""
    template_path = REPO_ROOT / template_rel
    if not template_path.exists():
        pytest.skip(f"Template not found: {template_path}")
    return verify_handler(path=str(template_path), ctx=governor_ctx)


# --- Tests: every template must be valid ------------------------------------

@pytest.mark.parametrize("template_rel", ALL_TEMPLATES)
def test_template_valid(template_rel: str, governor_ctx: PermissionContext) -> None:
    """Every .cortex template MUST be valid=True per codec-cortex 0.5.0."""
    result = _verify_template(template_rel, governor_ctx)
    fields = result.fields or {}
    valid = fields.get("valid")
    diagnostics = fields.get("diagnostics", []) or []
    error_diags = [d for d in diagnostics if d.startswith("[E")]
    assert valid is True, (
        f"{template_rel} is NOT valid per codec-cortex 0.5.0.\n"
        f"  valid={valid}\n"
        f"  sections={fields.get('sections')}\n"
        f"  entries={fields.get('entries')}\n"
        f"  error_diagnostics={error_diags}\n"
        f"  all_diagnostics={diagnostics}"
    )
    # No error-severity diagnostics allowed (E*)
    assert not error_diags, (
        f"{template_rel} has {len(error_diags)} error-severity diagnostics:\n"
        + "\n".join(f"  - {d}" for d in error_diags)
    )


@pytest.mark.parametrize("template_rel", ALL_IDENTITIES)
def test_identity_valid(template_rel: str, governor_ctx: PermissionContext) -> None:
    """Every identity .cortex MUST be valid=True per codec-cortex 0.5.0.

    Identities are level-1 files (skill/identity contracts). They MUST NOT
    contain live-state sigils (FCS, WRK, runtime-LNG) per E023.
    """
    result = _verify_template(template_rel, governor_ctx)
    fields = result.fields or {}
    valid = fields.get("valid")
    diagnostics = fields.get("diagnostics", []) or []
    error_diags = [d for d in diagnostics if d.startswith("[E")]
    assert valid is True, (
        f"{template_rel} is NOT valid per codec-cortex 0.5.0.\n"
        f"  error_diagnostics={error_diags}"
    )
    assert not error_diags, (
        f"{template_rel} has {len(error_diags)} error-severity diagnostics:\n"
        + "\n".join(f"  - {d}" for d in error_diags)
    )


# --- Tests: no E032 critical sigil incomplete -------------------------------

@pytest.mark.parametrize("template_rel", ALL_TEMPLATES + ALL_IDENTITIES)
def test_no_e032_critical_sigil_incomplete(
    template_rel: str, governor_ctx: PermissionContext
) -> None:
    """No E032_CRITICAL_SIGIL_INCOMPLETE diagnostics allowed.

    Critical sigils (KNW, LIM, LNG, AXM, DESC) must have all required
    fields populated.
    """
    result = _verify_template(template_rel, governor_ctx)
    diagnostics = (result.fields or {}).get("diagnostics", []) or []
    e032_diags = [d for d in diagnostics if "E032" in d]
    assert not e032_diags, (
        f"{template_rel} has {len(e032_diags)} E032 diagnostics:\n"
        + "\n".join(f"  - {d}" for d in e032_diags)
    )


# --- Tests: no E023 level-1 live state --------------------------------------

@pytest.mark.parametrize("template_rel", ALL_IDENTITIES)
def test_no_e023_level1_live_state(
    template_rel: str, governor_ctx: PermissionContext
) -> None:
    """No E023_LEVEL1_LIVE_STATE diagnostics allowed in identity files.

    Identity files (level 1) MUST NOT contain live-state sigils
    (FCS, LNG, WRK) — only contracts and examples.
    """
    result = _verify_template(template_rel, governor_ctx)
    diagnostics = (result.fields or {}).get("diagnostics", []) or []
    e023_diags = [d for d in diagnostics if "E023" in d]
    assert not e023_diags, (
        f"{template_rel} has {len(e023_diags)} E023 diagnostics:\n"
        + "\n".join(f"  - {d}" for d in e023_diags)
    )


# --- Tests: no W001 missing fields ------------------------------------------

@pytest.mark.parametrize("template_rel", ALL_TEMPLATES + ALL_IDENTITIES)
def test_no_w001_missing_fields(
    template_rel: str, governor_ctx: PermissionContext
) -> None:
    """No W001_MISSING_FIELDS diagnostics allowed.

    Every entry must have `name` as an explicit attr, plus all
    required fields for its sigil.
    """
    result = _verify_template(template_rel, governor_ctx)
    diagnostics = (result.fields or {}).get("diagnostics", []) or []
    w001_diags = [d for d in diagnostics if "W001" in d]
    assert not w001_diags, (
        f"{template_rel} has {len(w001_diags)} W001 diagnostics:\n"
        + "\n".join(f"  - {d}" for d in w001_diags)
    )


# --- Tests: no W002 invalid status ------------------------------------------

@pytest.mark.parametrize("template_rel", ALL_TEMPLATES + ALL_IDENTITIES)
def test_no_w002_invalid_status(
    template_rel: str, governor_ctx: PermissionContext
) -> None:
    """No W002_INVALID_STATUS diagnostics allowed.

    All status values must be canonical (blocked, current, deprecated,
    done, experimental, future, planned, specification) OR declared
    in $0 via # status: [...] comment.
    """
    result = _verify_template(template_rel, governor_ctx)
    diagnostics = (result.fields or {}).get("diagnostics", []) or []
    w002_diags = [d for d in diagnostics if "W002" in d]
    assert not w002_diags, (
        f"{template_rel} has {len(w002_diags)} W002 diagnostics:\n"
        + "\n".join(f"  - {d}" for d in w002_diags)
    )


# --- Tests: brain.cortex end-to-end after task.complete ---------------------

def test_brain_after_task_complete_no_w002(
    tmp_path: Path, governor_ctx: PermissionContext
) -> None:
    """End-to-end test: brain.cortex after task.complete must not have W002.

    Validates BC-2 fix: tasks_active should have status:"current",
    tasks_done should have status:"done" (NOT "active").
    """
    from arqux.handlers.cycle import create_cycle, mature_cycle
    from arqux.handlers.project import init_project
    from arqux.handlers.task import claim_task, complete_task, create_task
    from arqux.handlers.workspace import init_workspace
    from arqux.state import find_project_root

    # Init workspace + project + cycle + task + complete
    ws = tmp_path / "ws"
    ws.mkdir()
    init_workspace(path=str(ws / ".arqux"), ctx=governor_ctx)
    init_project(name="test-bc2", path=str(ws / ".arqux"), ctx=governor_ctx)
    root = find_project_root(start=str(ws / ".arqux"))
    assert root is not None, "project root not found"
    create_cycle(name="c1", path=str(ws / ".arqux"), ctx=governor_ctx)
    mature_cycle(cycle_id="CYCLE-01", path=str(ws / ".arqux"), ctx=governor_ctx)
    create_task(obj="test BC-2 fix", path=str(ws / ".arqux"), ctx=governor_ctx)
    claim_task(task_id="T-001", path=str(ws / ".arqux"), ctx=governor_ctx)
    complete_task(task_id="T-001", path=str(ws / ".arqux"), ctx=governor_ctx)

    # Verify brain.cortex
    brain_path = root / "brain.cortex"
    assert brain_path.exists(), f"brain.cortex not found at {brain_path}"
    result = verify_handler(path=str(brain_path), ctx=governor_ctx)
    diagnostics = (result.fields or {}).get("diagnostics", []) or []
    w002_diags = [d for d in diagnostics if "W002" in d]
    assert not w002_diags, (
        "brain.cortex has W002 diagnostics after task.complete (BC-2 not fixed):\n"
        + "\n".join(f"  - {d}" for d in w002_diags)
    )


# --- Tests: protocol.release clears env vars (BC-7) -------------------------

def test_protocol_release_clears_env_vars(tmp_path: Path, governor_ctx: PermissionContext) -> None:
    """BC-7 fix: protocol.release must clear ARQUX_AGENT_ID/ROLE."""
    import os

    from arqux.constants import PRODUCT_NAME_UPPER
    from arqux.handlers.protocol import adopt, release
    from arqux.handlers.workspace import init_workspace

    init_workspace(path=str(tmp_path / ".arqux"), ctx=governor_ctx)
    adopt(agent_id="test-agent", role="executor")

    assert os.environ.get(f"{PRODUCT_NAME_UPPER}_AGENT_ID") == "test-agent"

    release(agent_id="test-agent")

    assert os.environ.get(f"{PRODUCT_NAME_UPPER}_AGENT_ID") is None, (
        "BC-7 NOT fixed: ARQUX_AGENT_ID still set after release()"
    )
    assert os.environ.get(f"{PRODUCT_NAME_UPPER}_AGENT_ROLE") is None, (
        "BC-7 NOT fixed: ARQUX_AGENT_ROLE still set after release()"
    )


# --- Tests: find_project_root no nesting (BC-6) -----------------------------

def test_find_project_root_no_nesting(tmp_path: Path, governor_ctx: PermissionContext) -> None:
    """BC-6 fix: find_project_root(start='.../.arqux') must NOT return '.../.arqux/.arqux'.

    NOTE: This test verifies the BC-6 fix in isolation. The fix adds a check:
    if `cursor.name == target_dir and (cursor / BRAIN_CORTEX).exists()`,
    return cursor directly (no nesting). We test this by creating a brain.cortex
    directly inside a `.arqux/` directory and verifying that find_project_root
    returns that directory, not a nested `.arqux/.arqux`.
    """
    from arqux.state import find_project_root

    # Simulate a .arqux/ directory that contains brain.cortex directly
    # (the canonical layout that BC-6 aims to support).
    arqux_dir = tmp_path / ".arqux"
    arqux_dir.mkdir()
    (arqux_dir / "brain.cortex").write_text(
        "$0\n\n$1: TEST\nIDN:test{name:\"test\", status:\"current\"}\n",
        encoding="utf-8",
    )

    # When called with start=tmp_path/.arqux, must return tmp_path/.arqux
    # (NOT tmp_path/.arqux/.arqux)
    root = find_project_root(start=str(arqux_dir))
    assert root is not None, "BC-6: find_project_root returned None for valid .arqux"
    root_str = str(root)
    assert ".arqux/.arqux" not in root_str, (
        f"BC-6 NOT fixed: find_project_root returned nested path: {root_str}"
    )
    assert root_str.endswith(".arqux"), (
        f"BC-6: unexpected root path: {root_str}"
    )
