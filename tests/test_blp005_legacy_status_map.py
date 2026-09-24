"""BLP-005 (CYCLE-12): complete legacy status normalization + parser defects.

Covers the residual defects found by post-deploy audit of BLP-004:

- D-01: LEGACY_STATUS_MAP only mapped "pending" — 8 real BLPs carry
  "closed" (ENVX_MCP x6), "closed_with_observations" (x1) and
  "defined" (Banco Familiar x1). Evidence: "closed" BLPs have
  closed_at + executor (terminal); "defined" has empty executor and
  all quality_gates false (pre-execution draft).
- D-02: re_delegate read raw fm status instead of _effective_status;
  blueprint.list filtered/compared raw status so "closed" never
  matched a status=done filter.
- D-03a: Sequencer._MARKER_IN_BODY matched SNAKE_CASE identifiers
  inside content (LEGACY_STATUS_MAP -> phantom _STATUS_ marker).
- D-03c: cortex.checkpoint silently truncated fields when the
  separator was ';' or newline instead of ','.
"""

from __future__ import annotations

from pathlib import Path

from arqux.core.sequencer import Sequencer
from arqux.handlers.blueprint._helpers import (
    BP_DONE,
    BP_DRAFT,
    _effective_status,
)
from arqux.handlers.blueprint._read import list_blueprints
from arqux.handlers.blueprint.lifecycle import claim_blueprint, ready_blueprint
from arqux.handlers.blueprint.review import (
    fail_blueprint,
    re_delegate_blueprint,
)
from arqux.handlers.cortex.checkpoint import checkpoint_handler

OUT_ERROR = "OUT-ERROR"
OUT_WORK = "OUT-WORK"


def _write_bp(arqux_env, bp_id: str, status: str) -> Path:
    """Write a minimal BLP with an arbitrary (possibly legacy) status."""
    bp_dir = (
        arqux_env.proj_root / ".arqux" / "cycles" / arqux_env.cycle_id / "blueprints"
    )
    bp_dir.mkdir(parents=True, exist_ok=True)
    dest = bp_dir / f"{bp_id}.md"
    dest.write_text(
        "---\n"
        f'blueprint_id: "{bp_id}"\n'
        f'title: "legacy {status}"\n'
        f'cycle: "{arqux_env.cycle_id}"\n'
        f'status: "{status}"\n'
        'executor: ""\n'
        "---\n\n"
        f"# {bp_id}: legacy {status}\n\n"
        "## §1: Problem\n\nlegacy\n",
        encoding="utf-8",
    )
    return dest


def _out_is_error(out) -> bool:
    return out.profile == OUT_ERROR


# ---------------------------------------------------------------------------
# D-01: extended LEGACY_STATUS_MAP
# ---------------------------------------------------------------------------


def test_closed_maps_to_done():
    assert _effective_status({"status": "closed"}) == BP_DONE


def test_closed_with_observations_maps_to_done():
    assert _effective_status({"status": "closed_with_observations"}) == BP_DONE


def test_defined_maps_to_draft():
    assert _effective_status({"status": "defined"}) == BP_DRAFT


def test_unknown_status_still_fails_loudly():
    assert _effective_status({"status": "weirdo"}) == "weirdo"


# ---------------------------------------------------------------------------
# D-01/D-06 interaction: closed is terminal for fail/cancel
# ---------------------------------------------------------------------------


def test_fail_rejects_closed_blueprint(arqux_env):
    _write_bp(arqux_env, "BLP-050", "closed")
    out = fail_blueprint("BLP-050", reason="probe", path=str(arqux_env.proj_root))
    assert _out_is_error(out)
    assert "terminal" in str(out) or "done" in str(out)


def test_defined_can_ready_and_claim(arqux_env):
    _write_bp(arqux_env, "BLP-051", "defined")
    out = ready_blueprint("BLP-051", path=str(arqux_env.proj_root))
    assert not _out_is_error(out), out
    out = claim_blueprint("BLP-051", path=str(arqux_env.proj_root))
    assert not _out_is_error(out), out


# ---------------------------------------------------------------------------
# D-02: re_delegate + list use effective status
# ---------------------------------------------------------------------------


def test_re_delegate_from_closed_works(arqux_env):
    dest = _write_bp(arqux_env, "BLP-052", "closed")
    out = re_delegate_blueprint("BLP-052", path=str(arqux_env.proj_root))
    assert not _out_is_error(out), out
    assert 'status: "in_progress"' in dest.read_text(encoding="utf-8")


def test_list_filters_by_effective_status(arqux_env):
    _write_bp(arqux_env, "BLP-053", "closed")
    out = list_blueprints(status="done", path=str(arqux_env.proj_root))
    assert not _out_is_error(out), out
    bps = out.fields["blueprints"]
    match = [b for b in bps if b["id"] == "BLP-053"]
    assert match, f"closed BLP not listed under status=done: {bps}"
    assert match[0]["status"] == "done"
    assert match[0]["raw_status"] == "closed"


def test_list_omits_raw_status_for_canonical(arqux_env):
    _write_bp(arqux_env, "BLP-054", "done")
    out = list_blueprints(status="done", path=str(arqux_env.proj_root))
    bps = out.fields["blueprints"]
    match = [b for b in bps if b["id"] == "BLP-054"]
    assert match and "raw_status" not in match[0]


# ---------------------------------------------------------------------------
# D-03a: sequencer must not see markers inside identifiers
# ---------------------------------------------------------------------------


