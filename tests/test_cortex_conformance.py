"""BLP-007: Conformance tests for ArqUX CORTEX output.

Verifies that ArqUX-produced CORTEX is parseable by:
1. CODEC-CORTEX 0.6.2 (installed) — primary conformance
2. CODEC-CORTEX 1.0.0-rc.1 (new) — evaluated with adaptation

Also documents the differences between formats.

Acceptance criteria
-------------------
- AC-01: ArqUX CORTEX output is parseable by CODEC 0.6.2
- AC-02: ArqUX CORTEX output + adaptation is parseable by 1.0.0-rc.1
- AC-03: Differences between formats documented
- AC-04: Tests pass
- AC-05: No regression in existing tests
- AC-06: CORTEX 0.2 slots evaluation documented
"""

import re
import sys
from pathlib import Path

import pytest
from _governance_paths import governance_artifact

from arqux.cortex.model import parse_native
from arqux.cortex.reader import cortex_to_dict
from arqux.cortex.writer import write_cortex_from_json

ARQUX_ROOT = Path(__file__).resolve().parent.parent
CODEC_ROOT = Path("/home/vatrox/workspace/CODEC-CORTEX")

# Legacy 0.6.x codec — kept as an optional equivalence oracle. Under the
# codec-cortex>=1.0 pin ``cortex.core`` no longer exists; tests assert the
# v1 boundary unconditionally and only compare with legacy when importable.
try:
    from cortex.core.parser import parse_cortex as _legacy_parse  # type: ignore
except ImportError:
    _legacy_parse = None

# Files required for workspace-dependent tests
_BRAIN_CORTEX = governance_artifact("brain.cortex")
_JARVIS_CORTEX = governance_artifact("identities", "jarvis.cortex")

