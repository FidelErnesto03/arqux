"""BLP-009 regression tests.

Covers:

* ``identity_resolver._find_workspace_root`` must never treat a ``.arqux``
  directory as the workspace root (AC-01), and identity resolution must
  never construct ``.arqux/.arqux/`` paths (AC-02).
* ``blueprint.ready`` must refuse BLPs that still carry template
  placeholders (AC-03) while ignoring the ``☐``/``✅`` quality-gate cells
  of §18, which are gate state — not placeholders (AC-04).
"""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.blueprint.lifecycle import (
    _pending_placeholders,
    ready_blueprint,
)
from arqux.identity_resolver import _find_workspace_root, resolve_agent_identity


def _bp_path(proj_root: Path, bp_id: str) -> Path:
    cycles_dir = proj_root / ".arqux" / "cycles"
    for cdir in cycles_dir.iterdir():
        candidate = cdir / "blueprints" / f"{bp_id}.md"
        if candidate.exists():
            return candidate
    raise AssertionError(f"blueprint {bp_id} not found under {cycles_dir}")


def _status_of(bp_file: Path) -> str:
    text = bp_file.read_text(encoding="utf-8")
    for line in text.split("---", 2)[1].splitlines():
        if line.strip().startswith("status:"):
            return line.split(":", 1)[1].strip().strip('"')
    raise AssertionError("no status field in frontmatter")


# ---------------------------------------------------------------------------
# AC-01 / AC-02: workspace-root guard
# ---------------------------------------------------------------------------


def test_find_workspace_root_start_is_arqux(tmp_path: Path) -> None:
    """start=.arqux/ containing its own AGENTS.md resolves to the parent."""
    ws = tmp_path / "ws"
    arqux_dir = ws / ".arqux"
    arqux_dir.mkdir(parents=True)
    (ws / "AGENTS.md").write_text("kernel", encoding="utf-8")
    # The poisoned case: .arqux itself carries an AGENTS.md.
    (arqux_dir / "AGENTS.md").write_text("governance kernel", encoding="utf-8")

    assert _find_workspace_root(arqux_dir) == ws


def test_find_workspace_root_nested_arqux_skipped(tmp_path: Path) -> None:
    """A `.arqux` dir is never itself the root — its parent governs."""
    ws = tmp_path / "ws"
    nested = ws / "proj" / ".arqux"
    nested.mkdir(parents=True)
    (ws / "AGENTS.md").write_text("kernel", encoding="utf-8")
    (nested / "AGENTS.md").write_text("project governance", encoding="utf-8")

    # `.arqux` normalizes to its parent, which is the nearest governance
    # root (it holds `.arqux/AGENTS.md`). The `.arqux` dir is never picked.
    assert _find_workspace_root(nested) == ws / "proj"


def test_resolve_identity_never_produces_double_arqux(tmp_path: Path) -> None:
    """resolve_agent_identity from a `.arqux` start must not build `.arqux/.arqux/`."""
    ws = tmp_path / "ws"
    arqux_dir = ws / ".arqux"
    (arqux_dir / "identities").mkdir(parents=True)
    (ws / "AGENTS.md").write_text("kernel", encoding="utf-8")
    (arqux_dir / "AGENTS.md").write_text("gov", encoding="utf-8")
    (arqux_dir / "identities" / "alfred.cortex").write_text(
        'IDN:alfred{name:"alfred"}', encoding="utf-8"
    )

    # project_root is the .arqux dir itself — worst-case input.
    resolved = resolve_agent_identity("alfred", project_root=arqux_dir)
    assert resolved == "alfred"
    # And the resolver must not have fabricated a nested .arqux path.
    assert not (arqux_dir / ".arqux").exists()


# ---------------------------------------------------------------------------
# AC-03 / AC-04: blueprint.ready placeholder gate
# ---------------------------------------------------------------------------


def test_ready_rejects_unfilled_placeholders(arqux_env) -> None:
    """A freshly-created BLP retains template markers → ready is refused."""
    proj = arqux_env.proj_root
    bp = arqux_env.bp_id  # created by the fixture, sections still templated

    before = _status_of(_bp_path(proj, bp))
    out = ready_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)

    assert out.profile == "OUT-ERROR", out.to_text()
    assert "unfilled template placeholders" in out.to_text()
    assert out.fields.get("pending"), "error must list pending placeholders"
    # No transition happened.
    assert _status_of(_bp_path(proj, bp)) == before


def test_pending_placeholders_ignores_section_18(arqux_env) -> None:
    """§18 ☐/✅ quality-gate cells are gate state, not placeholders (AC-04)."""
    bp_file = _bp_path(arqux_env.proj_root, arqux_env.bp_id)
    text = bp_file.read_text(encoding="utf-8")
    assert "☐" in text, "fresh template must contain §18 gate cells"

    pending = _pending_placeholders(bp_file)
    assert all("☐" not in p and "✅" not in p for p in pending)


def test_pending_placeholders_no_identifier_false_positive(arqux_env) -> None:
    """`_…` inside identifiers (e.g. `has_validations`) is not a placeholder."""
    bp_file = _bp_path(arqux_env.proj_root, arqux_env.bp_id)
    text = bp_file.read_text(encoding="utf-8")
    text = text.replace("has_validations", "has_validations")  # already present in fm
    bp_file.write_text(text, encoding="utf-8")

    pending = _pending_placeholders(bp_file)
    assert not any("validations" in p.lower() for p in pending), pending


def test_ready_accepts_filled_blueprint(arqux_env) -> None:
    """Once every template marker is filled, ready transitions to ready."""
    from arqux.handlers.cycle import MARKER_PATTERN

    proj = arqux_env.proj_root
    bp = arqux_env.bp_id
    bp_file = _bp_path(proj, bp)
    text = bp_file.read_text(encoding="utf-8")
    for m in MARKER_PATTERN.finditer(text):
        text = text.replace(m.group(0), "filled")
    bp_file.write_text(text, encoding="utf-8")

    out = ready_blueprint(bp, path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.ready ok" in out.to_text(), out.to_text()
    assert _status_of(bp_file) == "ready"