def _scan_segment(body: str):
    wrapped = f"<!-- BLP:8 -->\n## §8: Design\n\n{body}\n<!-- /BLP:8 -->"
    return Sequencer("BLP").scan(wrapped)


def test_sequencer_ignores_snake_case_identifiers():
    code = 'LEGACY_STATUS_MAP = {"pending": BP_DRAFT}\n_transition(fm, BP_DONE)'
    result = _scan_segment(code)
    assert result.pending == [], (
        f"phantom markers from identifiers: {result.pending[0].pending_markers}"
    )


def test_sequencer_still_detects_real_placeholders():
    body = "| AC-01 | _Descripcion_ |\n- _Paso_"
    result = _scan_segment(body)
    assert result.pending, "real template placeholders were lost"
    assert sorted(result.pending[0].pending_markers) == ["Descripcion", "Paso"]


# ---------------------------------------------------------------------------
# D-03c: checkpoint separators + glued-key hint
# ---------------------------------------------------------------------------


def test_checkpoint_semicolon_warns_instead_of_silent_truncation(arqux_env):
    """';' is not a separator (values may contain it) — glued keys must hint."""
    out = checkpoint_handler(
        "fcs:alpha;obj:beta;tasks:gamma",
        path=str(arqux_env.proj_root),
    )
    assert not _out_is_error(out), out
    # fcs keeps the raw glued value — the hint is what makes the loss loud
    assert "hint" in out.fields
    assert "obj" in out.fields["hint"]
    assert "tasks" in out.fields["hint"]


def test_checkpoint_newline_separator(arqux_env):
    out = checkpoint_handler(
        "fcs:alpha\nobj:beta\ntasks:gamma\nstate:wip",
        path=str(arqux_env.proj_root),
    )
    assert not _out_is_error(out), out
    assert out.fields["obj"] == "beta"
    assert out.fields["tasks"] == "gamma"


def test_checkpoint_glued_keys_produce_hint(arqux_env):
    out = checkpoint_handler(
        "fcs:alpha|obj:beta|tasks:gamma",
        path=str(arqux_env.proj_root),
    )
    assert not _out_is_error(out), out
    assert "hint" in out.fields
    assert "obj" in out.fields["hint"]
    assert "tasks" in out.fields["hint"]


def test_checkpoint_list_value_round_trips(arqux_env):
    """Commas inside [...] list values must not split entries or fuse keys."""
    from arqux.core.state import crud_read

    out = checkpoint_handler(
        "fcs:X,obj:Y,tasks:[a,b],state:Z",
        path=str(arqux_env.proj_root),
    )
    assert not _out_is_error(out), out
    assert out.fields["tasks"] == "[a,b]"
    assert out.fields["state"] == "Z"

    read = crud_read(
        arqux_env.proj_root / ".arqux" / "brain.cortex", "$8/WRK:current"
    )
    value = read["entries"][0]["value"]
    assert value["fcs"] == "X"
    assert value["obj"] == "Y"
    assert value["tasks"] == "[a,b]"
    assert value["state"] == "Z"


def test_checkpoint_list_value_with_internal_colon_round_trips(arqux_env):
    """List items containing ':' keep the full content after re-reading."""
    from arqux.core.state import crud_read

    out = checkpoint_handler(
        "fcs:X,obj:Y,tasks:[T-1: draft, T-2: done],state:Z",
        path=str(arqux_env.proj_root),
    )
    assert not _out_is_error(out), out
    assert out.fields["tasks"] == "[T-1: draft, T-2: done]"
    assert out.fields["state"] == "Z"

    read = crud_read(
        arqux_env.proj_root / ".arqux" / "brain.cortex", "$8/WRK:current"
    )
    value = read["entries"][0]["value"]
    assert value["fcs"] == "X"
    assert value["obj"] == "Y"
    assert value["tasks"] == "[T-1: draft, T-2: done]"
    assert value["state"] == "Z"


def test_checkpoint_closing_bracket_ends_value_without_separator(arqux_env):
    """A key:value right after ']' starts a new entry even without a comma."""
    from arqux.core.state import crud_read

    out = checkpoint_handler(
        "fcs:X,obj:Y,tasks:[a,b] state:Z",
        path=str(arqux_env.proj_root),
    )
    assert not _out_is_error(out), out
    assert out.fields["tasks"] == "[a,b]"
    assert out.fields["state"] == "Z"
    assert "hint" not in out.fields

    read = crud_read(
        arqux_env.proj_root / ".arqux" / "brain.cortex", "$8/WRK:current"
    )
    value = read["entries"][0]["value"]
    assert value["fcs"] == "X"
    assert value["obj"] == "Y"
    assert value["tasks"] == "[a,b]"
    assert value["state"] == "Z"


def test_checkpoint_escaped_quote_round_trips_without_double_escaping(arqux_env):
    """Quoted values with escaped quotes unescape once — no double-escaping."""
    from arqux.core.state import crud_read

    out = checkpoint_handler(
        'fcs:"say \\"hi\\"",obj:Y,tasks:[a,b],state:Z',
        path=str(arqux_env.proj_root),
    )
    assert not _out_is_error(out), out
    assert out.fields["fcs"] == 'say "hi"'

    read = crud_read(
        arqux_env.proj_root / ".arqux" / "brain.cortex", "$8/WRK:current"
    )
    value = read["entries"][0]["value"]
    assert value["fcs"] == 'say "hi"'
    assert '\\"' not in value["fcs"]
