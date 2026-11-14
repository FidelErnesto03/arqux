"""Integrity and gates suite — findings 2.2/2.10 and the silent-corruption
classes from the issue registry (2026-10-01 Manhattan CYCLE-04).

- 2.10 gates fire late: `ready` must report ALL pending placeholders in one
  call, never approve six gates and fail on the seventh.
- A-06: a blueprint must not be declared ready with orphan frontmatter.
- content-driven writers must treat payload text literally (re.sub backrefs).
"""

from __future__ import annotations

from arqux.cortex_out import OUT_ERROR, OUT_WORK
from arqux.handlers.blueprint.lifecycle import ready_blueprint
from arqux.handlers.blueprint.manage import update_blueprint
from arqux.handlers.cycle import synthesize_cycle


def test_ready_reports_all_pending_placeholders_at_once(arqux_env):
    """2.10: one call, complete list of what is missing."""
    out = ready_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root),
                          ctx=arqux_env.gov_ctx)
    assert out.profile == OUT_ERROR, out.to_text()
    pending = out.fields.get("pending") or []
    assert len(pending) > 1, out.fields
    assert "placeholder" in out.message.lower() or "unfilled" in out.message.lower()


def test_ready_message_is_actionable(arqux_env):
    out = ready_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root),
                          ctx=arqux_env.gov_ctx)
    assert "fill" in out.message.lower() or "populate" in out.message.lower()


def test_cycle_synthesize_treats_backslashes_literally(arqux_env, governor_ctx):
    """Old defect: re.sub with a runtime replacement expanded `\\1` backrefs."""
    content = (
        "$1:{Propósito}$2:{Alcance, dentro y fuera}$3:{CYC-OBJ-1: Objetivo}"
        "$4:{Guía}$5:{Checkpoint}$6:{Índice BLP}$7:{Métricas: 0}"
        "$8:{Regla}$9:{Gates}"
    )
    out = synthesize_cycle(
        cycle_id=arqux_env.cycle_id, content=content,
        path=str(arqux_env.proj_root), ctx=governor_ctx,
    )
    assert out.profile == OUT_WORK, out.to_text()

    manifest = (
        arqux_env.proj_root / ".arqux" / "cycles" / arqux_env.cycle_id /
        "MANIFEST.md"
    )
    assert manifest.exists()
    text = manifest.read_text(encoding="utf-8")
    assert "Propósito" in text or "Proposito" in text


def test_backslash_payload_survives_synthesis(arqux_env, governor_ctx):
    """A literal backslash sequence must be written verbatim, not expanded."""
    content = (
        "$1:{path a\\1b}$2:{Alcance}$3:{CYC-OBJ-1: Objetivo}"
        "$4:{Guía}$5:{Checkpoint}$6:{Índice}$7:{Métricas: 0}"
        "$8:{Regla}$9:{Gates}"
    )
    out = synthesize_cycle(
        cycle_id=arqux_env.cycle_id, content=content,
        path=str(arqux_env.proj_root), ctx=governor_ctx,
    )
    assert out.profile == OUT_WORK, out.to_text()

    manifest = (
        arqux_env.proj_root / ".arqux" / "cycles" / arqux_env.cycle_id /
        "MANIFEST.md"
    )
    assert "a\\1b" in manifest.read_text(encoding="utf-8")


def test_blueprint_update_rejects_structural_markers_in_content(arqux_env):
    """H-1/2026-10-01 DEFECTO 1: content carrying section markers must not
    silently duplicate or fuse sections."""
    out = update_blueprint(
        arqux_env.bp_id, section="3",
        content="## §3: PRECONDITIONS\n<!-- BLP:3 -->\nnoise\n<!-- /BLP:3 -->",
        path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
    )
    if out.profile == OUT_WORK:
        bp = next(
            (arqux_env.proj_root / ".arqux" / "cycles" / arqux_env.cycle_id /
             "blueprints").glob("*.md")
        )
        text = bp.read_text(encoding="utf-8")
        assert text.count("## §3") == 1, "structural marker duplicated"
        assert text.count("## §8") == 1, "later section fused or lost"
    else:
        assert out.fields.get("code") in ("VALIDATION", "INVALID_ARGS"), out.to_text()


def test_blueprint_frontmatter_is_valid_yaml(arqux_env):
    """HD-04 (audit 2026-11-13): created blueprints must carry parseable YAML.

    The previous serializer embedded unescaped quotes inside a quoted scalar;
    the lenient internal reader tolerated it while any external YAML parser
    rejected the file.
    """
    import yaml

    from arqux.handlers.blueprint.lifecycle import create_blueprint

    out = create_blueprint(
        obj="yaml probe", path=str(arqux_env.proj_root),
        cycle=arqux_env.cycle_id, ctx=arqux_env.gov_ctx,
    )
    assert out.profile == OUT_WORK, out.to_text()
    bp_id = out.fields["blueprint_id"]

    bp = next(
        (arqux_env.proj_root / ".arqux" / "cycles" / arqux_env.cycle_id /
         "blueprints").glob(f"{bp_id}.md")
    )
    fm_raw = bp.read_text(encoding="utf-8").split("---", 2)[1]
    data = yaml.safe_load(fm_raw)
    assert isinstance(data, dict), fm_raw[:200]
    assert data.get("blueprint_id") == bp_id
    assert data.get("blp_markers@"), "marker map missing"


def test_synthesize_with_content_actually_writes_sections(arqux_env):
    """HD-03: a validated payload must be written, not silently ignored."""
    from arqux.handlers.blueprint.synthesize import synthesize_blueprint

    out = synthesize_blueprint(
        "BLP-101",
        content="$1:{Problema de prueba}$2:{Objetivo de prueba}",
        cycle=arqux_env.cycle_id,
        path=str(arqux_env.proj_root),
        ctx=arqux_env.gov_ctx,
    )
    assert out.profile == OUT_WORK, out.to_text()
    assert set(out.fields.get("sections_written", [])) == {"1", "2"}

    bp = (
        arqux_env.proj_root / ".arqux" / "cycles" / arqux_env.cycle_id /
        "blueprints" / "BLP-101.md"
    )
    text = bp.read_text(encoding="utf-8")
    assert "Problema de prueba" in text
    assert "Objetivo de prueba" in text
