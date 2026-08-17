"""Tests for BLP-004: arqux.cortex.reader — cortex_to_dict.

Covers:
  1. Parse simple CORTEX with one section + one attrs entry
  2. Parse multiple sections
  3. Parse cuerpo entries (multi-line body)
  4. Parse glossary with comments
  5. Parse comments within sections
  6. Round-trip: cortex_to_dict → write_cortex_from_json → cortex_to_dict
  7. Fallback parser (mock CODEC-CORTEX as unavailable)
  8. Empty document
  9. Real .cortex file (use a small fixture)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from arqux.cortex.reader import cortex_to_dict
from arqux.cortex.writer import write_cortex_from_json

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_CORTEX = """\
$0

$1: TEST

LNG:test{type:"process"}
"""

MULTI_SECTION_CORTEX = """\
$0

$1: FIRST

LNG:alpha{type:"process"}

$2: SECOND

ARQX:beta{level:"2"}
"""

CUERPO_CORTEX = """\
$0
GSIG:AXM{name:axiom, type:cuerpo, risk:H, layer:Prefrontal}

$1: RULES

AXM:rule1{
Step 1
Step 2
}
"""

GLOSSARY_COMMENTS_CORTEX = """\
$0
# This is a glossary comment
# Another comment

$1: TEST

LNG:test{type:"process"}
"""

SECTION_COMMENTS_CORTEX = """\
$0

$1: TEST
# Section comment 1
# Section comment 2

LNG:test{type:"process"}
"""

EMPTY_CORTEX = ""

REAL_FIXTURE = """\
$0
# Arqux governance kernel
# Sigil glossary

$1: METADATA

ARQX:artifact{level:"2", status:"active"}

$2: RULES

AXM:rule1{
Every agent must verify handlers.
No MCP means halt.
}
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSimpleParse:
    """Test 1: Parse simple CORTEX with one section + one attrs entry."""

    def test_one_section_one_attrs_entry(self):
        doc = cortex_to_dict(SIMPLE_CORTEX)
        assert "glossary" in doc
        assert "sections" in doc
        sections = doc["sections"]
        assert len(sections) == 1
        sec = sections[0]
        assert sec["id"] == "$1"
        assert sec["title"] == "TEST"
        entries = sec["entries"]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["sigil"] == "LNG"
        assert entry["name"] == "test"
        assert "attrs" in entry
        assert entry["attrs"]["type"] == "process"

    def test_glossary_header(self):
        doc = cortex_to_dict(SIMPLE_CORTEX)
        assert doc["glossary"]["header"] == "$0"


class TestMultipleSections:
    """Test 2: Parse multiple sections."""

    def test_two_sections(self):
        doc = cortex_to_dict(MULTI_SECTION_CORTEX)
        sections = doc["sections"]
        assert len(sections) == 2
        assert sections[0]["id"] == "$1"
        assert sections[0]["title"] == "FIRST"
        assert sections[1]["id"] == "$2"
        assert sections[1]["title"] == "SECOND"

    def test_entries_in_multiple_sections(self):
        doc = cortex_to_dict(MULTI_SECTION_CORTEX)
        assert len(doc["sections"][0]["entries"]) == 1
        assert len(doc["sections"][1]["entries"]) == 1
        assert doc["sections"][0]["entries"][0]["sigil"] == "LNG"
        assert doc["sections"][1]["entries"][0]["sigil"] == "ARQX"


class TestCuerpoEntries:
    """Test 3: Parse cuerpo entries (multi-line body)."""

    def test_cuerpo_body_extracted(self):
        doc = cortex_to_dict(CUERPO_CORTEX)
        sections = doc["sections"]
        assert len(sections) == 1
        entries = sections[0]["entries"]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["sigil"] == "AXM"
        assert entry["name"] == "rule1"
        assert "body" in entry
        assert "Step 1" in entry["body"]
        assert "Step 2" in entry["body"]

    def test_cuerpo_body_not_attrs(self):
        doc = cortex_to_dict(CUERPO_CORTEX)
        entry = doc["sections"][0]["entries"][0]
        assert "attrs" not in entry


