"""Tests for arqux.migrator — ARQX:artifact injection (BLP-041)."""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# migrate_file — core functionality
# ---------------------------------------------------------------------------


def test_migrate_injects_metadata(tmp_path) -> None:
    """migrate_file injects ARQX:artifact into a .cortex file."""
    from arqux.migrator import migrate_file

    f = tmp_path / "test.cortex"
    f.write_text("$0: test\n\n$1: SECTION\n\nbody here\n", encoding="utf-8")

    result = migrate_file(f, level=0, name="test-pkg", usage="config", kind="native")
    assert result is True
    content = f.read_text(encoding="utf-8")
    assert "ARQX:artifact" in content


def test_migrate_nonexistent_file(tmp_path) -> None:
    """migrate_file raises FileNotFoundError for missing file."""
    from arqux.migrator import migrate_file

    with pytest.raises(FileNotFoundError):
        migrate_file(tmp_path / "nonexistent.cortex", level=0, name="x", usage="config", kind="native")


def test_migrate_idempotent(tmp_path) -> None:
    """migrate_file returns False (no-op) on re-run."""
    from arqux.migrator import migrate_file

    f = tmp_path / "idempotent.cortex"
    f.write_text("$0: test\n\n$1: SECTION\n\nbody\n", encoding="utf-8")

    assert migrate_file(f, level=0, name="test-pkg", usage="config", kind="native") is True
    assert migrate_file(f, level=0, name="test-pkg", usage="config", kind="native") is False


# ---------------------------------------------------------------------------
# _inject_arqux_glossary_line
# ---------------------------------------------------------------------------


def test_inject_glossary_line_missing() -> None:
    """_inject_arqux_glossary_line adds ARQX glossary line when absent."""
    from arqux.migrator import _inject_arqux_glossary_line

    text = "$0\n# Sigil | Name | Type\n# AUD | aud | attrs"
    result = _inject_arqux_glossary_line(text)
    assert "ARQX" in result


def test_inject_glossary_line_already_present() -> None:
    """_inject_arqux_glossary_line returns text unchanged if ARQX present."""
    from arqux.migrator import _inject_arqux_glossary_line

    text = (
        "$0\n# ARQX | artifact | attrs\n# AUD | aud | attrs\n"
        'ARQX:arqx_contract{type:"attrs", open:true}\n'
    )
    result = _inject_arqux_glossary_line(text)
    assert result == text


def test_inject_glossary_line_adds_exec_decl() -> None:
    """Comment-only ARQX rows still need the executable contract (I001)."""
    from arqux.migrator import _inject_arqux_glossary_line

    text = "$0\n# ARQX | artifact | attrs\n# AUD | aud | attrs"
    result = _inject_arqux_glossary_line(text)
    assert "ARQX:arqx_contract{" in result


def test_inject_glossary_line_artifact_entry_is_not_a_declaration() -> None:
    """The ``ARQX:artifact`` data entry must not satisfy decl detection.

    A file carrying only the metadata entry still lacks the executable
    contract (I001_UNDECLARED_SYMBOL) — the injector must add it.
    """
    from arqux.migrator import _inject_arqux_glossary_line

    text = (
        "$0\n\n$19: ARQUX METADATA\n\n"
        'ARQX:artifact{level:0, name:"m", usage:"state", kind:"native"}\n'
    )
    result = _inject_arqux_glossary_line(text)
    assert "ARQX:arqx_contract{" in result


def test_inject_glossary_line_decl_lands_after_format() -> None:
    """The injected contract goes after ``$0:format`` when present."""
    from arqux.migrator import _inject_arqux_glossary_line

    text = "$0\n$0:format{cortex:1.0, encoding:UTF-8}\n\n$1: D\n"
    result = _inject_arqux_glossary_line(text)
    fmt_idx = result.index("$0:format")
    decl_idx = result.index("ARQX:arqx_contract")
    assert decl_idx > fmt_idx


def test_migrate_file_ensures_decl_when_metadata_present(tmp_path) -> None:
    """Metadata-bearing files still get the executable contract injected.

    The early-return path must repair a glossary missing the declaration,
    not just the pipe-table row.
    """
    from arqux.migrator import migrate_file

    f = tmp_path / "meta-only.cortex"
    f.write_text(
        "$0\n\n$19: ARQUX METADATA\n\n"
        'ARQX:artifact{level:0, name:"m", usage:"state", kind:"native"}\n',
        encoding="utf-8",
    )
    assert migrate_file(f, level=0, name="m", usage="state", kind="native") is True
    assert "ARQX:arqx_contract{" in f.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# migrate_identity_files
# ---------------------------------------------------------------------------


def test_migrate_identity_files(tmp_path) -> None:
    """migrate_identity_files migrates all .cortex files in directory."""
    from arqux.migrator import migrate_identity_files

    (tmp_path / "alfred.cortex").write_text(
        "$0: identity\n\n$1: IDENTITY\n", encoding="utf-8"
    )
    (tmp_path / "jarvis.cortex").write_text(
        "$0: identity\n\n$1: IDENTITY\n", encoding="utf-8"
    )

    results = migrate_identity_files(tmp_path)
    assert "alfred" in results
    assert "jarvis" in results
    assert results["alfred"] is True
    assert results["jarvis"] is True


def test_migrate_identity_files_not_dir(tmp_path) -> None:
    """migrate_identity_files raises NotADirectoryError for file path."""
    from arqux.migrator import migrate_identity_files

    f = tmp_path / "not_a_dir.cortex"
    f.write_text("test", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        migrate_identity_files(f)


# ---------------------------------------------------------------------------
# migrate_skill_file
# ---------------------------------------------------------------------------


def test_migrate_skill_file_inherited_requires_source() -> None:
    """migrate_skill_file raises ValueError for inherited without source."""
    from arqux.migrator import migrate_skill_file

    with pytest.raises(ValueError, match="source"):
        migrate_skill_file(Path("/tmp/x"), "test", "inherited")
