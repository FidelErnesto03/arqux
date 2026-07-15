"""Blueprint integration tests using the arqux_env fixture.

Tests cover the complete lifecycle, review, manage, and edge-case
paths by calling handlers directly (not through the CLI).
"""

from __future__ import annotations

import re
from pathlib import Path

from arqux.handlers.blueprint._read import list_blueprints, read_blueprint
from arqux.handlers.blueprint.lifecycle import (
    assign_blueprint,
    claim_blueprint,
    create_blueprint,
    mature_blueprint,
    ready_blueprint,
)
# define_blueprint was removed in ISS-002 — kept as thin wrapper for legacy tests
from arqux.handlers.blueprint import synthesize_blueprint


def define_blueprint(bp_id, **kwargs):
    """Legacy wrapper — define_blueprint removed in ISS-002.
    Converts old named params to synthesize content format."""
    sections = kwargs.pop("sections", None) or {}
    parts = {}
    if kwargs.get("pre"):
        parts["3"] = "\n".join(f"- [ ] {p}" for p in kwargs["pre"])
    if kwargs.get("scope"):
        parts["6"] = f"**Dentro:** {kwargs['scope']}"
    if kwargs.get("exclusions"):
        parts["6"] = (parts.get("6", "") + f"\n**Fuera:** {kwargs['exclusions']}").strip()
    if kwargs.get("acceptance_criteria"):
        acs = kwargs["acceptance_criteria"]
        parts["12"] = "\n".join(f"- [ ] **AC-{i+1:02d}:** {ac}" for i, ac in enumerate(acs))
    if kwargs.get("mandatory_rules"):
        parts["7"] = "\n".join(f"{i+1}. {r}" for i, r in enumerate(kwargs["mandatory_rules"]))
    for sid, body in sections.items():
        clean_sid = sid.replace("BLP:", "")
        parts[clean_sid] = body
    content = "\n".join(f"${k}:{{{v}}}" for k, v in parts.items()) if parts else "$1:{placeholder}"
    path = kwargs.get("path")
    ctx = kwargs.get("ctx")
    return synthesize_blueprint(bp_id, content=content, path=path, ctx=ctx)