class TestGlossaryComments:
    """Test 4: Parse glossary with comments."""

    def test_glossary_comments_captured(self):
        doc = cortex_to_dict(GLOSSARY_COMMENTS_CORTEX)
        comments = doc["glossary"]["comments"]
        assert len(comments) == 2
        assert "# This is a glossary comment" in comments
        assert "# Another comment" in comments

    def test_glossary_no_entries_in_sections(self):
        doc = cortex_to_dict(GLOSSARY_COMMENTS_CORTEX)
        # $0 should not appear in sections
        for sec in doc["sections"]:
            assert sec["id"] != "$0"


class TestSectionComments:
    """Test 5: Parse comments within sections."""

    def test_section_comments_captured(self):
        doc = cortex_to_dict(SECTION_COMMENTS_CORTEX)
        sec = doc["sections"][0]
        comments = sec.get("comments", [])
        assert "# Section comment 1" in comments
        assert "# Section comment 2" in comments


class TestRoundTrip:
    """Test 6: Round-trip cortex_to_dict → write_cortex_from_json → cortex_to_dict."""

    def test_roundtrip_simple(self):
        doc1 = cortex_to_dict(SIMPLE_CORTEX)
        text = write_cortex_from_json(doc1)
        doc2 = cortex_to_dict(text)
        # Compare sections and entries
        assert len(doc1["sections"]) == len(doc2["sections"])
        for s1, s2 in zip(doc1["sections"], doc2["sections"], strict=False):
            assert s1["id"] == s2["id"]
            assert s1["title"] == s2["title"]
            assert len(s1["entries"]) == len(s2["entries"])
            for e1, e2 in zip(s1["entries"], s2["entries"], strict=False):
                assert e1["sigil"] == e2["sigil"]
                assert e1["name"] == e2["name"]

    def test_roundtrip_attrs_preserved(self):
        doc1 = cortex_to_dict(SIMPLE_CORTEX)
        text = write_cortex_from_json(doc1)
        doc2 = cortex_to_dict(text)
        e1 = doc1["sections"][0]["entries"][0]
        e2 = doc2["sections"][0]["entries"][0]
        assert e1["attrs"]["type"] == e2["attrs"]["type"]

    def test_roundtrip_multi_section(self):
        doc1 = cortex_to_dict(MULTI_SECTION_CORTEX)
        text = write_cortex_from_json(doc1)
        doc2 = cortex_to_dict(text)
        assert len(doc1["sections"]) == len(doc2["sections"])
        assert len(doc2["sections"]) == 2

    def test_roundtrip_cuerpo(self):
        doc1 = cortex_to_dict(CUERPO_CORTEX)
        text = write_cortex_from_json(doc1)
        doc2 = cortex_to_dict(text)
        e1 = doc1["sections"][0]["entries"][0]
        e2 = doc2["sections"][0]["entries"][0]
        assert e1["sigil"] == e2["sigil"]
        assert e1["name"] == e2["name"]
        assert "body" in e2
        assert "Step 1" in e2["body"]
        assert "Step 2" in e2["body"]

    def test_roundtrip_real_fixture(self):
        doc1 = cortex_to_dict(REAL_FIXTURE)
        text = write_cortex_from_json(doc1)
        doc2 = cortex_to_dict(text)
        assert len(doc1["sections"]) == len(doc2["sections"])
        # Check entries count preserved
        total1 = sum(len(s["entries"]) for s in doc1["sections"])
        total2 = sum(len(s["entries"]) for s in doc2["sections"])
        assert total1 == total2


