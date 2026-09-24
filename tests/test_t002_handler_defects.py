"""Regression tests for T-002 — Manhattan CYCLE-01 handler defects.

Covers:
- cortex.gc: first_kept controls how many occurrences are kept per group
- write amplification: identical-content rewrites are skipped; metric
  batches land in a single rewrite
- sync.reconcile: documented level=project/workspace values are honored
- entry.add name handling: names stored verbatim, collisions documented
"""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.cortex import entry_add_handler, gc_handler
from arqux.handlers.sync import reconcile_handler
from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test", role="governor")

_GC_BRAIN = """$0

GSIG:KNW{name:"knowledge", type:"attrs", risk:"B", layer:"Semantic", description:"k"}

$10: KNOWLEDGE

KNW:metric{name:"metric", value:"1", updated:"a", topic:"metrics", content:"c", status:"current"}
KNW:metric{name:"metric", value:"2", updated:"b", topic:"metrics", content:"c", status:"current"}
KNW:metric{name:"metric", value:"3", updated:"b", topic:"metrics", content:"c", status:"current"}
KNW:metric{name:"metric", value:"4", updated:"b", topic:"metrics", content:"c", status:"current"}
"""

_PULSE_BRAIN = """$0

GSIG:KNW{name:"knowledge", type:"attrs", risk:"B", layer:"Semantic", description:"k"}

$6: PULSE

AUD:E_0001{date:"t", event:"E-0001", task:"-", kind:"note", agent:"a", result:"r", evidence:"r"}
"""


def _read_kept_values(f: Path, selector: str = "$10/KNW:*") -> list:
    from arqux.core.state import crud_read

    return [e["value"].get("value") for e in crud_read(f, selector)["entries"]]


# ---------------------------------------------------------------------------
# (2) cortex.gc first_kept
# ---------------------------------------------------------------------------


def test_gc_first_kept_default_keeps_first(tmp_path: Path) -> None:
    f = tmp_path / "brain.cortex"
    f.write_text(_GC_BRAIN)
    out = gc_handler(str(f), dry_run=False, force=True)
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["removed"] == 3
    assert _read_kept_values(f) == ["1"]


def test_gc_first_kept_honored(tmp_path: Path) -> None:
    """first_kept=N conserves the first N occurrences of each group."""
    f = tmp_path / "brain.cortex"
    f.write_text(_GC_BRAIN)
    out = gc_handler(str(f), dry_run=False, force=True, first_kept=2)
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["removed"] == 2
    assert _read_kept_values(f) == ["1", "2"]


def test_gc_first_kept_dry_run_reports_without_mutating(tmp_path: Path) -> None:
    f = tmp_path / "brain.cortex"
    f.write_text(_GC_BRAIN)
    out = gc_handler(str(f), dry_run=True, first_kept=2)
    assert out.profile == "OUT-WORK"
    assert out.fields["removed"] == 0
    assert len(out.fields["duplicates"]) == 2
    assert _read_kept_values(f) == ["1", "2", "3", "4"]


def test_gc_first_kept_invalid_value_returns_invalid_args(tmp_path: Path) -> None:
    """A non-numeric first_kept must not crash the handler."""
    f = tmp_path / "brain.cortex"
    f.write_text(_GC_BRAIN)
    out = gc_handler(str(f), dry_run=False, force=True, first_kept="two")
    assert out.profile == "OUT-ERROR"
    assert out.fields.get("code") == "INVALID_ARGS"
    assert "first_kept" in out.message
    assert _read_kept_values(f) == ["1", "2", "3", "4"]


def test_gc_duplicate_report_is_unambiguous(tmp_path: Path) -> None:
    """Report carries the effective first_kept count and the kept entry names."""
    f = tmp_path / "brain.cortex"
    f.write_text(_GC_BRAIN)
    out = gc_handler(str(f), dry_run=True, first_kept=2)
    dup = out.fields["duplicates"][0]
    assert dup["first_kept"] == 2
    assert dup["kept_names"] == ["metric", "metric"]
    assert dup["count"] == 4


def test_gc_single_atomic_rewrite(tmp_path: Path, monkeypatch) -> None:
    """gc removes all duplicates in ONE file rewrite, not one per duplicate."""
    import arqux.handlers.cortex.gc as gc_mod

    f = tmp_path / "brain.cortex"
    f.write_text(_GC_BRAIN)

    writes = {"n": 0}
    real = gc_mod.atomic_write_json

    def counting(doc, path, **kwargs):
        writes["n"] += 1
        return real(doc, path, **kwargs)

    monkeypatch.setattr(gc_mod, "atomic_write_json", counting)
    out = gc_handler(str(f), dry_run=False, force=True)
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["removed"] == 3
    assert writes["n"] == 1
    assert _read_kept_values(f) == ["1"]


# ---------------------------------------------------------------------------
# (3) write amplification
# ---------------------------------------------------------------------------


