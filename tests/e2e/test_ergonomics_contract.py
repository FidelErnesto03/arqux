"""Ergonomics contract suite — findings 2.1, 2.2, 2.3, 2.11 of the 2026-11 review.

Each test encodes a friction observed in real dogfooding so it cannot regress
silently:

- 2.1 the writing ramp must not require tacit rules (unbraced attrs accepted,
      collisions reported, never silently renamed).
- 2.2 asymmetric meta-handlers: dry-run must exercise the same validation path
      as apply; entry.add/entry.update metrics must describe real bytes.
- 2.3 silent successes are errors: an empty checkpoint must never overwrite
      working memory.
- 2.11 errors must propose the repair, not only a code.
"""

from __future__ import annotations

from pathlib import Path

from arqux.cortex_out import OUT_ERROR, OUT_WORK
from arqux.handlers.cortex.checkpoint import checkpoint_handler
from arqux.handlers.cortex.entries import (
    entry_add_handler,
    entry_get_handler,
    entry_update_handler,
)
from arqux.handlers.cortex.patch import patch_handler

DOC = """$0

$1: STATE

FCS:current{what:"test", priority:"high", status:"current", survive:"work"}

$2: LESSONS

LNG:existing{cause:"x", lesson:"y", prevention:"z"}
"""


def _file(tmp_path: Path) -> Path:
    f = tmp_path / "doc.cortex"
    f.write_text(DOC, encoding="utf-8")
    return f


def _read_doc(f: Path) -> str:
    return f.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 2.1 — writing ramp: unbraced attrs and explicit collisions
# ---------------------------------------------------------------------------


def test_unbraced_attrs_value_is_accepted(tmp_path, governor_ctx):
    """2.1: the daily write path accepts `key:"value", ...` without braces."""
    f = _file(tmp_path)
    out = entry_add_handler(
        str(f), section="$2", sigil="LNG", name="ramp",
        value='cause:"c", lesson:"l", prevention:"p"', ctx=governor_ctx,
    )
    assert out.profile == OUT_WORK, out.to_text()
    got = entry_get_handler(str(f), "$2/LNG:ramp", ctx=governor_ctx)
    entry = got.fields["entries"][0]
    value = entry.get("value") or entry.get("attrs") or {}
    assert value.get("lesson") == "l"


def test_name_collision_is_reported_never_silent(tmp_path, governor_ctx):
    """2.1: a duplicate name appends _XXXX but reports requested+renamed."""
    f = _file(tmp_path)
    first = entry_add_handler(
        str(f), section="$2", sigil="LNG", name="dup",
        value='lesson:"one"', ctx=governor_ctx,
    )
    assert first.profile == OUT_WORK, first.to_text()
    second = entry_add_handler(
        str(f), section="$2", sigil="LNG", name="dup",
        value='lesson:"two"', ctx=governor_ctx,
    )
    assert second.profile == OUT_WORK, second.to_text()
    assert second.fields.get("requested") == "dup"
    assert second.fields.get("renamed") != "dup"


# ---------------------------------------------------------------------------
# 2.2 — dry-run must not lie; metrics must describe real bytes
# ---------------------------------------------------------------------------


def test_patch_dry_run_fails_where_apply_fails(tmp_path, governor_ctx):
    """2.2: an invalid selector is rejected in BOTH dry-run and apply."""
    f = _file(tmp_path)
    before = _read_doc(f)

    bad = "$9/NOPE:x{body}"
    dry = patch_handler(str(f), bad, dry_run=True, ctx=governor_ctx)
    real = patch_handler(str(f), bad, dry_run=False, ctx=governor_ctx)

    assert dry.fields.get("patched", []) == [], dry.to_text()
    assert real.fields.get("patched", []) == [], real.to_text()
    assert dry.profile == real.profile, (dry.to_text(), real.to_text())
    assert _read_doc(f) == before


def test_entry_add_file_bytes_describe_the_real_file(tmp_path, governor_ctx):
    """2.2: entry.add reports the whole-file size in `file_bytes`."""
    f = _file(tmp_path)
    out = entry_add_handler(
        str(f), section="$2", sigil="LNG", name="metrics",
        value='lesson:"m"', ctx=governor_ctx,
    )
    assert out.profile == OUT_WORK, out.to_text()
    assert out.fields["file_bytes"] == f.stat().st_size


def test_entry_update_file_bytes_describe_the_real_file(tmp_path, governor_ctx):
    f = _file(tmp_path)
    out = entry_update_handler(
        str(f), "$1/FCS:current", set_="priority:low", ctx=governor_ctx,
    )
    assert out.profile == OUT_WORK, out.to_text()
    assert out.fields["file_bytes"] == f.stat().st_size


# ---------------------------------------------------------------------------
# 2.3 — silent successes are errors
# ---------------------------------------------------------------------------


def test_empty_checkpoint_is_rejected_and_preserves_state(arqux_env):
    """2.3: an empty checkpoint must not erase WRK:current (E-0108..E-0113)."""
    brain = arqux_env.proj_root / ".arqux" / "brain.cortex"
    before = brain.read_text(encoding="utf-8")

    out = checkpoint_handler("", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)

    assert out.profile == OUT_ERROR, out.to_text()
    assert out.fields.get("code") == "INVALID_ARGS"
    assert brain.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# 2.11 — errors propose the repair
# ---------------------------------------------------------------------------


def test_patch_failure_reports_selector_and_reason(tmp_path, governor_ctx):
    f = _file(tmp_path)
    out = patch_handler(str(f), "$9/NOPE:x{body}", dry_run=False, ctx=governor_ctx)
    text = out.to_text()
    assert "NOPE" in text or "NOPE" in str(out.fields), text
    assert out.fields.get("failed") or out.fields.get("code"), text


def test_cycle_synthesize_without_braces_explains_the_expected_form(arqux_env, governor_ctx):
    """2.11: `$1:text` (no braces) fails with a hint about the valid form."""
    from arqux.handlers.cycle import synthesize_cycle

    out = synthesize_cycle(
        cycle_id=arqux_env.cycle_id,
        content="$1:purpose sin llaves",
        path=str(arqux_env.proj_root),
        ctx=governor_ctx,
    )
    text = out.to_text().lower()
    assert out.profile == OUT_ERROR
    assert any(hint in text for hint in ("brace", "llave", "{", "section")), text