class TestFallbackParser:
    """Test 7: Fallback parser (mock CODEC-CORTEX as unavailable)."""

    def test_fallback_parses_section(self):
        with patch("arqux.cortex.reader._PARSER", None):
            doc = cortex_to_dict(SIMPLE_CORTEX)
        assert len(doc["sections"]) == 1
        assert doc["sections"][0]["id"] == "$1"
        assert doc["sections"][0]["title"] == "TEST"

    def test_fallback_parses_attrs_entry(self):
        with patch("arqux.cortex.reader._PARSER", None):
            doc = cortex_to_dict(SIMPLE_CORTEX)
        entry = doc["sections"][0]["entries"][0]
        assert entry["sigil"] == "LNG"
        assert entry["name"] == "test"
        assert entry["attrs"]["type"] == "process"

    def test_fallback_parses_multiple_sections(self):
        with patch("arqux.cortex.reader._PARSER", None):
            doc = cortex_to_dict(MULTI_SECTION_CORTEX)
        assert len(doc["sections"]) == 2

    def test_fallback_parses_cuerpo(self):
        with patch("arqux.cortex.reader._PARSER", None):
            doc = cortex_to_dict(CUERPO_CORTEX)
        entry = doc["sections"][0]["entries"][0]
        assert entry["sigil"] == "AXM"
        assert entry["name"] == "rule1"
        assert "body" in entry
        assert "Step 1" in entry["body"]

    def test_fallback_parses_glossary_comments(self):
        with patch("arqux.cortex.reader._PARSER", None):
            doc = cortex_to_dict(GLOSSARY_COMMENTS_CORTEX)
        comments = doc["glossary"]["comments"]
        assert "# This is a glossary comment" in comments

    def test_fallback_parses_section_comments(self):
        with patch("arqux.cortex.reader._PARSER", None):
            doc = cortex_to_dict(SECTION_COMMENTS_CORTEX)
        sec = doc["sections"][0]
        comments = sec.get("comments", [])
        assert "# Section comment 1" in comments

    def test_fallback_roundtrip(self):
        with patch("arqux.cortex.reader._PARSER", None):
            doc1 = cortex_to_dict(SIMPLE_CORTEX)
            text = write_cortex_from_json(doc1)
            doc2 = cortex_to_dict(text)
        assert len(doc1["sections"]) == len(doc2["sections"])
        e1 = doc1["sections"][0]["entries"][0]
        e2 = doc2["sections"][0]["entries"][0]
        assert e1["sigil"] == e2["sigil"]
        assert e1["name"] == e2["name"]


class TestEmptyDocument:
    """Test 8: Empty document."""

    def test_empty_string(self):
        doc = cortex_to_dict("")
        assert doc["glossary"]["header"] == "$0"
        assert doc["glossary"]["comments"] == []
        assert doc["sections"] == []

    def test_whitespace_only(self):
        doc = cortex_to_dict("   \n\n  \n")
        assert doc["glossary"]["header"] == "$0"
        assert doc["sections"] == []

    def test_just_glossary(self):
        doc = cortex_to_dict("$0\n")
        assert doc["glossary"]["header"] == "$0"
        assert doc["sections"] == []


class TestRealFixture:
    """Test 9: Real .cortex file (small fixture)."""

    def test_real_fixture_sections(self):
        doc = cortex_to_dict(REAL_FIXTURE)
        assert len(doc["sections"]) == 2
        assert doc["sections"][0]["id"] == "$1"
        assert doc["sections"][0]["title"] == "METADATA"
        assert doc["sections"][1]["id"] == "$2"
        assert doc["sections"][1]["title"] == "RULES"

    def test_real_fixture_attrs_entry(self):
        doc = cortex_to_dict(REAL_FIXTURE)
        entry = doc["sections"][0]["entries"][0]
        assert entry["sigil"] == "ARQX"
        assert entry["name"] == "artifact"
        assert entry["attrs"]["level"] == "2"
        assert entry["attrs"]["status"] == "active"

    def test_real_fixture_cuerpo_entry(self):
        doc = cortex_to_dict(REAL_FIXTURE)
        entry = doc["sections"][1]["entries"][0]
        assert entry["sigil"] == "AXM"
        assert entry["name"] == "rule1"
        assert "body" in entry
        assert "Every agent must verify handlers." in entry["body"]

    def test_real_fixture_glossary_comments(self):
        doc = cortex_to_dict(REAL_FIXTURE)
        comments = doc["glossary"]["comments"]
        assert any("Arqux governance kernel" in c for c in comments)

    def test_real_fixture_from_file(self, tmp_path):
        """Write fixture to file, read it back."""
        p = tmp_path / "test.cortex"
        p.write_text(REAL_FIXTURE, encoding="utf-8")
        text = p.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        assert len(doc["sections"]) == 2