def test_sync_metrics_batch_single_rewrite(tmp_path: Path, monkeypatch) -> None:
    """N metrics merge into the brain PULSE with a single rewrite."""
    import arqux.cortex.atomic as atomic_mod
    import arqux.sync as sync_mod
    from arqux.cortex.reader import cortex_to_dict

    brain_dir = tmp_path / ".arqux"
    brain_dir.mkdir()
    brain = brain_dir / "brain.cortex"
    brain.write_text(_PULSE_BRAIN, encoding="utf-8")

    writes = {"n": 0}
    real = atomic_mod.atomic_write_json

    def counting(doc, path, **kwargs):
        writes["n"] += 1
        return real(doc, path, **kwargs)

    monkeypatch.setattr(atomic_mod, "atomic_write_json", counting)
    doc = cortex_to_dict(brain.read_text(encoding="utf-8"))
    sync_mod._upsert_metrics(doc, {"handlers": 7, "tasks_done": 2, "cycles_closed": 1}, "ts")
    atomic_mod.atomic_write_json(doc, str(brain))
    assert writes["n"] == 1

    from arqux.core.state import crud_read

    entries = crud_read(brain, "$6/KNW:*")["entries"]
    by_name = {e["name"]: e["value"].get("value") for e in entries}
    assert by_name == {"handlers": "7", "tasks_done": "2", "cycles_closed": "1"}


# ---------------------------------------------------------------------------
# (5) reconcile level signature
# ---------------------------------------------------------------------------


def _ws_and_project(tmp_path: Path) -> Path:
    from arqux.handlers import project, workspace

    workspace.init_workspace(path=str(tmp_path), ctx=_CONTEXT)
    proj = tmp_path / "proj"
    proj.mkdir()
    project.init_project(name="proj", path=str(proj), ctx=_CONTEXT)
    return proj


def test_reconcile_level_workspace_forces_meta_brain(tmp_path: Path) -> None:
    """level=workspace reconciles the meta-brain even from a project path."""
    proj = _ws_and_project(tmp_path)
    out = reconcile_handler(path=str(proj), level="workspace", ctx=_CONTEXT)
    assert out.profile == "OUT-WORK", str(out.fields)
    assert "workspace=true" in out.message


def test_reconcile_level_project_forces_project_brain(tmp_path: Path) -> None:
    """level=project reconciles the project brain (OBJ updated)."""
    from arqux.core.state import crud_read

    proj = _ws_and_project(tmp_path)
    out = reconcile_handler(path=str(proj), level="project", ctx=_CONTEXT)
    assert out.profile == "OUT-WORK", str(out.fields)
    assert "workspace=false" in out.message
    obj = crud_read(proj / ".arqux" / "brain.cortex", "$3/OBJ:*")
    assert obj["entries"]
    assert obj["entries"][0]["value"].get("event") == "brain.reconcile"


# ---------------------------------------------------------------------------
# (1) entry.add name handling
# ---------------------------------------------------------------------------


def test_entry_add_preserves_name_verbatim(tmp_path: Path) -> None:
    """Names are stored verbatim — no case, hyphen, dot or underscore mangling."""
    f = tmp_path / "brain.cortex"
    f.write_text(_GC_BRAIN)
    for name in ("MyMetric", "my-metric", "metric.v2", "metric_2"):
        out = entry_add_handler(
            str(f), "$10", "KNW", name,
            'name:"x", value:"1", updated:"t", topic:"metrics", content:"c", status:"current"',
            force=True, ctx=_CONTEXT,
        )
        assert out.profile == "OUT-WORK", str(out.fields)
        assert out.fields["name"] == name
        assert out.fields.get("renamed") is None


def test_entry_add_collision_rename_is_documented(tmp_path: Path) -> None:
    """Same-name writes get a _NNNN suffix, reported via requested/renamed."""
    f = tmp_path / "brain.cortex"
    f.write_text(_GC_BRAIN)
    value = 'name:"x", value:"1", updated:"t", topic:"metrics", content:"c", status:"current"'
    first = entry_add_handler(str(f), "$10", "KNW", "dup", value, force=True, ctx=_CONTEXT)
    second = entry_add_handler(str(f), "$10", "KNW", "dup", value, force=True, ctx=_CONTEXT)
    assert first.fields["name"] == "dup"
    assert second.fields["name"] == "dup_0001"
    assert second.fields["requested"] == "dup"
    assert second.fields["renamed"] == "dup_0001"


# ---------------------------------------------------------------------------
# (4) opaque validation + value-optional (pinning T-004 fixes)
# ---------------------------------------------------------------------------


def test_entry_add_content_only_accepted_without_value(tmp_path: Path) -> None:
    """Pinned from T-004: content (canal I) alone is enough — no value needed."""
    f = tmp_path / "brain.cortex"
    f.write_text(_GC_BRAIN)
    out = entry_add_handler(
        str(f), "$10", "KNW", "dummy",
        content='KNW:from_content{name:"from_content", value:"9", updated:"t", topic:"metrics", content:"c", status:"current"}',
        force=True, ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["name"].startswith("from_content")


def test_entry_add_validation_errors_enumerated(tmp_path: Path) -> None:
    """Pinned from T-004: each violation is enumerated with entry/field context."""
    f = tmp_path / "brain.cortex"
    f.write_text(_GC_BRAIN + "\nKNW:bad0{name:\"bad0\"}\n")
    out = entry_add_handler(
        str(f), "$10", "KNW", "bad1",
        'name:"bad1", bogus_field:"x"',
        ctx=_CONTEXT,
    )
    assert out.profile == "OUT-ERROR"
    assert out.fields.get("error_count", 0) >= 2
    diagnostics = out.fields.get("diagnostics") or []
    assert len(diagnostics) == out.fields["error_count"]
    for i, diag in enumerate(diagnostics, 1):
        assert f"[{i}] {diag}" in out.message
    assert "KNW:bad0" in out.message and "KNW:bad1" in out.message