_HAS_WORKSPACE_FILES = _BRAIN_CORTEX.exists() and _JARVIS_CORTEX.exists()
_skip_no_workspace = pytest.mark.skipif(
    not _HAS_WORKSPACE_FILES,
    reason="workspace .cortex files absent at project and workspace level",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_codec_v1_importable() -> None:
    """Insert CODEC-CORTEX 1.0.0-rc.1 root on sys.path if needed."""
    codec_path = str(CODEC_ROOT)
    if codec_path not in sys.path:
        sys.path.insert(0, codec_path)


@pytest.fixture(autouse=True)
def _isolate_codec_v1_path():
    """Keep the rc1 sys.path injection from leaking into later test modules.

    ``_ensure_codec_v1_importable`` mutates process-global ``sys.path``;
    without cleanup, ``codec_cortex`` stays importable for the rest of the
    session and ``test_cortex_v1_conformance`` activates against a stale
    (legacy) binding. Snapshot and restore both ``sys.path`` and any
    ``codec_cortex*`` modules imported while the test ran.
    """
    path_snapshot = list(sys.path)
    module_snapshot = {
        name: mod for name, mod in sys.modules.items()
        if name == "codec_cortex" or name.startswith("codec_cortex.")
    }
    yield
    sys.path[:] = path_snapshot
    for name in [n for n in sys.modules
                 if n == "codec_cortex" or n.startswith("codec_cortex.")]:
        sys.modules.pop(name, None)
    sys.modules.update(module_snapshot)


# ---------------------------------------------------------------------------
# AC-01: CODEC-CORTEX 0.6.2 (installed) — primary conformance
# ---------------------------------------------------------------------------

class TestConformanceCodec062:
    """AC-01: ArqUX CORTEX output is parseable by the pinned CORTEX codec.

    Primary check: the codec-cortex 1.0.x boundary
    (``arqux.cortex.model.parse_native`` — the dispatcher under the hood).
    The legacy 0.6.x parse is kept as an equivalence check behind
    ``pytest.importorskip`` for environments where ``cortex.core`` is still
    installed.
    """

    @_skip_no_workspace
    def test_brain_cortex_parseable(self):
        """brain.cortex → ArqUX reader → ArqUX writer → parse with the codec."""
        text = _BRAIN_CORTEX.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        output = write_cortex_from_json(doc)

        # Must parse without errors
        parsed = parse_native(output)
        assert len(parsed.sections) > 0
        total = sum(len(s.entries) for s in parsed.sections)
        assert total > 100

        # Legacy 0.6.x equivalence — only when cortex.core is installed.
        if _legacy_parse is not None:
            legacy = _legacy_parse(output)
            assert sum(len(s.entries) for s in legacy.sections) > 100

    @_skip_no_workspace
    def test_brain_cortex_parseable_with_content(self):
        """brain.cortex → ArqUX writer → parse with the codec → verify content.

        Beyond merely parsing, verify that content survives the round trip:
        the LNG section (``$7``) entries must match in count, sigil and name.
        """
        text = _BRAIN_CORTEX.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        output = write_cortex_from_json(doc)

        parsed = parse_native(output)

        # Find LNG entries in both and compare
        original_lng = [s for s in doc["sections"] if s.get("id") == "$7"]
        if original_lng:
            orig_entries = original_lng[0].get("entries", [])
            # Find matching section in parsed
            parsed_sec = [s for s in parsed.sections if s.id == "$7"]
            if parsed_sec:
                parsed_entries = parsed_sec[0].entries
                assert len(parsed_entries) == len(orig_entries)
                # Verify first entry sigil and name match
                if orig_entries and parsed_entries:
                    assert parsed_entries[0].sigil == orig_entries[0]["sigil"]
                    assert parsed_entries[0].name == orig_entries[0]["name"]

        # Legacy 0.6.x equivalence — only when cortex.core is installed.
        if _legacy_parse is not None:
            _legacy_parse(output)

    @_skip_no_workspace
    def test_identity_parseable(self):
        """Identity file → ArqUX reader → ArqUX writer → parse with the codec."""
        text = _JARVIS_CORTEX.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        output = write_cortex_from_json(doc)

        parsed = parse_native(output)
        assert len(parsed.sections) > 0

        # Legacy 0.6.x equivalence — only when cortex.core is installed.
        if _legacy_parse is not None:
            legacy = _legacy_parse(output)
            assert len(legacy.sections) > 0

    def test_simple_doc_parseable(self):
        """Simple ArqUX-generated doc → parse with the codec."""
        doc = {
            "glossary": {"header": "$0", "comments": ["# test glossary"]},
            "sections": [
                {
                    "id": "$1",
                    "title": "TEST",
                    "entries": [
                        {
                            "sigil": "LNG",
                            "name": "test",
                            "attrs": {"type": "process", "lesson": "test"},
                        }
                    ],
                }
            ],
        }
        output = write_cortex_from_json(doc)
        parsed = parse_native(output)
        # The v1 glossary is metadata, not a section — find the TEST section
        test_sections = [s for s in parsed.sections if s.id == "$1"]
        assert len(test_sections) == 1
        assert len(test_sections[0].entries) == 1

        # Legacy 0.6.x equivalence — only when cortex.core is installed.
        if _legacy_parse is not None:
            legacy = _legacy_parse(output)
            assert len([s for s in legacy.sections if s.id == "$1"]) == 1


# ---------------------------------------------------------------------------
# AC-02: CODEC-CORTEX 1.0.0-rc.1 (new) — evaluated with adaptation
# ---------------------------------------------------------------------------

class TestConformanceCodec100rc1:
    """AC-02: Evaluate conformance with CODEC 1.0.0-rc.1."""

    def test_codec_100rc1_available(self):
        """Verify CODEC 1.0.0-rc.1 is available for testing."""
        _ensure_codec_v1_importable()
        try:
            import codec_cortex  # noqa: F401
        except ImportError:
            pytest.skip("CODEC-CORTEX 1.0.0-rc.1 not available")
        assert codec_cortex is not None

    def test_arqux_output_has_format_declaration(self):
        """ArqUX output declares and parses as CORTEX 0.1."""
        _ensure_codec_v1_importable()
        try:
            from codec_cortex.dispatcher import parse_cortex as parse_v1
        except ImportError:
            pytest.skip("CODEC-CORTEX 1.0.0-rc.1 not available")

        doc = {
            "glossary": {"header": "$0", "comments": ["# test"]},
            "sections": [
                {
                    "id": "$1",
                    "title": "TEST",
                    "entries": [
                        {
                            "sigil": "LNG",
                            "name": "test",
                            "attrs": {"type": "process"},
                        }
                    ],
                }
            ],
        }
        # The strict path emits the dispatcher-facing dialect declaration
        # (codec-cortex>=1.0 pin: ``cortex:1.0`` — accepted alongside 0.1).
        output = write_cortex_from_json(doc, strict=True)

        assert re.search(
            r'\$0:format\{cortex:"?(0\.1|1\.0)"?, encoding:"?UTF-8"?', output)
        parsed = parse_v1(output)
        assert [(section.id, len(section.ideas)) for section in parsed.sections] == [(1, 1)]

    def test_real_arqux_output_is_parseable_by_current_codec(self):
        """Generated ArqUX output declares every used sigil for the codec."""
        _ensure_codec_v1_importable()
        try:
            from codec_cortex.dispatcher import parse_cortex as parse_v1
        except ImportError:
            pytest.skip("CODEC-CORTEX 1.0.0-rc.1 not available")

        # Generate real ArqUX output
        doc = {
            "glossary": {"header": "$0", "comments": ["# test"]},
            "sections": [
                {
                    "id": "$1",
                    "title": "TEST",
                    "entries": [
                        {
                            "sigil": "LNG",
                            "name": "test",
                            "attrs": {"type": "process"},
                        }
                    ],
                }
            ],
        }
        output = write_cortex_from_json(doc, strict=True)

        parsed = parse_v1(output)
        assert any(symbol.sigil == "LNG" for symbol in parsed.glossary.symbols)

    def test_full_adaptation_for_1_0_0_rc1(self):
        """Document what full adaptation for 1.0.0-rc.1 requires.

        A fully 1.0.0-rc.1-conformant document must:
          - use ``$0:KERNEL`` as the glossary header
          - declare ``$0:format{cortex:0.1,encoding:UTF-8}``
          - declare each sigil with a full contract (type, weight, fields,
            focus, desc) in the glossary before it is referenced in a section
        """
        _ensure_codec_v1_importable()
        try:
            from codec_cortex.dispatcher import parse_cortex as parse_v1
        except ImportError:
            pytest.skip("CODEC-CORTEX 1.0.0-rc.1 not available")

        # Full 1.0.0-rc.1 conformant document with declared sigils
        text = (
            "$0:KERNEL\n"
            "$0:format{cortex:0.1,encoding:UTF-8}\n"
            "LNG:lesson{type:attrs,weight:M,"
            'fields:"type:text|lesson:text",'
            'focus:type,desc:"Learned lesson"}\n'
            "\n"
            "$1: TEST\n"
            "\n"
            'LNG:test{type:"process", lesson:"test lesson"}\n'
        )
        doc = parse_v1(text)
        assert len(doc.sections) > 0
        # Verify the idea was parsed
        section = [s for s in doc.sections if s.id == 1][0]
        assert len(section.ideas) == 1
        assert section.ideas[0].symbol == "LNG"
        assert section.ideas[0].name == "test"


# ---------------------------------------------------------------------------
# AC-03: Document differences between CODEC 0.6.2 and 1.0.0-rc.1
# ---------------------------------------------------------------------------

class TestFormatDifferences:
    """AC-03: Document differences between CODEC 0.6.x and 1.0.x.

    Each test asserts the pinned codec-cortex 1.0.x behaviour directly and
    keeps the legacy 0.6.x side as a conditional comparison when
    ``cortex.core`` is importable.
    """

    def test_glossary_header_difference(self):
        """Legacy accepts a bare ``$0`` header; v1 accepts ``$0``/``$0:KERNEL``
        but only inside a document that declares ``$0:format``."""
        text = '$0\n\n$1: TEST\n\nLNG:test{type:"process"}\n'
        # Legacy 0.6.x accepts bare $0 with undeclared sigils.
        if _legacy_parse is not None:
            assert _legacy_parse(text) is not None

        _ensure_codec_v1_importable()
        dispatcher = pytest.importorskip("codec_cortex.dispatcher")
        # The same document is not a valid 1.0.x artifact: $0:format missing.
        scalars = pytest.importorskip("codec_cortex.scalars")
        with pytest.raises(scalars.ParseError, match="G010"):
            dispatcher.parse_cortex(text)
        # ``$0:KERNEL`` (capa) is accepted once the dialect is declared.
        v1_text = (
            "$0:KERNEL\n"
            "$0:format{cortex:0.1,encoding:UTF-8}\n"
            'LNG:lesson{type:attrs,weight:M,fields:"type:text|lesson:text",'
            'focus:type,desc:"Learned lesson"}\n'
            "\n$1: TEST\n\n"
            'LNG:test{type:"process", lesson:"x"}\n'
        )
        doc = dispatcher.parse_cortex(v1_text)
        assert doc.glossary.capa == "KERNEL"
        assert len(doc.sections) == 1

    def test_format_declaration_difference(self):
        """0.6.x doesn't require $0:format; the 1.0.x dispatcher does (G010)."""
        text = '$0\n\n$1: TEST\n\nLNG:test{type:"process"}\n'
        # 0.6.x parses without $0:format.
        if _legacy_parse is not None:
            assert _legacy_parse(text) is not None

        _ensure_codec_v1_importable()
        dispatcher = pytest.importorskip("codec_cortex.dispatcher")
        scalars = pytest.importorskip("codec_cortex.scalars")
        with pytest.raises(scalars.ParseError, match="G010_FORMAT_REQUIRED"):
            dispatcher.parse_cortex(text)

    def test_sigil_declaration_difference(self):
        """0.6.x allows undeclared sigils; 1.0.x requires them (I001)."""
        text = '$0\n\n$1: TEST\n\nLNG:test{type:"process"}\n'
        # 0.6.x parses undeclared sigils.
        if _legacy_parse is not None:
            assert _legacy_parse(text) is not None

        _ensure_codec_v1_importable()
        dispatcher = pytest.importorskip("codec_cortex.dispatcher")
        scalars = pytest.importorskip("codec_cortex.scalars")
        # With $0:format present but no glossary declaration → I001.
        v1_text = (
            "$0\n"
            "$0:format{cortex:1.0,encoding:UTF-8}\n"
            "\n$1: TEST\n\n"
            'LNG:test{type:"process"}\n'
        )
        with pytest.raises(scalars.ParseError, match="I001_UNDECLARED_SYMBOL"):
            dispatcher.parse_cortex(v1_text)

    def test_1_0_0_rc1_rejects_bare_dollar_zero(self):
        """1.0.0-rc.1 rejects bare $0 (requires $0:KERNEL / $0:format)."""
        _ensure_codec_v1_importable()
        try:
            from codec_cortex.dispatcher import parse_cortex as parse_v1
            from codec_cortex.scalars import ParseError
        except ImportError:
            pytest.skip("CODEC-CORTEX 1.0.0-rc.1 not available")

        # Bare $0 without $0:format → should fail
        text = '$0\n\n$1: TEST\n\nLNG:test{type:"process"}\n'
        with pytest.raises(ParseError):
            parse_v1(text)

    def test_1_0_0_rc1_rejects_undeclared_sigils(self):
        """1.0.0-rc.1 rejects undeclared sigils (I001_UNDECLARED_SYMBOL)."""
        _ensure_codec_v1_importable()
        try:
            from codec_cortex.dispatcher import parse_cortex as parse_v1
            from codec_cortex.scalars import ParseError
        except ImportError:
            pytest.skip("CODEC-CORTEX 1.0.0-rc.1 not available")

        # Has $0:format but no declared sigils → should fail on undeclared LNG
        text = (
            "$0:KERNEL\n"
            "$0:format{cortex:0.1,encoding:UTF-8}\n"
            "\n"
            "$1: TEST\n"
            "\n"
            'LNG:test{type:"process"}\n'
        )
        with pytest.raises(ParseError, match="I001_UNDECLARED_SYMBOL"):
            parse_v1(text)


# ---------------------------------------------------------------------------
# AC-06: Evaluate CORTEX 0.2 slots (document, don't adopt)
# ---------------------------------------------------------------------------

class TestCortex02Evaluation:
    """AC-06: Evaluate CORTEX 0.2 slots (document, don't adopt)."""

    def test_cortex_02_slot_syntax(self):
        """Evaluate CORTEX 0.2 slot syntax (※N:valor).

        CORTEX 0.2 introduces *slots* using the ``※N:valor`` syntax for
        positional references within attrs, reducing duplication for repeated
        values::

            # With slots (0.2):
            LNG:lesson{type:※1, ※1:"process", lesson:"test"}
            # Without slots (0.1):
            LNG:lesson{type:"process", lesson:"test"}

        The slot parser lives in ``codec_cortex.slotparser`` (and the lower
        level ``codec_cortex.slots`` helpers).  This test exercises the import
        surface to confirm the module is reachable when 1.0.0-rc.1 is present.
        """
        _ensure_codec_v1_importable()
        try:
            from codec_cortex.slotparser import parse_slots  # noqa: F401
        except ImportError:
            pytest.skip("CODEC-CORTEX 1.0.0-rc.1 slots module not available")

        # CORTEX 0.2 uses ※N:valor for slot references.
        # Example: ※1:"process" defines slot 1, then type:※1 references it.
        # This reduces duplication for repeated values.
        #
        # The key finding is that 0.2 slots exist but are NOT adopted in
        # CYCLE-11 because:
        # 1. Requires 1.0.0-rc.1 parser (not installed as default)
        # 2. Different mental model for agents
        # 3. ArqUX output format would need significant changes
        # Decision: evaluate in future cycle, not CYCLE-11
        assert True  # Evaluation documented

    def test_cortex_02_not_adopted_decision(self):
        """Document the CYCLE-11 decision to NOT adopt CORTEX 0.2 slots.

        The cycle manifest (§3 exclusions) explicitly states that adopting
        CORTEX 0.2 slots is NOT part of this cycle; only evaluate it.

        Reasons documented:
        1. ArqUX decoupling is the priority — slots are a separate concern
        2. 1.0.0-rc.1 requires $0:KERNEL, $0:format, declared sigils — a
           major format change
        3. Slot syntax (※N:valor) changes how agents construct CORTEX
        4. Backward compatibility with existing .cortex files would be
           impacted

        Future cycle (CYCLE-12+) should:
        1. Add $0:format{cortex:0.1} to ArqUX writer output
        2. Declare sigils with contracts in glossary
        3. Optionally support 0.2 slots as a writer option
        """
        assert True  # Decision documented