class TestEdgeCases:
    """Additional edge case tests."""

    def test_non_string_input_raises(self):
        with pytest.raises(ValueError, match="Expected str"):
            cortex_to_dict(123)

    def test_none_input_raises(self):
        with pytest.raises(ValueError, match="Expected str"):
            cortex_to_dict(None)  # type: ignore[arg-type]

    def test_attrs_with_integer_value(self):
        text = "$0\n\n$1: TEST\n\nTIE:nano{window:8}\n"
        doc = cortex_to_dict(text)
        entry = doc["sections"][0]["entries"][0]
        assert entry["attrs"]["window"] == 8

    def test_attrs_with_boolean_value(self):
        text = '$0\n\n$1: TEST\n\nLNG:test{active:true}\n'
        doc = cortex_to_dict(text)
        entry = doc["sections"][0]["entries"][0]
        assert entry["attrs"]["active"] is True

    def test_section_with_no_title(self):
        text = "$0\n\n$1\n\nLNG:test{type:\"process\"}\n"
        doc = cortex_to_dict(text)
        sec = doc["sections"][0]
        assert sec["id"] == "$1"
        # Title should be None or empty
        assert sec["title"] is None or sec["title"] == ""


class TestFallbackEdgeCases:
    """Additional fallback parser edge cases for coverage."""

    def test_fallback_attrs_with_integer(self):
        with patch("arqux.cortex.reader._PARSER", None):
            text = "$0\n\n$1: T\n\nTIE:nano{window:8, load:AGENTS}\n"
            doc = cortex_to_dict(text)
        entry = doc["sections"][0]["entries"][0]
        assert entry["attrs"]["window"] == 8
        assert entry["attrs"]["load"] == "AGENTS"

    def test_fallback_attrs_with_boolean(self):
        with patch("arqux.cortex.reader._PARSER", None):
            text = "$0\n\n$1: T\n\nLNG:test{active:true, dead:false}\n"
            doc = cortex_to_dict(text)
        entry = doc["sections"][0]["entries"][0]
        assert entry["attrs"]["active"] is True
        assert entry["attrs"]["dead"] is False

    def test_fallback_attrs_with_float(self):
        with patch("arqux.cortex.reader._PARSER", None):
            text = "$0\n\n$1: T\n\nLNG:test{val:3.14}\n"
            doc = cortex_to_dict(text)
        entry = doc["sections"][0]["entries"][0]
        assert entry["attrs"]["val"] == 3.14

    def test_fallback_empty_attrs(self):
        with patch("arqux.cortex.reader._PARSER", None):
            text = "$0\n\n$1: T\n\nLNG:test{}\n"
            doc = cortex_to_dict(text)
        entry = doc["sections"][0]["entries"][0]
        assert entry["attrs"] == {}

    def test_fallback_cuerpo_not_attrs(self):
        """Multi-line body that isn't valid attrs → cuerpo."""
        with patch("arqux.cortex.reader._PARSER", None):
            text = "$0\n\n$1: T\n\nAXM:rule{\njust some text\nnot attrs\n}\n"
            doc = cortex_to_dict(text)
        entry = doc["sections"][0]["entries"][0]
        assert "body" in entry
        assert "just some text" in entry["body"]

    def test_fallback_multi_line_attrs(self):
        """Multi-line entry with valid attrs parsed as attrs."""
        with patch("arqux.cortex.reader._PARSER", None):
            text = "$0\n\n$1: T\n\nLNG:test{\ntype:\"process\",\nlevel:\"2\"\n}\n"
            doc = cortex_to_dict(text)
        entry = doc["sections"][0]["entries"][0]
        assert "attrs" in entry
        assert entry["attrs"]["type"] == "process"

    def test_fallback_glossary_only_with_comments(self):
        """Just $0 with comments, no other sections."""
        with patch("arqux.cortex.reader._PARSER", None):
            text = "$0\n# only comment\n"
            doc = cortex_to_dict(text)
        assert doc["glossary"]["comments"] == ["# only comment"]
        assert doc["sections"] == []

    def test_fallback_multiple_entries_in_section(self):
        with patch("arqux.cortex.reader._PARSER", None):
            text = "$0\n\n$1: T\n\nLNG:a{x:1}\nLNG:b{y:2}\n"
            doc = cortex_to_dict(text)
        entries = doc["sections"][0]["entries"]
        assert len(entries) == 2
        assert entries[0]["name"] == "a"
        assert entries[1]["name"] == "b"

    def test_fallback_skips_gsig_declarations(self):
        with patch("arqux.cortex.reader._PARSER", None):
            text = "$0\nGSIG:AXM{name:axiom}\n\n$1: T\n\nLNG:test{x:1}\n"
            doc = cortex_to_dict(text)
        # GSIG line should not appear as an entry
        assert len(doc["sections"]) == 1
        assert len(doc["sections"][0]["entries"]) == 1

    def test_fallback_section_no_title(self):
        with patch("arqux.cortex.reader._PARSER", None):
            text = "$0\n\n$1\n\nLNG:test{x:1}\n"
            doc = cortex_to_dict(text)
        sec = doc["sections"][0]
        assert sec["id"] == "$1"
        assert sec["title"] is None

    def test_fallback_unrecognized_lines_skipped(self):
        with patch("arqux.cortex.reader._PARSER", None):
            text = "$0\n\n$1: T\n\ngarbage line\nLNG:test{x:1}\n"
            doc = cortex_to_dict(text)
        # Should still parse the valid entry
        assert len(doc["sections"][0]["entries"]) == 1

    def test_fallback_string_escaping(self):
        with patch("arqux.cortex.reader._PARSER", None):
            text = '$0\n\n$1: T\n\nLNG:test{msg:"hello \\"world\\""}\n'
            doc = cortex_to_dict(text)
        entry = doc["sections"][0]["entries"][0]
        assert entry["attrs"]["msg"] == 'hello "world"'


