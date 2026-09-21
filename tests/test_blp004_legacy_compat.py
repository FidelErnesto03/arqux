"""BLP-004 (CYCLE-12): legacy blueprint compatibility + governance integrity.

Covers defects found in production (ENVX_INFRA FAMILIAR deploy, 2026-09-18)
plus audit findings:

- D-01: legacy status "pending" blocked all lifecycle transitions.
- D-02: blueprint.ac only supported checkbox ACs (legacy table rows failed).
- D-03: blueprint.execute extracted ACs from hardcoded §12 (parsed risks).
- D-04: blueprint.execute reported outcome=complete without persisting.
- D-05: _section() used \\xdf (ß) instead of § — completion gates dead.
- D-06: fail/cancel/block_for_architect bypassed VALID_TRANSITIONS.
"""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.blueprint._helpers import (
    BP_DRAFT,
    _effective_status,
    _find_ac,
    _mark_table_ac,
    _section,
    _transition,
    _unchecked_items,
)
from arqux.handlers.blueprint.execute import _extract_ac_ids, execute_blueprint
from arqux.handlers.blueprint.lifecycle import claim_blueprint, ready_blueprint
from arqux.handlers.blueprint.manage import task_blueprint, update_blueprint
from arqux.handlers.blueprint.review import (
    ac_blueprint,
    cancel_blueprint,
    complete_blueprint,
    fail_blueprint,
)

FIXTURE = Path(__file__).parent / "fixtures" / "legacy_BLP_pending_table_acs.md"
OUT_ERROR = "OUT-ERROR"
OUT_WORK = "OUT-WORK"


def _install_legacy_bp(arqux_env, bp_id: str = "BLP-009") -> Path:
    """Copy the legacy fixture into the env cycle's blueprints dir."""
    bp_dir = (
        arqux_env.proj_root / ".arqux" / "cycles" / arqux_env.cycle_id / "blueprints"
    )
    bp_dir.mkdir(parents=True, exist_ok=True)
    text = FIXTURE.read_text(encoding="utf-8").replace(
        'blueprint_id: "BLP-004"', f'blueprint_id: "{bp_id}"'
    )
    dest = bp_dir / f"{bp_id}.md"
    dest.write_text(text, encoding="utf-8")
    return dest


def _read_fm(path: Path) -> dict:
    parts = path.read_text(encoding="utf-8").split("---", 2)
    fm: dict = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm


def _fill_template_placeholders(arqux_env) -> None:
    """Fill leftover template markers on the fixture's fresh BLP.

    BLP-009's ``blueprint.ready`` gate refuses unfilled placeholders; these
    tests exercise lifecycle transitions, not the gate.
    """
    from arqux.handlers.blueprint.lifecycle import _pending_placeholders

    bp_file = (
        arqux_env.proj_root / ".arqux" / "cycles" / arqux_env.cycle_id
        / "blueprints" / f"{arqux_env.bp_id}.md"
    )
    pending = _pending_placeholders(bp_file, arqux_env.proj_root)
    if pending:
        text = bp_file.read_text(encoding="utf-8")
        for marker in pending:
            text = text.replace(marker, "filled")
        bp_file.write_text(text, encoding="utf-8")


def _read_body(path: Path) -> str:
    return path.read_text(encoding="utf-8").split("---", 2)[2]


def _complete_all_tasks(arqux_env, bp_id: str) -> None:
    body = _read_body(_bp_file(arqux_env, bp_id))
    import re

    for tid in re.findall(r"\*\*(T-\d+\.\d+):\*\*", body):
        task_blueprint(
            bp_id, tid, "completed",
            path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx,
        )


def _bp_file(arqux_env, bp_id: str) -> Path:
    return (
        arqux_env.proj_root / ".arqux" / "cycles" / arqux_env.cycle_id
        / "blueprints" / f"{bp_id}.md"
    )


# ---------------------------------------------------------------------------
# D-01: legacy status normalization
# ---------------------------------------------------------------------------


def test_effective_status_maps_pending() -> None:
    assert _effective_status({"status": "pending"}) == BP_DRAFT
    assert _effective_status({"status": "Pending"}) == BP_DRAFT


def test_effective_status_passthrough_canonical() -> None:
    for s in ("draft", "ready", "in_progress", "blocked", "done", "cancelled"):
        assert _effective_status({"status": s}) == s


def test_effective_status_unknown_returns_raw() -> None:
    assert _effective_status({"status": "weirdo"}) == "weirdo"


