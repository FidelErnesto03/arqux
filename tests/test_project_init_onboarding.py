"""Regression tests for project onboarding (BLP-007 / BUG-005).

BUG-005 (workspace issue): incorporating a new project via ``project.init``
exposed six deficiencies — an invalid seeded brain (E024/E034), a false
``registered_in_workspace=true`` (plain line instead of a ``DOM:`` entry),
silent ``_XXXX`` renames in ``cortex.entry.add``, a seeding guide that
contradicts the validator schema, a read-only ``cortex.ref`` that writes
AUD entries, and no valid level-2 brain template.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from arqux.constants import ARQUX_DIR
from arqux.handlers import project, workspace
from arqux.handlers.cortex.entries import entry_add_handler
from arqux.handlers.cortex.ref import ref_handler
from arqux.state import cortex_verify, crud_read

_SAMPLE = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# DOM   | domain     | attrs      | B | Semantic       | Domain descriptor
# IDN   | identity   | attrs      | B | Semantic       | Identity
# FCS   | focus      | attrs      | H | Working        | Focus
# OBJ   | objective  | attrs      | H | Working        | Objective
# WRK   | work       | attrs      | B | Working        | Work state


$1: METADATA

IDN:test{name:"sample"}

$2: FOCUS

FCS:current{what:"test", priority:"low", status:"current", survive:"work"}

$3: OBJECTIVES

OBJ:main{goal:"exist", status:"current", success:"verified", survive:"work"}
"""


def _init_project_in_workspace(workspace_root: Path, governor_ctx, name: str = "mi_app") -> Path:
    """Create a governed workspace + a fresh project dir inside it."""
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    proj_dir = workspace_root / name
    proj_dir.mkdir()
    return proj_dir


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_init_produces_valid_brain(workspace_root: Path, governor_ctx) -> None:
    """AC-01: ``project.init`` without seed produces a brain.cortex that
    passes ``cortex.verify`` (no E024/E034 — FCS and OBJ present)."""
    proj = _init_project_in_workspace(workspace_root, governor_ctx)
    result = project.init_project(name="mi_app", path=str(proj), ctx=governor_ctx)
    assert result.profile == "OUT-WORK", str(result.fields)

    brain = proj / ARQUX_DIR / "brain.cortex"
    assert brain.exists()
    check = cortex_verify(brain)
    errors = [d for d in check["diagnostics"] if "E0" in d]
    assert check["valid"], f"seeded brain invalid: {check['diagnostics']}"
    assert not any("E024" in d or "E034" in d for d in errors)


def test_init_registers_dom_entry(workspace_root: Path, governor_ctx) -> None:
    """AC-02: registration writes a real ``DOM:<name>`` entry into the
    workspace ``projects.cortex`` (not a raw text line)."""
    proj = _init_project_in_workspace(workspace_root, governor_ctx)
    result = project.init_project(name="mi_app", path=str(proj), ctx=governor_ctx)
    assert result.profile == "OUT-WORK", str(result.fields)
    assert result.fields.get("registered_in_workspace") is True

    projects_cortex = workspace_root / ARQUX_DIR / "projects.cortex"
    assert projects_cortex.exists(), "projects.cortex must exist after registration"
    read = crud_read(projects_cortex, "DOM:mi_app")
    names = [e["name"] for e in read["entries"] if e["sigil"] == "DOM"]
    assert "mi_app" in names, f"DOM entry missing; found {names}"


def test_init_reports_unregistered_honestly(tmp_path: Path, governor_ctx) -> None:
    """AC-02b: a project outside any workspace reports
    ``registered_in_workspace=False`` — never a false success."""
    proj = tmp_path / "outside" / "mi_app"
    proj.mkdir(parents=True)
    result = project.init_project(name="mi_app", path=str(proj), ctx=governor_ctx)
    assert result.profile == "OUT-WORK", str(result.fields)
    assert result.fields.get("registered_in_workspace") is False


def test_entry_add_keeps_requested_name(tmp_path: Path) -> None:
    """AC-03a: without a collision, ``entry.add`` stores the entry under the
    requested name — no gratuitous ``_XXXX`` suffix."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE, encoding="utf-8")
    add = entry_add_handler(
        str(f), "$1", "DOM", "mi_app",
        'name:"Mi App", path:"/tmp/mi_app", status:"current"',
        force=True,
    )
    assert add.profile == "OUT-WORK", str(add.fields)
    assert add.fields.get("name") == "mi_app", (
        f"entry renamed without collision: {add.fields.get('name')}"
    )
    read = crud_read(f, "$1/DOM:mi_app")
    assert any(e["name"] == "mi_app" for e in read["entries"])


def test_entry_add_reports_rename_on_collision(tmp_path: Path) -> None:
    """AC-03b: on collision, ``entry.add`` suffixes ``_NNNN`` AND reports the
    rename explicitly (``renamed``/``requested`` fields in OUT-WORK)."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE, encoding="utf-8")
    first = entry_add_handler(
        str(f), "$1", "DOM", "mi_app",
        'name:"Mi App", path:"/tmp/a", status:"current"',
        force=True,
    )
    assert first.profile == "OUT-WORK", str(first.fields)

    second = entry_add_handler(
        str(f), "$1", "DOM", "mi_app",
        'name:"Mi App 2", path:"/tmp/b", status:"current"',
        force=True,
    )
    assert second.profile == "OUT-WORK", str(second.fields)
    assigned = second.fields.get("name", "")
    assert assigned != "mi_app", "collision should produce a distinct name"
    assert second.fields.get("renamed") or second.fields.get("requested"), (
        f"rename not reported explicitly: {second.fields}"
    )


def test_cortex_ref_is_readonly(workspace_root: Path, governor_ctx) -> None:
    """AC-04: ``cortex.ref`` must not mutate the target brain — byte-identical
    before/after (currently writes AUD:E_* into PULSE)."""
    proj = _init_project_in_workspace(workspace_root, governor_ctx)
    project.init_project(name="mi_app", path=str(proj), ctx=governor_ctx)
    brain = proj / ARQUX_DIR / "brain.cortex"
    before = _sha256(brain)

    result = ref_handler("WRK", path=str(proj), ctx=governor_ctx)
    assert result.profile == "OUT-WORK", str(result.fields)
    assert _sha256(brain) == before, "cortex.ref mutated the brain file"


def test_seed_guide_matches_validator_schema(workspace_root: Path, governor_ctx) -> None:
    """AC-05: the ``STP:build_brain`` guide names the fields the validator
    actually requires (KNW: topic/content/status; RSK: survive)."""
    proj = _init_project_in_workspace(workspace_root, governor_ctx)
    result = project.init_project(name="mi_app", path=str(proj), ctx=governor_ctx)
    assert result.profile == "OUT-WORK", str(result.fields)
    guide = result.message
    assert "KNW" in guide and "topic" in guide and "content" in guide and "status" in guide, (
        "seed guide does not list the KNW{topic,content,status} schema"
    )
    assert "RSK" in guide and "survive" in guide, (
        "seed guide does not list the RSK{survive,...} schema"
    )