class TestCuerpoFallbackExtraction:
    """Test cuerpo extraction from raw when parser fails to type it."""

    def test_cuerpo_with_undeclared_sigil(self):
        """When a cuerpo entry's sigil isn't declared in glossary,
        the parser types it as 'attrs' with empty value.
        The reader should extract the body from raw."""
        text = """\
$0

$1: RULES

AXM:rule1{
Do the thing
Then do more
}
"""
        doc = cortex_to_dict(text)
        entry = doc["sections"][0]["entries"][0]
        assert entry["sigil"] == "AXM"
        assert entry["name"] == "rule1"
        assert "body" in entry
        assert "Do the thing" in entry["body"]
        assert "Then do more" in entry["body"]


class TestParserFailureFallback:
    """Test that regex fallback is used when CODEC-CORTEX parser raises."""

    def test_parser_exception_triggers_fallback(self):
        """When the parser raises an exception, the reader falls back to regex."""
        with patch("arqux.cortex.reader._PARSER") as mock_parser:
            mock_parser.side_effect = RuntimeError("parser crashed")
            mock_parser._PARSER_API = "cortex_core"
            doc = cortex_to_dict(SIMPLE_CORTEX)
        # Fallback should still parse correctly
        assert len(doc["sections"]) == 1
        assert doc["sections"][0]["id"] == "$1"

    def test_parser_exception_fallback_attrs(self):
        with patch("arqux.cortex.reader._PARSER") as mock_parser:
            mock_parser.side_effect = RuntimeError("parser crashed")
            doc = cortex_to_dict(SIMPLE_CORTEX)
        entry = doc["sections"][0]["entries"][0]
        assert entry["sigil"] == "LNG"
        assert entry["name"] == "test"