def test_transition_pending_maps_to_draft() -> None:
    assert _transition("BLP-009", "pending", "ready") is None
    assert _transition("BLP-009", "pending", "in_progress") is not None


def test_transition_unknown_status_fails_loudly() -> None:
    err = _transition("BLP-009", "weirdo", "ready")
    assert err is not None and "weirdo" in err


def test_legacy_pending_can_ready_and_claim(arqux_env) -> None:
    bp_path = _install_legacy_bp(arqux_env)
    r = ready_blueprint("BLP-009", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    assert r.profile == OUT_WORK
    assert _read_fm(bp_path)["status"] == "ready"
    r = claim_blueprint("BLP-009", path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert r.profile == OUT_WORK
    assert _read_fm(bp_path)["status"] == "in_progress"


# ---------------------------------------------------------------------------
# D-02: ac_blueprint multi-format
# ---------------------------------------------------------------------------


def test_find_ac_checkbox_format() -> None:
    body = "## §12: ACs\n\n- [ ] **AC-01:** Trigger ENABLED\n- [x] **AC-02:** Job disabled\n"
    assert _find_ac(body, "AC-01") == ("- [ ] **AC-01:** Trigger ENABLED", "checkbox")
    assert _find_ac(body, "AC-02")[1] == "checkbox"


def test_find_ac_table_format() -> None:
    body = "| AC-01 | Trigger ENABLED | query | pending |\n| AC-02 | Job | query | pending |\n"
    found = _find_ac(body, "AC-02")
    assert found is not None and found[1] == "table"


def test_find_ac_not_found() -> None:
    assert _find_ac("no acs here", "AC-99") is None


def test_mark_table_ac_rewrites_last_cell() -> None:
    row = "| AC-01 | Trigger ENABLED | query | pending |"
    assert _mark_table_ac(row, "verified") == "| AC-01 | Trigger ENABLED | query | verified |"
    assert _mark_table_ac("| AC-01 | two |", "verified") is None


def test_ac_blueprint_marks_table_row(arqux_env) -> None:
    bp_path = _install_legacy_bp(arqux_env)
    ready_blueprint("BLP-009", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    claim_blueprint("BLP-009", path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    r = ac_blueprint(
        "BLP-009", "AC-01", "verified", evidence="trigger ENABLED",
        path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx,
    )
    assert r.profile == OUT_WORK
    body = _read_body(bp_path)
    assert "| AC-01 | Trigger creado y ENABLED | query dba_triggers | verified |" in body
    assert "Verified: trigger ENABLED" in body


def test_ac_blueprint_checkbox_still_works(arqux_env) -> None:
    update_blueprint(
        arqux_env.bp_id, section="12",
        content="- [ ] **AC-01:** something verifiable",
        path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
    )
    _fill_template_placeholders(arqux_env)
    ready_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    claim_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    r = ac_blueprint(
        arqux_env.bp_id, "AC-01", "verified",
        path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx,
    )
    assert r.profile == OUT_WORK


def test_ac_error_message_lists_formats(arqux_env) -> None:
    _install_legacy_bp(arqux_env)
    ready_blueprint("BLP-009", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    claim_blueprint("BLP-009", path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    r = ac_blueprint("BLP-009", "AC-99", "verified", path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert r.profile == OUT_ERROR
    assert "checkbox and table" in r.message


# ---------------------------------------------------------------------------
# D-03/D-04: execute honest AC discovery + persistence
# ---------------------------------------------------------------------------


def test_extract_ac_ids_finds_table_and_checkbox() -> None:
    body = (
        "- [ ] **AC-01:** checkbox ac\n"
        "| AC-02 | table ac | q | pending |\n"
        "- **R-08 (risk)**: not an ac\n"
    )
    assert _extract_ac_ids(body) == ["AC-01", "AC-02"]


def test_execute_dry_run_lists_real_acs(arqux_env) -> None:
    _install_legacy_bp(arqux_env)
    r = execute_blueprint("BLP-009", dry_run=True, path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert r.profile == OUT_WORK
    acs = r.fields["acs"]
    ids = [a["ac"] for a in acs]
    assert "AC-01" in ids and "AC-12" in ids and len(ids) == 12
    assert all(a["status"] == "parsed" for a in acs)
    assert not any("R-08" in a["ac"] or "R-09" in a["ac"] for a in acs)


def test_execute_real_marks_table_acs(arqux_env) -> None:
    bp_path = _install_legacy_bp(arqux_env)
    ready_blueprint("BLP-009", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    claim_blueprint("BLP-009", path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    r = execute_blueprint("BLP-009", dry_run=False, path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert r.profile == OUT_WORK
    assert r.fields["outcome"] == "complete"
    fm = _read_fm(bp_path)
    assert fm["status"] == "done"
    assert fm["closed_at"]
    body = _read_body(bp_path)
    assert "| AC-01 | Trigger creado y ENABLED | query dba_triggers | verified |" in body


def test_execute_rejects_invalid_origin(arqux_env) -> None:
    _install_legacy_bp(arqux_env)  # status=pending → draft; draft→done invalid
    r = execute_blueprint("BLP-009", dry_run=False, path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert r.profile == OUT_ERROR
    assert r.fields.get("code") == "INVALID_STATE"


# ---------------------------------------------------------------------------
# D-05: _section alive — completion gate works
# ---------------------------------------------------------------------------


def test_section_matches_real_marker() -> None:
    body = "## §1: Problem\n\ntext\n\n## §14: Tareas\n\n- [ ] **T-1.1:** x\n"
    assert "T-1.1" in _section(body, 14)
    assert _section(body, 3) == ""


def test_unchecked_items_detects_pending_tasks() -> None:
    body = "## §14: Tareas\n\n- [ ] **T-1.1:** todo\n- [x] **T-1.2:** done\n"
    assert _unchecked_items(body, 14, "T") == ["T-1.1: todo"]


def test_complete_rejects_unchecked_tasks(arqux_env) -> None:
    """EXECUTION_INCOMPLETE gate revives: template §14 placeholders block done."""
    _fill_template_placeholders(arqux_env)
    ready_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    claim_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    r = complete_blueprint(arqux_env.bp_id, evidence="done", path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert r.profile == OUT_ERROR
    assert r.fields.get("code") == "EXECUTION_INCOMPLETE"


def test_complete_succeeds_when_tasks_checked(arqux_env) -> None:
    _fill_template_placeholders(arqux_env)
    ready_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    claim_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    _complete_all_tasks(arqux_env, arqux_env.bp_id)
    r = complete_blueprint(arqux_env.bp_id, evidence="done", path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert r.profile == OUT_WORK


# ---------------------------------------------------------------------------
# D-06: terminal states cannot be force-overwritten
# ---------------------------------------------------------------------------


def _done_bp(arqux_env) -> str:
    bp_id = arqux_env.bp_id
    _fill_template_placeholders(arqux_env)
    ready_blueprint(bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    claim_blueprint(bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    _complete_all_tasks(arqux_env, bp_id)
    r = complete_blueprint(bp_id, evidence="done", path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert r.profile == OUT_WORK
    return bp_id


def test_fail_from_done_rejected(arqux_env) -> None:
    bp_id = _done_bp(arqux_env)
    r = fail_blueprint(bp_id, "late fail", path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert r.profile == OUT_ERROR
    assert "terminal" in r.message


def test_cancel_from_done_rejected(arqux_env) -> None:
    bp_id = _done_bp(arqux_env)
    r = cancel_blueprint(bp_id, "late cancel", path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert r.profile == OUT_ERROR


def test_fail_records_prior_status(arqux_env) -> None:
    bp_id = arqux_env.bp_id
    _fill_template_placeholders(arqux_env)
    ready_blueprint(bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    claim_blueprint(bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    r = fail_blueprint(bp_id, "real blocker", path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert r.profile == OUT_WORK
    fm = _read_fm(_bp_file(arqux_env, bp_id))
    assert fm["status"] == "blocked"
    assert fm["prior_status"] == "in_progress"


# ---------------------------------------------------------------------------
# E2E: full lifecycle on legacy fixture — no hacks
# ---------------------------------------------------------------------------


def test_e2e_legacy_full_lifecycle(arqux_env) -> None:
    bp_path = _install_legacy_bp(arqux_env)
    proj = str(arqux_env.proj_root)

    assert ready_blueprint("BLP-009", path=proj, ctx=arqux_env.gov_ctx).profile == OUT_WORK
    assert claim_blueprint("BLP-009", path=proj, ctx=arqux_env.exec_ctx).profile == OUT_WORK
    assert ac_blueprint("BLP-009", "AC-01", "verified", evidence="ok", path=proj, ctx=arqux_env.exec_ctx).profile == OUT_WORK
    _complete_all_tasks(arqux_env, "BLP-009")
    assert complete_blueprint("BLP-009", evidence="e2e", path=proj, ctx=arqux_env.exec_ctx).profile == OUT_WORK

    fm = _read_fm(bp_path)
    assert fm["status"] == "done"