from arqux.handlers.blueprint.manage import gate_blueprint, update_blueprint
from arqux.handlers.blueprint.review import (
    ac_blueprint,
    approve_blueprint,
    block_for_architect,
    cancel_blueprint,
    complete_blueprint,
    fail_blueprint,
    re_delegate_blueprint,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bp_path(proj_root: Path, bp_id: str) -> Path:
    """Resolve the blueprint file path for a given bp_id."""
    cycles_dir = proj_root / ".arqux" / "cycles"
    for cdir in cycles_dir.iterdir():
        candidate = cdir / "blueprints" / f"{bp_id}.md"
        if candidate.exists():
            return candidate
    raise AssertionError(f"blueprint {bp_id} not found under {cycles_dir}")


def _read_fm(proj_root: Path, bp_id: str) -> dict:
    """Parse the frontmatter of a blueprint file."""
    text = _bp_path(proj_root, bp_id).read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, "malformed frontmatter"
    fm: dict = {}
    for line in parts[1].strip().splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip('"')
        if val == "true":
            val = True
        elif val == "false":
            val = False
        fm[key] = val
    return fm


def _set_fm(proj_root: Path, bp_id: str, key: str, value) -> None:
    """Set a single frontmatter field in a blueprint file."""
    bp_file = _bp_path(proj_root, bp_id)
    text = bp_file.read_text(encoding="utf-8")
    pattern = rf"^{re.escape(key)}:\s*.+$"
    replacement = f"{key}: {str(value).lower()}" if isinstance(value, bool) else f'{key}: "{value}"'

    if re.search(pattern, text, re.MULTILINE):
        text = re.sub(pattern, replacement, text, count=1, flags=re.MULTILINE)
    else:
        parts = text.split("---", 2)
        assert len(parts) >= 3
        parts[1] = parts[1].rstrip() + f"\n{replacement}"
        text = "---".join(parts)
    bp_file.write_text(text, encoding="utf-8")


def _gates_all_true(proj_root: Path, bp_id: str) -> None:
    """Set all quality gates to true in frontmatter (including learning)."""
    gates = [
        "has_clear_objective",
        "has_verifiable_preconditions",
        "has_scope_and_exclusions",
        "has_acceptance_criteria",
        "has_work_procedure",
        "has_required_validations",
        "has_learning_recorded",
    ]
    for gate in gates:
        _set_fm(proj_root, bp_id, gate, True)


def _clear_sections(proj_root: Path, bp_id: str) -> None:
    """Remove template placeholder content from §13 and §14.

    The default BLP template ships with validation rows and unchecked
    task items that block ``complete_blueprint``.
    """
    update_blueprint(bp_id, section="13", content=" ", path=str(proj_root))
    update_blueprint(bp_id, section="14", content=" ", path=str(proj_root))


# ---------------------------------------------------------------------------
# Lifecycle tests
# ---------------------------------------------------------------------------


def test_create_blueprint_draft(arqux_env) -> None:
    """Verify a newly created BLP exists as a file with status: draft."""
    bp_file = _bp_path(arqux_env.proj_root, arqux_env.bp_id)
    assert bp_file.exists(), f"{bp_file} should exist"
    fm = _read_fm(arqux_env.proj_root, arqux_env.bp_id)
    assert fm.get("status") == "draft", f"expected draft, got {fm.get('status')}"
    assert fm.get("blueprint_id") == arqux_env.bp_id


def test_define_blueprint(arqux_env) -> None:
    """Define a blueprint — uses synthesize wrapper (ISS-002)."""
    result = define_blueprint(
        arqux_env.bp_id,
        pre=["precondition one"],
        scope="integration test scope",
        path=str(arqux_env.proj_root),
        ctx=arqux_env.gov_ctx,
    )
    assert "blueprint.synthesize ok" in result.to_text()
    fm = _read_fm(arqux_env.proj_root, arqux_env.bp_id)
    assert fm.get("status") in ("draft",), f"expected draft, got {fm.get('status')}"


def test_mature_blueprint(arqux_env) -> None:
    """Mature a BLP and approve gates, then verify status."""
    define_blueprint(arqux_env.bp_id, scope="x", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    mature_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    fm = _read_fm(arqux_env.proj_root, arqux_env.bp_id)
    assert fm.get("status") == "maturing", f"expected maturing, got {fm.get('status')}"
    result = gate_blueprint(arqux_env.bp_id, gate="has_clear_objective", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    assert "blueprint.gate ok" in result.to_text(), result.to_text()


def test_ready_blueprint(arqux_env) -> None:
    """Gate all and ready — verify status=ready."""
    define_blueprint(arqux_env.bp_id, scope="x", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    mature_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    gate_blueprint(arqux_env.bp_id, gate="all", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    _gates_all_true(arqux_env.proj_root, arqux_env.bp_id)
    result = ready_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    assert "blueprint.ready ok" in result.to_text(), result.to_text()
    fm = _read_fm(arqux_env.proj_root, arqux_env.bp_id)
    assert fm.get("status") == "ready"


def test_complete_blueprint(arqux_env) -> None:
    """Full path through claim and complete — verify status=review."""
    define_blueprint(arqux_env.bp_id, scope="x", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    mature_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    gate_blueprint(arqux_env.bp_id, gate="all", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    _gates_all_true(arqux_env.proj_root, arqux_env.bp_id)
    ready_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    assign_blueprint(arqux_env.bp_id, executor="test-executor", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    claim_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    _clear_sections(arqux_env.proj_root, arqux_env.bp_id)
    result = complete_blueprint(arqux_env.bp_id, evidence="all done", path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert "blueprint.complete ok" in result.to_text(), result.to_text()
    fm = _read_fm(arqux_env.proj_root, arqux_env.bp_id)
    assert fm.get("status") == "review"


def test_fail_blueprint(arqux_env) -> None:
    """Fail a BLP — verify status=blocked."""
    result = fail_blueprint(arqux_env.bp_id, reason="unexpected obstacle", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    assert "blueprint.fail ok" in result.to_text(), result.to_text()
    fm = _read_fm(arqux_env.proj_root, arqux_env.bp_id)
    assert fm.get("status") == "blocked"
    assert "unexpected obstacle" in str(fm.get("blocked_reason", ""))


# ---------------------------------------------------------------------------
# Review tests
# ---------------------------------------------------------------------------


def test_ac_verify(arqux_env) -> None:
    """Verify a single AC passes."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    define_blueprint(bp, acceptance_criteria=["first criterion"], path=str(proj), ctx=arqux_env.gov_ctx)
    mature_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    gate_blueprint(bp, gate="all", path=str(proj), ctx=arqux_env.gov_ctx)
    _gates_all_true(proj, bp)
    ready_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assign_blueprint(bp, executor="test-executor", path=str(proj), ctx=arqux_env.gov_ctx)
    claim_blueprint(bp, path=str(proj), ctx=arqux_env.exec_ctx)
    _clear_sections(proj, bp)
    complete_blueprint(bp, evidence="done", path=str(proj), ctx=arqux_env.exec_ctx)
    result = ac_blueprint(bp, "AC-01", "verified", evidence="looks good", path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.ac ok" in result.to_text(), result.to_text()
    assert "verified" in result.to_text()


def test_ac_fail(arqux_env) -> None:
    """AC failure triggers auto re-delegate — verify loop increments."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    define_blueprint(bp, acceptance_criteria=["first criterion"], path=str(proj), ctx=arqux_env.gov_ctx)
    mature_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    gate_blueprint(bp, gate="all", path=str(proj), ctx=arqux_env.gov_ctx)
    _gates_all_true(proj, bp)
    ready_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assign_blueprint(bp, executor="test-executor", path=str(proj), ctx=arqux_env.gov_ctx)
    claim_blueprint(bp, path=str(proj), ctx=arqux_env.exec_ctx)
    _clear_sections(proj, bp)
    complete_blueprint(bp, evidence="done", path=str(proj), ctx=arqux_env.exec_ctx)
    result = ac_blueprint(bp, "AC-01", "failed", reason="not met", path=str(proj), ctx=arqux_env.gov_ctx)
    assert "re_delegate" in result.to_text() or "failed" in result.to_text()
    fm = _read_fm(proj, bp)
    assert fm.get("status") == "in_progress"


def test_approve_blueprint(arqux_env) -> None:
    """Full lifecycle: create→define→mature→gate→ready→assign→claim→complete→ac→approve."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    define_blueprint(bp, acceptance_criteria=["main AC"], path=str(proj), ctx=arqux_env.gov_ctx)
    mature_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    gate_blueprint(bp, gate="all", path=str(proj), ctx=arqux_env.gov_ctx)
    _gates_all_true(proj, bp)
    ready_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assign_blueprint(bp, executor="test-executor", path=str(proj), ctx=arqux_env.gov_ctx)
    claim_blueprint(bp, path=str(proj), ctx=arqux_env.exec_ctx)
    _clear_sections(proj, bp)
    complete_blueprint(bp, evidence="done", path=str(proj), ctx=arqux_env.exec_ctx)
    ac_blueprint(bp, "AC-01", "verified", evidence="meets spec", path=str(proj), ctx=arqux_env.gov_ctx)
    # Record learning so approve does not reject on LEARNING_GATE
    identity_dir = arqux_env.ws_root / ".arqux" / "identities"
    identity_dir.mkdir(parents=True, exist_ok=True)
    (identity_dir / "test.cortex").write_text(
        f'LNG:{bp.lower()}{{type:"process", lesson:"integration test"}}\n',
        encoding="utf-8",
    )
    result = approve_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.approve ok" in result.to_text(), result.to_text()
    fm = _read_fm(proj, bp)
    assert fm.get("status") == "done"


def test_re_delegate(arqux_env) -> None:
    """Re-delegate resets the BLP from review to in_progress with incremented loop."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    define_blueprint(bp, scope="x", path=str(proj), ctx=arqux_env.gov_ctx)
    mature_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    gate_blueprint(bp, gate="all", path=str(proj), ctx=arqux_env.gov_ctx)
    _gates_all_true(proj, bp)
    ready_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assign_blueprint(bp, executor="test-executor", path=str(proj), ctx=arqux_env.gov_ctx)
    claim_blueprint(bp, path=str(proj), ctx=arqux_env.exec_ctx)
    _clear_sections(proj, bp)
    complete_blueprint(bp, evidence="done", path=str(proj), ctx=arqux_env.exec_ctx)
    result = re_delegate_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.re_delegate ok" in result.to_text(), result.to_text()
    fm = _read_fm(proj, bp)
    assert fm.get("status") == "in_progress"
    assert str(fm.get("verification_loop", "")) == "1"


def test_block_for_architect(arqux_env) -> None:
    """block_for_architect marks BLP as blocked with appropriate message."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    result = block_for_architect(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.block_for_architect ok" in result.to_text(), result.to_text()
    fm = _read_fm(proj, bp)
    assert fm.get("status") == "blocked"


def test_cancel_blueprint(arqux_env) -> None:
    """Cancel a draft BLP — verify status=cancelled."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    result = cancel_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.cancel ok" in result.to_text(), result.to_text()
    fm = _read_fm(proj, bp)
    assert fm.get("status") == "cancelled"


# ---------------------------------------------------------------------------
# Manage tests
# ---------------------------------------------------------------------------


def test_assign_blueprint(arqux_env) -> None:
    """Assign a ready BLP to an executor and verify the executor field."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    define_blueprint(bp, scope="x", path=str(proj), ctx=arqux_env.gov_ctx)
    mature_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    gate_blueprint(bp, gate="all", path=str(proj), ctx=arqux_env.gov_ctx)
    _gates_all_true(proj, bp)
    ready_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    result = assign_blueprint(bp, executor="test-executor", path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.assign ok" in result.to_text(), result.to_text()
    fm = _read_fm(proj, bp)
    assert fm.get("executor") == "test-executor"


def test_claim_blueprint(arqux_env) -> None:
    """Claim a ready BLP — verify status changes to in_progress."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    define_blueprint(bp, scope="x", path=str(proj), ctx=arqux_env.gov_ctx)
    mature_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    gate_blueprint(bp, gate="all", path=str(proj), ctx=arqux_env.gov_ctx)
    _gates_all_true(proj, bp)
    ready_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assign_blueprint(bp, executor="test-executor", path=str(proj), ctx=arqux_env.gov_ctx)
    result = claim_blueprint(bp, path=str(proj), ctx=arqux_env.exec_ctx)
    assert "blueprint.claim ok" in result.to_text(), result.to_text()
    fm = _read_fm(proj, bp)
    assert fm.get("status") == "in_progress"


def test_update_blueprint(arqux_env) -> None:
    """Update a section and verify content changed."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    result = update_blueprint(bp, section="2", content="Updated objective", path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.update ok" in result.to_text(), result.to_text()
    body = _bp_path(proj, bp).read_text(encoding="utf-8")
    assert "Updated objective" in body


def test_update_blueprint_with_puml(arqux_env) -> None:
    """Update a section with PUML diagram."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    result = update_blueprint(bp, section="5", puml="@startuml\ntest\n@enduml", path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.update ok" in result.to_text(), result.to_text()
    body = _bp_path(proj, bp).read_text(encoding="utf-8")
    assert "@startuml" in body


def test_update_blueprint_empty_args(arqux_env) -> None:
    """Update without section or note should return error."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    result = update_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assert "error" in result.to_text().lower()


def test_read_blueprint(arqux_env) -> None:
    """Read back the blueprint content."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    result = read_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.read ok" in result.to_text() or "test BLP" in result.to_text() or bp in result.to_text()


def test_list_blueprints(arqux_env) -> None:
    """List blueprints and verify the created BLP appears."""
    proj = arqux_env.proj_root
    result = list_blueprints(path=str(proj))
    assert "blueprints:" in result.to_text() or "count=" in result.to_text()
    fields = result.fields if hasattr(result, "fields") else {}
    count = fields.get("count", 0)
    assert count >= 1, f"expected at least 1 blueprint, got {count}"


def test_update_blueprint_with_note(arqux_env) -> None:
    """Update a BLP with just a note (no section)."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    result = update_blueprint(bp, note="progress note added", path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.update ok" in result.to_text(), result.to_text()
    body = _bp_path(proj, bp).read_text(encoding="utf-8")
    assert "progress note added" in body


def test_gate_blueprint_single_gate(arqux_env) -> None:
    """Gate a single named gate (not 'all')."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    define_blueprint(bp, scope="x", path=str(proj), ctx=arqux_env.gov_ctx)
    mature_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    result = gate_blueprint(bp, gate="has_clear_objective", path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.gate ok" in result.to_text(), result.to_text()


def test_task_blueprint(arqux_env) -> None:
    """Mark a blueprint task as in_progress then completed."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    define_blueprint(bp, scope="x", path=str(proj), ctx=arqux_env.gov_ctx)
    mature_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    gate_blueprint(bp, gate="all", path=str(proj), ctx=arqux_env.gov_ctx)
    _gates_all_true(proj, bp)
    ready_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assign_blueprint(bp, executor="test-executor", path=str(proj), ctx=arqux_env.gov_ctx)
    claim_blueprint(bp, path=str(proj), ctx=arqux_env.exec_ctx)

    from arqux.handlers.blueprint.manage import task_blueprint
    result_in_progress = task_blueprint(bp, "T-1.1", "in_progress", path=str(proj), ctx=arqux_env.exec_ctx)
    assert "blueprint.task ok" in result_in_progress.to_text(), result_in_progress.to_text()
    result_done = task_blueprint(bp, "T-1.1", "completed", evidence="task done", path=str(proj), ctx=arqux_env.exec_ctx)
    assert "blueprint.task ok" in result_done.to_text(), result_done.to_text()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_missing_cycle(arqux_env) -> None:
    """Creating a blueprint without a cycle should fail gracefully."""
    path = str(arqux_env.proj_root)
    cycles_dir = arqux_env.proj_root / ".arqux" / "cycles"
    if cycles_dir.exists():
        for c in cycles_dir.iterdir():
            import shutil
            shutil.rmtree(c)
    result = create_blueprint(obj="orphan BLP", path=path, ctx=arqux_env.gov_ctx)
    assert "error" in result.profile.lower() or "no cycles" in result.to_text().lower()


def test_double_approve(arqux_env) -> None:
    """Approving an already-approved BLP must return an error."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    define_blueprint(bp, acceptance_criteria=["x"], path=str(proj), ctx=arqux_env.gov_ctx)
    mature_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    gate_blueprint(bp, gate="all", path=str(proj), ctx=arqux_env.gov_ctx)
    _gates_all_true(proj, bp)
    ready_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assign_blueprint(bp, executor="test-executor", path=str(proj), ctx=arqux_env.gov_ctx)
    claim_blueprint(bp, path=str(proj), ctx=arqux_env.exec_ctx)
    _clear_sections(proj, bp)
    complete_blueprint(bp, evidence="done", path=str(proj), ctx=arqux_env.exec_ctx)
    ac_blueprint(bp, "AC-01", "verified", evidence="ok", path=str(proj), ctx=arqux_env.gov_ctx)
    identity_dir = arqux_env.ws_root / ".arqux" / "identities"
    identity_dir.mkdir(parents=True, exist_ok=True)
    (identity_dir / "test.cortex").write_text(
        f'LNG:{bp.lower()}{{type:"process", lesson:"integration test"}}\n',
        encoding="utf-8",
    )
    result_first = approve_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.approve ok" in result_first.to_text(), result_first.to_text()
    result_second = approve_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assert "error" in result_second.profile.lower() or "invalid transition" in result_second.to_text()
