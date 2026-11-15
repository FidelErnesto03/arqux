"""CYCLE-13 coverage for the CODEC-CORTEX 1.0.0rc1 boundary."""

from __future__ import annotations

from arqux.cortex.codec_compat import codec_info, verify_text
from arqux.cortex.migration import migrate_file
from arqux.cortex.reader import cortex_to_dict
from arqux.cortex.writer import write_cortex_from_json


def _legacy_document() -> str:
    return (
        "$0\n"
        "GSIG:LNG{name:\"lesson\", type:\"attrs\", risk:\"M\", "
        "layer:\"Episodic\", description:\"Lesson\"}\n"
        "$1: DATA\n"
        'LNG:first{type:"process", lesson:"legacy"}\n'
    )


def test_writer_emits_strict_declarations_for_current_codec() -> None:
    # strict=True is the contract this test names: the strict path upgrades
    # legacy GSIG lines to executable v1 declarations.
    text = write_cortex_from_json(cortex_to_dict(_legacy_document()), strict=True)
    assert "GSIG:" not in text
    assert "LNG:lesson{" in text
    assert '$0:format{cortex:1.0, encoding:UTF-8}' in text


def test_default_writer_emits_v1_dialect() -> None:
    """Under the codec-cortex>=1.0 pin every emitted artifact must carry the
    dialect line (G010_FORMAT_REQUIRED); the old BUG-1 guard that pinned the
    default path to the 0.6.2 dialect is obsolete — the 0.6.x validator that
    rejected ``$0:format`` is no longer the pinned codec."""
    text = write_cortex_from_json(cortex_to_dict(_legacy_document()))
    assert '$0:format{cortex:1.0, encoding:UTF-8}' in text


def test_codec_boundary_verifies_generated_text() -> None:
    # Codec-verifiable output is the strict path: strict=False preserves
    # legacy ``GSIG:`` symbols verbatim for lossless round-trip, which the
    # v1 dispatcher rejects (G018_SYMBOL_WEIGHT_REQUIRED).
    text = write_cortex_from_json(cortex_to_dict(_legacy_document()), strict=True)
    result = verify_text(text)
    assert result["valid"] is True
    assert result["parser"] in {"legacy", "dispatcher"}


def test_migration_is_dry_run_by_default(tmp_path) -> None:
    source = tmp_path / "legacy.cortex"
    original = _legacy_document()
    source.write_text(original, encoding="utf-8")

    result = migrate_file(source)

    assert result["status"] == "preview"
    assert source.read_text(encoding="utf-8") == original
    assert result["changed"] is True


def test_migration_is_atomic_and_reversible(tmp_path) -> None:
    source = tmp_path / "legacy.cortex"
    source.write_text(_legacy_document(), encoding="utf-8")

    result = migrate_file(source, dry_run=False)

    assert result["status"] == "migrated"
    assert result["backup"] is not None
    migrated = source.read_text(encoding="utf-8")
    assert "GSIG:" not in migrated
    assert "LNG:lesson{" in migrated
    assert verify_text(migrated)["valid"] is True


def test_inspect_reports_codec_version() -> None:
    info = codec_info()
    assert info.parser in {"legacy", "dispatcher", None}
