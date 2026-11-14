"""T-1.18 (BLP-001 ampliacion A) — ARQX metadata resolves from either section.

CORTEX 1.0 forbids a sub-section of the glossary (G004), so migrated artifacts
carry ``ARQX:artifact`` in ``$1`` instead of ``$0.1``. Both must resolve to the
same ``ArtifactMetadata``: the moment one stops resolving, the artifact silently
degrades to NIVEL 0 (W001_NO_METADATA) and an agent boots without a contract.
"""
from __future__ import annotations

from arqux.constants import ArtifactKind, ArtifactUsage, CortexLevel
from arqux.formats import read_arqux_metadata

LEGACY_DOC = """$0

# ARQX | artifact | attrs | B | Semantic

$0.1: ARQUX METADATA

ARQX:artifact{level:1, name:"probe", usage:"identity", kind:"native"}


$1: IDENTITY

IDN:probe{name:"Probe", role:"assistant", status:"current"}
"""

V1_DOC = """$0

# ARQX | artifact | attrs | B | Semantic

$1: IDENTITY

ARQX:artifact{level:1, name:"probe", usage:"identity", kind:"native"}

IDN:probe{name:"Probe", role:"assistant", status:"current"}
"""


def _assert_metadata(md, *, where: str) -> None:
    assert md.level is CortexLevel.BEHAVIORAL, f"{where}: level={md.level}"
    assert md.name == "probe", f"{where}: name={md.name}"
    assert md.usage is ArtifactUsage.IDENTITY, f"{where}: usage={md.usage}"
    assert md.kind is ArtifactKind.NATIVE, f"{where}: kind={md.kind}"


def test_metadata_resolves_from_legacy_section():
    """Metadata in $0.1 (BLP-041) still resolves — backward compatibility."""
    _assert_metadata(read_arqux_metadata(LEGACY_DOC), where="$0.1")


def test_metadata_resolves_from_identity_section():
    """Metadata in $1 resolves — the CORTEX 1.0 location (G004)."""
    _assert_metadata(read_arqux_metadata(V1_DOC), where="$1")


def test_both_sections_yield_identical_metadata():
    """The two layouts are equivalent: no artifact changes level when migrated."""
    legacy = read_arqux_metadata(LEGACY_DOC)
    v1 = read_arqux_metadata(V1_DOC)
    assert legacy.to_dict() == v1.to_dict()


def test_missing_metadata_degrades_to_package():
    """Control: without metadata the artifact degrades — the failure A prevents."""
    md = read_arqux_metadata("$0\n\n$1: IDENTITY\n\nIDN:x{name:\"x\"}\n")
    assert md.level is CortexLevel.PACKAGE
    assert md.name == "<unknown>"
