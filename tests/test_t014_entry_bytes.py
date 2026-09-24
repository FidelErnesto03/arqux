"""Regression tests for T-014 — entry_bytes fidelity and bytes_written
semantics across sibling handlers.

Covers:
- entry.add: entry_bytes/bytes_written match the writer's serialized
  bytes on disk even when the input value is unquoted (the writer quotes
  attr strings via _serialise_attrs).
- entry.add: cuerpo (body) entries report the serialized multi-line form.
- entry.update/delete/move, cortex.gc, cortex.write: bytes_written is
  documented as whole-file size and file_bytes reports the same value,
  matching the file size on disk (additive file_bytes field).
"""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.cortex import (
    entry_add_handler,
    entry_delete_handler,
    entry_move_handler,
    entry_update_handler,
    gc_handler,
    write_handler,
)
from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test", role="governor")

_SAMPLE = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# OBJ   | objective  | attrs      | H | Working        | Active goal
# STP   | step       | attrs      | M | Working        | Step

$3: OBJECTIVES

OBJ:goal1{goal:"Test objective", status:"current"}

$5: STEPS

STP:one{step:"a"}
"""


def _file_bytes(f: Path) -> int:
    return len(f.read_text(encoding="utf-8").encode("utf-8"))


# ---------------------------------------------------------------------------
# entry_bytes fidelity
# ---------------------------------------------------------------------------


def test_entry_add_unquoted_value_entry_bytes_matches_disk(tmp_path: Path) -> None:
    """Unquoted attrs input: the writer quotes strings, so entry_bytes must
    be measured on the serialized (quoted) form, not the raw input."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    out = entry_add_handler(
        str(f), "$3", "OBJ", "newgoal", "goal:Retro, status:current",
        force=True, ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)

    disk_line = next(
        line for line in f.read_text(encoding="utf-8").splitlines()
        if line.startswith("OBJ:newgoal")
    )
    # The writer normalized the unquoted input to quoted attrs on disk.
    assert disk_line == 'OBJ:newgoal{goal:"Retro", status:"current"}'
    # entry_bytes/bytes_written equal the serialized bytes on disk.
    assert out.fields["entry_bytes"] == len(disk_line.encode("utf-8"))
    assert out.fields["bytes_written"] == out.fields["entry_bytes"]
    # And NOT the raw input rendering (which lacks the quotes).
    assert out.fields["entry_bytes"] != len(
        b"OBJ:newgoal{goal:Retro, status:current}"
    )
    assert out.fields["file_bytes"] == _file_bytes(f)


def test_entry_add_quoted_value_entry_bytes_unchanged(tmp_path: Path) -> None:
    """Already-quoted input serializes identically — entry_bytes still exact."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    value = 'goal:"Quoted", status:"current"'
    out = entry_add_handler(
        str(f), "$3", "OBJ", "quoted", value, force=True, ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    disk_line = next(
        line for line in f.read_text(encoding="utf-8").splitlines()
        if line.startswith("OBJ:quoted")
    )
    assert disk_line == f"OBJ:quoted{{{value}}}"
    assert out.fields["entry_bytes"] == len(disk_line.encode("utf-8"))


def test_entry_add_body_entry_bytes_matches_serialized_form(tmp_path: Path) -> None:
    """Cuerpo (body) values serialize as multi-line SIGIL:name{\\nbody\\n};
    entry_bytes must equal that serialized form."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    out = entry_add_handler(
        str(f), "$3", "OBJ", "body_entry", "plain free text body",
        force=True, ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    applied = out.fields["applied"]
    # The writer's serialized form appears verbatim in the file.
    assert applied in f.read_text(encoding="utf-8")
    assert out.fields["entry_bytes"] == len(applied.encode("utf-8"))
    assert out.fields["bytes_written"] == out.fields["entry_bytes"]


def test_entry_add_content_entry_bytes_matches_disk(tmp_path: Path) -> None:
    """content= (canal I) path: entry_bytes still tracks the on-disk bytes."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    out = entry_add_handler(
        str(f), "$3", "OBJ", "dummy",
        content='OBJ:from_content{goal:"C", status:"planned"}',
        force=True, ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    name = out.fields["name"]
    disk_line = next(
        line for line in f.read_text(encoding="utf-8").splitlines()
        if line.startswith(f"OBJ:{name}")
    )
    assert out.fields["entry_bytes"] == len(disk_line.encode("utf-8"))


# ---------------------------------------------------------------------------
# bytes_written semantics across siblings: file size (documented divergence)
# ---------------------------------------------------------------------------


def test_entry_update_reports_file_bytes(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    out = entry_update_handler(
        str(f), "OBJ:goal1", set_="status:done", force=True, ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["bytes_written"] == _file_bytes(f)
    assert out.fields["file_bytes"] == _file_bytes(f)


def test_entry_delete_reports_file_bytes(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    out = entry_delete_handler(str(f), "OBJ:goal1", force=True, ctx=_CONTEXT)
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["bytes_written"] == _file_bytes(f)
    assert out.fields["file_bytes"] == _file_bytes(f)


def test_entry_move_reports_file_bytes(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    out = entry_move_handler(str(f), "OBJ:goal1", "$5", force=True, ctx=_CONTEXT)
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["bytes_written"] == _file_bytes(f)
    assert out.fields["file_bytes"] == _file_bytes(f)


def test_gc_reports_file_bytes(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE + "\nSTP:one{step:\"dup\"}\nSTP:one{step:\"dup\"}\n")
    out = gc_handler(str(f), dry_run=False, force=True, ctx=_CONTEXT)
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["bytes_written"] == _file_bytes(f)
    assert out.fields["file_bytes"] == _file_bytes(f)


def test_cortex_write_reports_file_bytes(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    out = write_handler(str(f), _SAMPLE, force=True, ctx=_CONTEXT)
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["bytes_written"] == _file_bytes(f)
    assert out.fields["file_bytes"] == _file_bytes(f)


def test_schemas_document_bytes_written_semantics() -> None:
    """Each write/mutation handler schema documents its bytes_written metric."""
    from arqux.handlers.cortex import handler_schemas

    desc = {s["name"]: s["description"] for s in handler_schemas}
    for name in (
        "cortex.entry.add",
        "cortex.entry.update",
        "cortex.entry.delete",
        "cortex.entry.move",
        "cortex.gc",
        "cortex.write",
    ):
        assert "bytes_written" in desc[name], name
        assert "file_bytes" in desc[name], name
