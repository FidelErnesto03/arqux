"""BLP-003: frontmatter consistency across the blueprint/cycle lifecycle.

Covers the umbrella scope fused from the 2026-10-01 framework-gap issue:

- CA-01 synthesis populates ``title``/``cycle`` on create.
- CA-02/03 ``ready`` rejects an orphan frontmatter (empty title/cycle).
- CA-04 ``list`` falls back to the body title when ``title: ""``.
- CA-06/07 ``reconcile_cycle`` synchronizes the MANIFEST frontmatter.
- CA-08 ``complete`` persists real ``governor``/``executor`` (never anonymous).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from arqux.constants import OUT_ERROR
from arqux.handlers.blueprint._read import list_blueprints
from arqux.handlers.blueprint.lifecycle import claim_blueprint, ready_blueprint
from arqux.handlers.blueprint.manage import update_blueprint
from arqux.handlers.blueprint.review import complete_blueprint
from arqux.handlers.blueprint.synthesize import synthesize_blueprint
from arqux.sync import reconcile_cycle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bp_dir(proj_root: Path, cycle: str) -> Path:
    return proj_root / ".arqux" / "cycles" / cycle / "blueprints"


def _bp_path(proj_root: Path, bp_id: str) -> Path:
    cycles = proj_root / ".arqux" / "cycles"
    for cdir in sorted(cycles.iterdir()):
        candidate = cdir / "blueprints" / f"{bp_id}.md"
        if candidate.exists():
            return candidate
    raise AssertionError(f"blueprint {bp_id} not found under {cycles}")


def _read_fm(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, "malformed frontmatter"
    fm: dict = {}
    for line in parts[1].strip().splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        val = val.strip().strip('"')
        if val == "true":
            val = True
        elif val == "false":
            val = False
        fm[key.strip()] = val
    return fm


def _write_blp(
    proj_root: Path,
    cycle: str,
    bp_id: str,
    *,
    title: str,
    cycle_field: str,
    heading: str | None = None,
) -> Path:
    """Write a minimal, placeholder-free BLP for gate-focused tests."""
    bp_dir = _bp_dir(proj_root, cycle)
    bp_dir.mkdir(parents=True, exist_ok=True)
    path = bp_dir / f"{bp_id}.md"
    path.write_text(
        f'---\n'
        f'blueprint_id: "{bp_id}"\n'
        f'title: "{title}"\n'
        f'cycle: "{cycle_field}"\n'
        f'status: "draft"\n'
        f'governor: "test-governor"\n'
        f'---\n\n'
        f'# {bp_id}: {heading or title}\n\n'
        f'## §14: Tareas\n\n_(no pending tasks)_\n',
        encoding="utf-8",
    )
    return path


def _scrub_placeholders(proj_root: Path, bp_id: str) -> None:
    from arqux.handlers.blueprint.lifecycle import _pending_placeholders

    bp_file = _bp_path(proj_root, bp_id)
    pending = _pending_placeholders(bp_file, proj_root)
    if not pending:
        return
    text = bp_file.read_text(encoding="utf-8")
    for marker in pending:
        text = text.replace(marker, "filled")
    bp_file.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# CA-01 — synthesize populates title/cycle
# ---------------------------------------------------------------------------


def test_synthesize_populates_title_and_cycle(arqux_env) -> None:
    result = synthesize_blueprint(
        "BLP-002", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx
    )
    assert "blueprint.synthesize" in result.to_text(), result.to_text()
    fm = _read_fm(_bp_path(arqux_env.proj_root, "BLP-002"))
    assert str(fm.get("title", "")).strip(), "synthesize left an empty title"
    assert str(fm.get("cycle", "")).strip(), "synthesize left an empty cycle"


# ---------------------------------------------------------------------------
# CA-02 / CA-03 — ready rejects an orphan frontmatter
# ---------------------------------------------------------------------------


def test_ready_rejects_empty_title(arqux_env) -> None:
    proj = arqux_env.proj_root
    _write_blp(proj, arqux_env.cycle_id, "BLP-010", title="", cycle_field=arqux_env.cycle_id)
    result = ready_blueprint(
        "BLP-010", path=str(proj), cycle=arqux_env.cycle_id, ctx=arqux_env.gov_ctx
    )
    assert result.profile == OUT_ERROR, result.to_text()
    assert "title" in result.to_text()


def test_ready_rejects_empty_cycle(arqux_env) -> None:
    proj = arqux_env.proj_root
    _write_blp(proj, arqux_env.cycle_id, "BLP-011", title="Has title", cycle_field="")
    result = ready_blueprint(
        "BLP-011", path=str(proj), cycle=arqux_env.cycle_id, ctx=arqux_env.gov_ctx
    )
    assert result.profile == OUT_ERROR, result.to_text()
    assert "cycle" in result.to_text()


# ---------------------------------------------------------------------------
# CA-04 — list falls back to the body title
# ---------------------------------------------------------------------------


def test_list_falls_back_to_body_title(arqux_env) -> None:
    proj = arqux_env.proj_root
    _write_blp(
        proj,
        arqux_env.cycle_id,
        "BLP-012",
        title="",
        cycle_field=arqux_env.cycle_id,
        heading="Titulo Del Cuerpo",
    )
    result = list_blueprints(path=str(proj))
    entries = result.fields.get("blueprints", [])
    entry = next(e for e in entries if e["id"] == "BLP-012")
    assert entry["title"] == "Titulo Del Cuerpo"


# ---------------------------------------------------------------------------
# CA-06 / CA-07 — reconcile_cycle synchronizes the MANIFEST frontmatter
# ---------------------------------------------------------------------------


def test_reconcile_syncs_manifest_frontmatter(arqux_env) -> None:
    proj = arqux_env.proj_root
    manifest = proj / ".arqux" / "cycles" / arqux_env.cycle_id / "MANIFEST.md"

    text = manifest.read_text(encoding="utf-8")
    text = re.sub(r'(?m)^status:.*$', 'status: "draft"', text)
    text = re.sub(r'(?m)^governor:.*$', 'governor: "test-governor"', text)
    text = re.sub(r'(?m)^project_ref:.*$', 'project_ref: ""', text)
    text = re.sub(r'(?m)^updated_at:.*$', 'updated_at: ""', text)
    text = re.sub(
        r"## §9:.*?(?=\n## §10:|\Z)",
        "## §9: Puntos de Control\n\n| Compuerta | Estado |\n|---|---|\n"
        "| has_clear_purpose | \u2705 |\n",
        text,
        flags=re.DOTALL,
    )
    manifest.write_text(text, encoding="utf-8")

    result = reconcile_cycle(proj, arqux_env.cycle_id)
    assert result["reconciled"] is True, result.get("errors")

    new_text = manifest.read_text(encoding="utf-8")
    fm = _read_fm(manifest)
    assert fm["project_ref"] == "test-proj"
    assert fm["updated_at"], "updated_at must be refreshed"
    assert fm["status"] in ("draft", "active")
    assert fm["governor"] == "test-governor", "real governor must be preserved"
    assert "has_clear_purpose: true" in new_text, "quality gate not synced"


# ---------------------------------------------------------------------------
# CA-08 — complete persists real governor/executor
# ---------------------------------------------------------------------------


def test_complete_sets_governor_and_executor(arqux_env) -> None:
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    update_blueprint(bp, section="6", content="**Dentro:** x", path=str(proj), ctx=arqux_env.gov_ctx)
    _scrub_placeholders(proj, bp)
    assert "ok" in ready_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx).to_text()
    claim_blueprint(bp, path=str(proj), ctx=arqux_env.exec_ctx)
    update_blueprint(bp, section="13", content=" ", path=str(proj), ctx=arqux_env.gov_ctx)
    update_blueprint(bp, section="14", content=" ", path=str(proj), ctx=arqux_env.gov_ctx)

    # Force anonymous to prove complete rewrites it from ctx.agent_id.
    bp_file = _bp_path(proj, bp)
    text = bp_file.read_text(encoding="utf-8")
    text = re.sub(r'(?m)^governor:.*$', 'governor: "anonymous"', text)
    text = re.sub(r'(?m)^executor:.*$', 'executor: "anonymous"', text)
    bp_file.write_text(text, encoding="utf-8")

    result = complete_blueprint(
        bp, evidence="all done", path=str(proj), ctx=arqux_env.exec_ctx
    )
    assert "blueprint.complete ok" in result.to_text(), result.to_text()
    fm = _read_fm(bp_file)
    assert fm["governor"] == "test-executor"
    assert fm["executor"] == "test-executor"


# ---------------------------------------------------------------------------
# Hardening from the independent audit (H-1..H-4)
# ---------------------------------------------------------------------------


def _manifest(proj_root: Path, cycle: str) -> Path:
    return proj_root / ".arqux" / "cycles" / cycle / "MANIFEST.md"


def _strip_gate_block(text: str) -> str:
    return re.sub(r"(?ms)^quality_gates@:.*?^\}\n?", "", text)


@pytest.mark.parametrize(
    "title_line", ["title: ''", "title: ~", "title: null", "title: false"]
)
def test_ready_rejects_none_like_title(arqux_env, title_line: str) -> None:
    proj = arqux_env.proj_root
    bp_dir = _bp_dir(proj, arqux_env.cycle_id)
    bp_dir.mkdir(parents=True, exist_ok=True)
    (bp_dir / "BLP-020.md").write_text(
        "---\n"
        'blueprint_id: "BLP-020"\n'
        f"{title_line}\n"
        f'cycle: "{arqux_env.cycle_id}"\n'
        'status: "draft"\n'
        "---\n\n"
        "# BLP-020: x\n\n"
        "## §14: Tareas\n\n",
        encoding="utf-8",
    )
    result = ready_blueprint(
        "BLP-020", path=str(proj), cycle=arqux_env.cycle_id, ctx=arqux_env.gov_ctx
    )
    assert result.profile == OUT_ERROR, result.to_text()
    assert "title" in result.to_text()


def test_reconcile_cleans_legacy_gate_key(arqux_env) -> None:
    proj = arqux_env.proj_root
    manifest = _manifest(proj, arqux_env.cycle_id)
    text = _strip_gate_block(manifest.read_text(encoding="utf-8"))
    text = re.sub(
        r"(?m)^(_template_ref:.*)$",
        'quality_gates@: "{"\nhas_clear_purpose: "false,"\n'
        'has_explicit_scope: "false,"\n\\1',
        text,
        count=1,
    )
    text = re.sub(
        r"## §9:.*?(?=\n## §10:|\Z)",
        "## §9: PC\n\n| Compuerta | Estado |\n|---|---|\n"
        "| has_clear_purpose | \u2705 |\n",
        text,
        flags=re.DOTALL,
    )
    manifest.write_text(text, encoding="utf-8")

    reconcile_cycle(proj, arqux_env.cycle_id)

    new = manifest.read_text(encoding="utf-8")
    assert new.count("quality_gates@:") == 1, "duplicate quality_gates@ key"
    assert new.count("has_clear_purpose:") == 1, "orphan flat gate line left behind"
    assert "has_clear_purpose: true" in new


def test_reconcile_preserves_operator_active(arqux_env) -> None:
    proj = arqux_env.proj_root
    manifest = _manifest(proj, arqux_env.cycle_id)
    text = re.sub(
        r"(?m)^status:.*$",
        'status: "active"',
        manifest.read_text(encoding="utf-8"),
        count=1,
    )
    manifest.write_text(text, encoding="utf-8")

    reconcile_cycle(proj, arqux_env.cycle_id)

    assert _read_fm(manifest)["status"] == "active", "active downgraded to draft"


def test_reconcile_skips_gates_without_section9(arqux_env) -> None:
    proj = arqux_env.proj_root
    manifest = _manifest(proj, arqux_env.cycle_id)
    text = _strip_gate_block(manifest.read_text(encoding="utf-8"))
    text = re.sub(
        r"## §9:.*?(?=\n## §10:|\Z)",
        "## §9: nothing\n\nno gates here\n",
        text,
        flags=re.DOTALL,
    )
    manifest.write_text(text, encoding="utf-8")

    reconcile_cycle(proj, arqux_env.cycle_id)

    assert "quality_gates@" not in manifest.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Round-2 hardening (F-1, F-2, F-5, F-6)
# ---------------------------------------------------------------------------


def test_synthesize_preserves_canonical_gate_block(arqux_env) -> None:
    synthesize_blueprint("BLP-021", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    fm_text = _bp_path(arqux_env.proj_root, "BLP-021").read_text(encoding="utf-8").split("---", 2)[1]
    assert "quality_gates@:" in fm_text, "canonical gate block was flattened"
    assert re.search(r"(?m)^quality_gates:", fm_text) is None, "legacy quality_gates: key present"


def test_list_reads_blp_title_marker(arqux_env) -> None:
    proj = arqux_env.proj_root
    bp_dir = _bp_dir(proj, arqux_env.cycle_id)
    bp_dir.mkdir(parents=True, exist_ok=True)
    (bp_dir / "BLP-022.md").write_text(
        "---\n"
        'blueprint_id: "BLP-022"\n'
        'title: ""\n'
        f'cycle: "{arqux_env.cycle_id}"\n'
        'status: "draft"\n'
        "---\n\n"
        "<!-- BLP:TITLE -->\n"
        "Marcador Titulo Real\n"
        "<!-- /BLP:TITLE -->\n\n"
        "## §14: Tareas\n\n",
        encoding="utf-8",
    )
    result = list_blueprints(path=str(proj))
    entry = next(e for e in result.fields["blueprints"] if e["id"] == "BLP-022")
    assert entry["title"] == "Marcador Titulo Real"


def test_reconcile_reads_unquoted_status(arqux_env) -> None:
    proj = arqux_env.proj_root
    manifest = _manifest(proj, arqux_env.cycle_id)
    text = re.sub(
        r"(?m)^status:.*$",
        "status: closed",
        manifest.read_text(encoding="utf-8"),
        count=1,
    )
    manifest.write_text(text, encoding="utf-8")

    reconcile_cycle(proj, arqux_env.cycle_id)

    assert _read_fm(manifest)["status"] == "closed"


def test_list_survives_file_without_frontmatter(arqux_env) -> None:
    proj = arqux_env.proj_root
    bp_dir = _bp_dir(proj, arqux_env.cycle_id)
    bp_dir.mkdir(parents=True, exist_ok=True)
    (bp_dir / "BLP-023.md").write_text("# no frontmatter\n", encoding="utf-8")

    result = list_blueprints(path=str(proj))

    assert result.profile != OUT_ERROR


# ---------------------------------------------------------------------------
# Round-3 hardening (H-F7..H-F9): canonical block survives the whole lifecycle
# ---------------------------------------------------------------------------


def _fm_of(proj: Path, bp_id: str) -> str:
    return _bp_path(proj, bp_id).read_text(encoding="utf-8").split("---", 2)[1]


def test_ready_preserves_canonical_gate_block(arqux_env) -> None:
    proj, bp = arqux_env.proj_root, arqux_env.bp_id
    update_blueprint(bp, section="6", content="**Dentro:** x", path=str(proj), ctx=arqux_env.gov_ctx)
    _scrub_placeholders(proj, bp)
    ready_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)

    fm_text = _fm_of(proj, bp)
    assert "quality_gates@:" in fm_text
    assert re.search(r"(?m)^quality_gates:", fm_text) is None


def test_complete_preserves_canonical_gate_block(arqux_env) -> None:
    proj, bp = arqux_env.proj_root, arqux_env.bp_id
    update_blueprint(bp, section="6", content="**Dentro:** x", path=str(proj), ctx=arqux_env.gov_ctx)
    _scrub_placeholders(proj, bp)
    ready_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    claim_blueprint(bp, path=str(proj), ctx=arqux_env.exec_ctx)
    update_blueprint(bp, section="13", content=" ", path=str(proj), ctx=arqux_env.gov_ctx)
    update_blueprint(bp, section="14", content=" ", path=str(proj), ctx=arqux_env.gov_ctx)
    complete_blueprint(bp, evidence="done", path=str(proj), ctx=arqux_env.exec_ctx)

    fm_text = _fm_of(proj, bp)
    assert "quality_gates@:" in fm_text
    assert re.search(r"(?m)^quality_gates:", fm_text) is None
    assert re.search(r"(?m)^has_clear_objective:", fm_text) is None


def test_synthesize_handles_backslash_in_governor(arqux_env) -> None:
    from arqux.constants import ROLE_GOVERNOR
    from arqux.permissions import PermissionContext

    ctx = PermissionContext(agent_id="a\\1b", role=ROLE_GOVERNOR)
    result = synthesize_blueprint("BLP-024", path=str(arqux_env.proj_root), ctx=ctx)
    assert "blueprint.synthesize" in result.to_text(), result.to_text()
    fm = _read_fm(_bp_path(arqux_env.proj_root, "BLP-024"))
    assert fm.get("governor") == "a\\1b"


def test_set_frontmatter_line_inserts_missing_key() -> None:
    from arqux.handlers.blueprint.synthesize import _set_frontmatter_line

    text = '---\nblueprint_id: "x"\n---\n\n# body\n'
    out = _set_frontmatter_line(text, "governor", "alfred")
    assert 'governor: "alfred"' in out
    assert out.index("governor") < out.index("# body")


def test_set_fm_scalar_handles_backslash() -> None:
    from arqux.sync import _set_fm_scalar

    out = _set_fm_scalar('governor: "x"\n', "governor", "a\\1b")
    assert 'governor: "a\\1b"' in out


def test_reconcile_handles_backslash_governor(arqux_env) -> None:
    proj = arqux_env.proj_root
    manifest = _manifest(proj, arqux_env.cycle_id)
    text = re.sub(
        r"(?m)^governor:.*$",
        lambda _m: 'governor: "a\\1b"',
        manifest.read_text(encoding="utf-8"),
        count=1,
    )
    manifest.write_text(text, encoding="utf-8")

    result = reconcile_cycle(proj, arqux_env.cycle_id)

    assert result["reconciled"] is True, result.get("errors")
    assert "a\\1b" in manifest.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# blueprint.frontmatter.update (BLP-003 measure #2)
# ---------------------------------------------------------------------------


def test_frontmatter_update_repairs_orphan(arqux_env) -> None:
    from arqux.handlers.blueprint.manage import update_frontmatter

    proj = arqux_env.proj_root
    bp_dir = _bp_dir(proj, arqux_env.cycle_id)
    bp_dir.mkdir(parents=True, exist_ok=True)
    (bp_dir / "BLP-030.md").write_text(
        '---\nblueprint_id: "BLP-030"\ntitle: ""\ncycle: ""\nstatus: "draft"\n---\n\n'
        "<!-- BLP:TITLE -->\nTitulo Orfano\n<!-- /BLP:TITLE -->\n\n## §14: Tareas\n\n",
        encoding="utf-8",
    )

    result = update_frontmatter(
        "BLP-030", cycle=arqux_env.cycle_id, path=str(proj), ctx=arqux_env.gov_ctx
    )

    assert "blueprint.frontmatter.update ok" in result.to_text(), result.to_text()
    fm = _read_fm(_bp_path(proj, "BLP-030"))
    assert fm["title"] == "Titulo Orfano"  # derived from the body marker
    assert fm["cycle"] == arqux_env.cycle_id


def test_frontmatter_update_requires_input(arqux_env) -> None:
    from arqux.handlers.blueprint.manage import update_frontmatter

    proj = arqux_env.proj_root
    bp_dir = _bp_dir(proj, arqux_env.cycle_id)
    bp_dir.mkdir(parents=True, exist_ok=True)
    (bp_dir / "BLP-031.md").write_text(
        '---\nblueprint_id: "BLP-031"\ntitle: "Has title"\ncycle: "X"\nstatus: "draft"\n---\n\n',
        encoding="utf-8",
    )
    result = update_frontmatter("BLP-031", path=str(proj), ctx=arqux_env.gov_ctx)
    assert result.profile == OUT_ERROR, result.to_text()
