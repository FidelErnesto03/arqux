"""Regression tests for T-011 — metrics upsert + sync_brain batch rewrite."""

from __future__ import annotations

from pathlib import Path

from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test", role="governor")

_BRAIN = """$0

GSIG:WRK{name:"work", type:"attrs", risk:"B", layer:"Working", description:"w"}
GSIG:FCS{name:"focus", type:"attrs", risk:"H", layer:"Working", description:"f"}
GSIG:KNW{name:"knowledge", type:"attrs", risk:"B", layer:"Semantic", description:"k"}

$2: FOCUS

FCS:current{name:"current", what:"Initial focus", priority:"medium", status:"current", survive:"work"}

$6: PULSE

KNW:tasks_active{name:"tasks_active", value:"1", updated:"old", topic:"metrics", content:"metric tasks_active=1", status:"current"}

$8: ACTIVE_CONTEXT

WRK:current{name:"current", phase:"active", current:"initial", blocked:"no", survive:"work"}
"""


def _brain(tmp_path: Path) -> Path:
    brain_dir = tmp_path / ".arqux"
    brain_dir.mkdir()
    brain = brain_dir / "brain.cortex"
    brain.write_text(_BRAIN, encoding="utf-8")
    return brain


def _read_knw(brain: Path, name: str) -> list[dict]:
    from arqux.core.state import crud_read

    return [
        e for e in crud_read(brain, f"$6/KNW:{name}")["entries"]
        if e["name"] == name
    ]


def test_metrics_upsert_updates_existing_entry(tmp_path: Path) -> None:
    """Two syncs with the same metric → ONE KNW entry, value updated in place."""

    from arqux.sync import sync_brain

    brain = _brain(tmp_path)
    sync_brain(brain.parent, "event.one", metrics={"tasks_active": 5})
    sync_brain(brain.parent, "event.two", metrics={"tasks_active": 7})

    entries = _read_knw(brain, "tasks_active")
    assert len(entries) == 1, f"expected 1 upserted entry, got {len(entries)}"
    val = entries[0]["value"]
    assert val["value"] == "7"
    assert val["content"] == "metric tasks_active=7"
    assert val["updated"] != "old"


def test_metrics_upsert_appends_only_new_metrics(tmp_path: Path) -> None:
    from arqux.sync import sync_brain

    brain = _brain(tmp_path)
    sync_brain(brain.parent, "event.one", metrics={"tasks_active": 3, "handlers": 9})

    assert len(_read_knw(brain, "tasks_active")) == 1
    new_entries = _read_knw(brain, "handlers")
    assert len(new_entries) == 1
    assert new_entries[0]["value"]["value"] == "9"


def test_metrics_skipped_when_section_absent(tmp_path: Path) -> None:
    """create_section=False semantics: no $6 → metrics skipped, no crash."""
    from arqux.sync import sync_brain

    brain = _brain(tmp_path)
    text = brain.read_text(encoding="utf-8")
    text = text.replace(
        "$6: PULSE\n\nKNW:tasks_active{name:\"tasks_active\", value:\"1\", updated:\"old\", topic:\"metrics\", content:\"metric tasks_active=1\", status:\"current\"}\n\n",
        "",
    )
    assert "$6" not in text
    brain.write_text(text, encoding="utf-8")

    sync_brain(brain.parent, "event.one", metrics={"tasks_active": 5})
    assert "$6" not in brain.read_text(encoding="utf-8")


def test_sync_brain_single_rewrite_per_event(tmp_path: Path, monkeypatch) -> None:
    """WRK + FCS + metrics batch into ONE atomic rewrite per sync_brain call."""
    import arqux.cortex.atomic as atomic_mod
    from arqux.sync import sync_brain

    brain = _brain(tmp_path)

    writes = {"n": 0}
    real = atomic_mod.atomic_write_json

    def counting(doc, path, **kwargs):
        writes["n"] += 1
        return real(doc, path, **kwargs)

    monkeypatch.setattr(atomic_mod, "atomic_write_json", counting)
    sync_brain(
        brain.parent,
        "batch.event",
        focus="Batched focus",
        metrics={"tasks_active": 4},
    )
    assert writes["n"] == 1

    from arqux.core.state import crud_read

    wrk = crud_read(brain, "$8/WRK:current")["entries"][0]["value"]
    assert wrk["event"] == "batch.event"
    fcs = crud_read(brain, "$2/FCS:current")["entries"][0]["value"]
    assert fcs["what"] == "Batched focus"
    knw = _read_knw(brain, "tasks_active")
    assert len(knw) == 1
    assert knw[0]["value"]["value"] == "4"


def test_sync_brain_batch_preserves_focus_create_only(tmp_path: Path) -> None:
    """T-001 semantics survive the batch: existing FCS what preserved."""
    from arqux.sync import sync_brain

    brain = _brain(tmp_path)
    sync_brain(
        brain.parent,
        "batch.event",
        focus="Generic text",
        focus_create_only=True,
        metrics={"tasks_active": 2},
    )

    from arqux.core.state import crud_read

    fcs = crud_read(brain, "$2/FCS:current")["entries"][0]["value"]
    assert fcs["what"] == "Initial focus"
    assert fcs["event"] == "batch.event"
    assert len(_read_knw(brain, "tasks_active")) == 1


def test_meta_brain_synced_even_when_brain_mutations_fail(tmp_path: Path) -> None:
    """C2: all brain mutations fail ($2/$6/$8 absent) but metrics were passed —
    the meta-brain DOM must still be synced."""
    from arqux.core.state import crud_read
    from arqux.handlers import project, workspace
    from arqux.sync import sync_brain

    ws = tmp_path / "ws"
    ws.mkdir()
    proj = ws / "proj"
    proj.mkdir()
    workspace.init_workspace(path=str(ws), ctx=_CONTEXT)
    project.init_project(name="proj", path=str(proj), ctx=_CONTEXT)

    brain = proj / ".arqux" / "brain.cortex"
    brain.write_text("$0\n", encoding="utf-8")

    sync_brain(proj, "meta.event", metrics={"handlers": 3})

    meta = ws / ".arqux" / "meta-brain.cortex"
    dom = crud_read(meta, "$2/DOM:proj")["entries"]
    assert dom, "meta-brain DOM:proj not created"
    assert dom[0]["value"].get("last_event") == "meta.event"
