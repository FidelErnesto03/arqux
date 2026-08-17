"""Tests for BLP-001: ArqUX's own CORTEX writer.

Covers:
  1. Basic document with glossary + one section + one attrs entry
  2. Multiple sections with multiple entries
  3. String escaping (quotes, backslashes, unicode)
  4. Cuerpo entries (multi-line body)
  5. Empty sections
  6. Comments in glossary and sections
  7. Round-trip: write → parse with CODEC-CORTEX → verify data matches
  8. Boolean and integer values (unquoted)
  9. None values (skipped)
 10. Section with no title (glossary-style)

The writer module (``arqux.cortex.writer``) has NO dependency on
CODEC-CORTEX.  The round-trip test imports the CODEC-CORTEX parser
directly — tests may depend on it, the writer cannot.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure CODEC-CORTEX parser is importable for round-trip tests.
# The legacy ``cortex.core`` parser is installed alongside arqux; if it is
# not available we skip the round-trip tests rather than failing.
# ---------------------------------------------------------------------------
_HAS_CORTEX_PARSER = False
try:
    from cortex.core.parser import parse_cortex as _parse_cortex  # noqa: F401

    _HAS_CORTEX_PARSER = True
except ImportError:
    pass

# Also try codec_cortex (newer package) — add its path if needed.
if not _HAS_CORTEX_PARSER:
    _CODEC_PATH = Path("/home/vatrox/workspace/CODEC-CORTEX")
    if _CODEC_PATH.is_dir():
        sys.path.insert(0, str(_CODEC_PATH))
    try:
        from codec_cortex.parser import parse_cortex as _parse_cortex  # noqa: F401

        _HAS_CORTEX_PARSER = True
    except ImportError:
        pass

requires_parser = pytest.mark.skipif(
    not _HAS_CORTEX_PARSER,
    reason="CODEC-CORTEX parser not available",
)

from arqux.cortex.writer import write_cortex_from_json  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_GLOSSARY_COMMENTS = [
    "# -- $0: GLOSSARY --",
    "# Sigil | Name | Type | Risk | Layer | Description",
    "# ARQX  | artifact  | attrs  | B | Semantic | ArqUX artifact metadata",
    "# FCS   | focus     | attrs  | H | Working    | Active attention anchor",
    "# DESC  | description | cuerpo | B | Semantic | Structured textual description",
]


def _basic_doc() -> dict:
    """A minimal document with glossary + one section + one attrs entry."""
    return {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$19",
                "title": "ARQUX METADATA",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "artifact",
                        "attrs": {
                            "level": "2",
                            "name": "brain",
                            "usage": "state",
                            "kind": "native",
                        },
                    }
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# 1. Basic document
# ---------------------------------------------------------------------------


def test_basic_document() -> None:
    """Glossary + one section + one attrs entry produces valid CORTEX."""
    text = write_cortex_from_json(_basic_doc())
    assert "$0" in text
    assert "$19: ARQUX METADATA" in text
    assert 'ARQX:artifact{level:"2", name:"brain", usage:"state", kind:"native"}' in text
    # Glossary comments preserved
    assert "# -- $0: GLOSSARY --" in text
    assert "# ARQX  | artifact  | attrs  | B | Semantic | ArqUX artifact metadata" in text


def test_basic_document_starts_with_glossary() -> None:
    """Output must start with the $0 glossary header."""
    text = write_cortex_from_json(_basic_doc())
    assert text.startswith("$0\n")


def test_basic_document_ends_with_newline() -> None:
    """Output must end with a trailing newline."""
    text = write_cortex_from_json(_basic_doc())
    assert text.endswith("\n")


# ---------------------------------------------------------------------------
# 2. Multiple sections with multiple entries
# ---------------------------------------------------------------------------


def test_multiple_sections_multiple_entries() -> None:
    """Multiple sections each with multiple entries render correctly."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "SECTION ONE",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "first",
                        "attrs": {"val": "a"},
                    },
                    {
                        "sigil": "ARQX",
                        "name": "second",
                        "attrs": {"val": "b"},
                    },
                ],
            },
            {
                "id": "$2",
                "title": "SECTION TWO",
                "entries": [
                    {
                        "sigil": "FCS",
                        "name": "current",
                        "attrs": {"what": "test", "priority": "high"},
                    }
                ],
            },
        ],
    }
    text = write_cortex_from_json(doc)
    assert "$1: SECTION ONE" in text
    assert "$2: SECTION TWO" in text
    assert 'ARQX:first{val:"a"}' in text
    assert 'ARQX:second{val:"b"}' in text
    assert 'FCS:current{what:"test", priority:"high"}' in text
    # Section 1 comes before section 2
    assert text.index("$1: SECTION ONE") < text.index("$2: SECTION TWO")


# ---------------------------------------------------------------------------
# 3. String escaping (quotes, backslashes, unicode)
# ---------------------------------------------------------------------------


def test_string_escaping_quotes() -> None:
    """Double quotes inside strings are escaped as \\"."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "ESCAPE",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {"val": 'say "hello"'},
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert r'val:"say \"hello\""' in text


def test_string_escaping_backslashes() -> None:
    """Backslashes inside strings are escaped as \\\\."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "ESCAPE",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {"val": "back\\slash"},
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert r'val:"back\\slash"' in text


def test_string_escaping_unicode() -> None:
    """Unicode characters are preserved (not escaped)."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "ESCAPE",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {"val": "café résumé — 日本語"},
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert 'café résumé — 日本語' in text


def test_string_escaping_combined() -> None:
    """Quotes + backslashes + unicode together escape correctly."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "ESCAPE",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {"val": 'café "hello" \\ path'},
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert r'val:"café \"hello\" \\ path"' in text


# ---------------------------------------------------------------------------
# 4. Cuerpo entries (multi-line body)
# ---------------------------------------------------------------------------


def test_cuerpo_entry_multiline() -> None:
    """Cuerpo entries render as multi-line with closing brace on its own line."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "BODY",
                "entries": [
                    {
                        "sigil": "DESC",
                        "name": "mydesc",
                        "body": "Line one\nLine two\nLine three",
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    expected_entry = "DESC:mydesc{\nLine one\nLine two\nLine three\n}"
    assert expected_entry in text


def test_cuerpo_entry_single_line_body() -> None:
    """A cuerpo entry with a single-line body still uses multi-line format."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "BODY",
                "entries": [
                    {
                        "sigil": "DESC",
                        "name": "short",
                        "body": "Just one line",
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert "DESC:short{\nJust one line\n}" in text


# ---------------------------------------------------------------------------
# 5. Empty sections
# ---------------------------------------------------------------------------


def test_empty_section() -> None:
    """A section with no entries renders just the header."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {"id": "$1", "title": "EMPTY", "entries": []},
        ],
    }
    text = write_cortex_from_json(doc)
    assert "$1: EMPTY" in text
    # No entries should be present
    assert "ARQX:" not in text
    assert "FCS:" not in text


def test_empty_section_no_entries_key() -> None:
    """A section without an 'entries' key is treated as empty."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {"id": "$1", "title": "NO_ENTRIES"},
        ],
    }
    text = write_cortex_from_json(doc)
    assert "$1: NO_ENTRIES" in text


# ---------------------------------------------------------------------------
# 6. Comments in glossary and sections
# ---------------------------------------------------------------------------


def test_glossary_comments_preserved() -> None:
    """Glossary comment lines appear verbatim in output."""
    comments = [
        "# -- $0: MY GLOSSARY --",
        "# Custom comment line",
        "# Another comment",
    ]
    doc = {
        "glossary": {"comments": comments},
        "sections": [],
    }
    text = write_cortex_from_json(doc)
    for c in comments:
        assert c in text


def test_section_comments_preserved() -> None:
    """Comment lines within a section appear verbatim after the header."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "WITH COMMENTS",
                "comments": ["# section comment 1", "# section comment 2"],
                "entries": [
                    {"sigil": "ARQX", "name": "x", "attrs": {"v": "1"}}
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert "# section comment 1" in text
    assert "# section comment 2" in text
    # Comments appear after the section header
    header_idx = text.index("$1: WITH COMMENTS")
    comment_idx = text.index("# section comment 1")
    assert comment_idx > header_idx


# ---------------------------------------------------------------------------
# 7. Round-trip: write → parse → verify
# ---------------------------------------------------------------------------


@requires_parser
def test_roundtrip_basic() -> None:
    """JSON → CORTEX → parse preserves attrs data."""
    doc = _basic_doc()
    text = write_cortex_from_json(doc)
    parsed = _parse_cortex(text)

    # Find $19 section
    sec19 = None
    for sec in parsed.sections:
        if sec.id == "$19":
            sec19 = sec
            break
    assert sec19 is not None, "$19 section not found"
    assert sec19.title == "ARQUX METADATA"
    assert len(sec19.entries) == 1

    entry = sec19.entries[0]
    assert entry.sigil == "ARQX"
    assert entry.name == "artifact"
    assert entry.value == {
        "level": "2",
        "name": "brain",
        "usage": "state",
        "kind": "native",
    }


@requires_parser
def test_roundtrip_multiple_entries() -> None:
    """Multiple entries round-trip correctly."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "MULTI",
                "entries": [
                    {"sigil": "ARQX", "name": "a", "attrs": {"x": "1"}},
                    {"sigil": "ARQX", "name": "b", "attrs": {"x": "2"}},
                    {"sigil": "FCS", "name": "c", "attrs": {"y": "3"}},
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    parsed = _parse_cortex(text)

    sec = next(s for s in parsed.sections if s.id == "$1")
    assert len(sec.entries) == 3
    assert sec.entries[0].value == {"x": "1"}
    assert sec.entries[1].value == {"x": "2"}
    assert sec.entries[2].value == {"y": "3"}


@requires_parser
def test_roundtrip_cuerpo() -> None:
    """Cuerpo (multi-line body) entries round-trip correctly."""
    body_text = "First line\nSecond line\nThird line"
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "BODY",
                "entries": [
                    {"sigil": "DESC", "name": "mydesc", "body": body_text}
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    parsed = _parse_cortex(text)

    sec = next(s for s in parsed.sections if s.id == "$1")
    assert len(sec.entries) == 1
    entry = sec.entries[0]
    assert entry.sigil == "DESC"
    assert entry.name == "mydesc"
    assert entry.value == body_text


@requires_parser
def test_roundtrip_string_escaping() -> None:
    """Strings with special characters survive a write→parse round-trip."""
    special = 'quotes "here" and back\\slash and café'
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "ESCAPE",
                "entries": [
                    {"sigil": "ARQX", "name": "test", "attrs": {"val": special}}
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    parsed = _parse_cortex(text)

    sec = next(s for s in parsed.sections if s.id == "$1")
    entry = sec.entries[0]
    assert entry.value == {"val": special}


@requires_parser
def test_roundtrip_booleans_integers() -> None:
    """Boolean and integer values round-trip as unquoted atoms."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "TYPES",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {
                            "b_true": True,
                            "b_false": False,
                            "i_val": 42,
                            "f_val": 3.14,
                        },
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    parsed = _parse_cortex(text)

    sec = next(s for s in parsed.sections if s.id == "$1")
    entry = sec.entries[0]
    assert entry.value["b_true"] == True  # noqa: E712
    assert entry.value["b_false"] == False  # noqa: E712
    assert entry.value["i_val"] == 42
    # float may be parsed as float or string depending on parser
    assert float(entry.value["f_val"]) == 3.14


@requires_parser
def test_roundtrip_none_skipped() -> None:
    """None values are skipped in output and absent after parsing."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "NONE",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {
                            "present": "yes",
                            "absent": None,
                            "also_present": 123,
                        },
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    # None key should not appear in output
    assert "absent" not in text
    parsed = _parse_cortex(text)

    sec = next(s for s in parsed.sections if s.id == "$1")
    entry = sec.entries[0]
    assert "present" in entry.value
    assert "absent" not in entry.value
    assert "also_present" in entry.value


# ---------------------------------------------------------------------------
# 8. Boolean and integer values (unquoted)
# ---------------------------------------------------------------------------


def test_boolean_values_unquoted() -> None:
    """True → true, False → false (no quotes)."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "BOOL",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {"t": True, "f": False},
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert "t:true" in text
    assert "f:false" in text
    assert 't:"true"' not in text
    assert 'f:"false"' not in text


def test_integer_values_unquoted() -> None:
    """Integers render without quotes."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "INT",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {"zero": 0, "positive": 42, "negative": -7},
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert "zero:0" in text
    assert "positive:42" in text
    assert "negative:-7" in text
    assert 'zero:"0"' not in text


# ---------------------------------------------------------------------------
# 9. None values (skipped)
# ---------------------------------------------------------------------------


def test_none_values_skipped() -> None:
    """None values are omitted from the output entirely."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "NONE",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {"keep": "yes", "drop": None},
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert "keep" in text
    assert "drop" not in text


# ---------------------------------------------------------------------------
# 10. Section with no title (glossary-style)
# ---------------------------------------------------------------------------


def test_section_no_title() -> None:
    """A section with title=None renders just the $N header (no colon)."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$5",
                "title": None,
                "entries": [
                    {"sigil": "ARQX", "name": "x", "attrs": {"v": "1"}}
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    # Header should be "$5" not "$5: ..."
    assert "\n$5\n" in text
    assert "$5:" not in text


def test_section_no_title_key() -> None:
    """A section without a 'title' key defaults to no-title (glossary-style)."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$5",
                "entries": [
                    {"sigil": "ARQX", "name": "x", "attrs": {"v": "1"}}
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert "\n$5\n" in text


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------


def test_no_glossary() -> None:
    """A document with no glossary defaults to $0 header."""
    doc = {"sections": []}
    text = write_cortex_from_json(doc)
    assert text.startswith("$0\n")


def test_empty_document() -> None:
    """An empty document produces just the $0 glossary header."""
    text = write_cortex_from_json({})
    assert text.strip() == "$0"


def test_attrs_and_body_mutually_exclusive() -> None:
    """An entry with both attrs and body raises ValueError."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "ERR",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "bad",
                        "attrs": {"x": "1"},
                        "body": "text",
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="mutually exclusive"):
        write_cortex_from_json(doc)


def test_entry_neither_attrs_nor_body() -> None:
    """An entry with neither attrs nor body raises ValueError."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "ERR",
                "entries": [
                    {"sigil": "ARQX", "name": "bad"}
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="neither"):
        write_cortex_from_json(doc)


def test_glossary_symbols_ignored() -> None:
    """The 'symbols' key in glossary is ignored — comments carry the glossary."""
    doc = {
        "glossary": {
            "comments": ["# my comment"],
            "symbols": [{"sigil": "X", "name": "y"}],
        },
        "sections": [],
    }
    text = write_cortex_from_json(doc)
    assert "# my comment" in text
    # Symbol data should not appear as entry lines
    assert "X:y{" not in text


def test_custom_glossary_header() -> None:
    """A custom glossary header is used if provided."""
    doc = {
        "glossary": {"header": "$0:KERNEL", "comments": []},
        "sections": [],
    }
    text = write_cortex_from_json(doc)
    assert text.startswith("$0:KERNEL")


@requires_parser
def test_roundtrip_empty_section() -> None:
    """Empty sections survive a write→parse round-trip."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {"id": "$1", "title": "EMPTY", "entries": []},
            {"id": "$2", "title": "ALSO_EMPTY", "entries": []},
        ],
    }
    text = write_cortex_from_json(doc)
    parsed = _parse_cortex(text)
    ids = [s.id for s in parsed.sections]
    assert "$1" in ids
    assert "$2" in ids


@requires_parser
def test_roundtrip_section_no_title() -> None:
    """A section with no title round-trips correctly."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$5",
                "title": None,
                "entries": [
                    {"sigil": "ARQX", "name": "x", "attrs": {"v": "1"}}
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    parsed = _parse_cortex(text)
    sec = next(s for s in parsed.sections if s.id == "$5")
    assert len(sec.entries) == 1
    assert sec.entries[0].value == {"v": "1"}


@requires_parser
def test_roundtrip_section_comments() -> None:
    """Section comments survive a write→parse round-trip."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "WITH COMMENTS",
                "comments": ["# important note", "# another note"],
                "entries": [
                    {"sigil": "ARQX", "name": "x", "attrs": {"v": "1"}}
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    parsed = _parse_cortex(text)
    sec = next(s for s in parsed.sections if s.id == "$1")
    assert "# important note" in sec.comments
    assert "# another note" in sec.comments


@requires_parser
def test_roundtrip_multiple_sections() -> None:
    """Multiple sections with mixed entry types round-trip correctly."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$19",
                "title": "METADATA",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "artifact",
                        "attrs": {"level": "2", "name": "brain"},
                    }
                ],
            },
            {
                "id": "$2",
                "title": "FOCUS",
                "entries": [
                    {
                        "sigil": "FCS",
                        "name": "current",
                        "attrs": {"what": "test", "priority": "high"},
                    },
                    {
                        "sigil": "DESC",
                        "name": "detail",
                        "body": "Detailed description\nwith multiple lines",
                    },
                ],
            },
            {
                "id": "$3",
                "title": "EMPTY",
                "entries": [],
            },
        ],
    }
    text = write_cortex_from_json(doc)
    parsed = _parse_cortex(text)

    # Section $19
    sec19 = next(s for s in parsed.sections if s.id == "$19")
    assert sec19.title == "METADATA"
    assert sec19.entries[0].value == {"level": "2", "name": "brain"}

    # Section $2
    sec2 = next(s for s in parsed.sections if s.id == "$2")
    assert sec2.title == "FOCUS"
    assert len(sec2.entries) == 2
    assert sec2.entries[0].value == {"what": "test", "priority": "high"}
    assert sec2.entries[1].value == "Detailed description\nwith multiple lines"

    # Section $3 (empty)
    sec3 = next(s for s in parsed.sections if s.id == "$3")
    assert sec3.title == "EMPTY"
    assert len(sec3.entries) == 0


# ---------------------------------------------------------------------------
# OBS-001: Cuerpo body containing a line that is exactly "}" breaks round-trip
# ---------------------------------------------------------------------------


def test_cuerpo_body_with_lone_brace_raises() -> None:
    """A cuerpo body containing a line that is exactly '}' raises ValueError.

    This prevents silent data loss: the CORTEX parser's depth-aware brace
    matching would truncate the body at the first lone '}' line.
    """
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "BODY",
                "entries": [
                    {
                        "sigil": "DESC",
                        "name": "bad",
                        "body": "Some text\n}\nMore text",
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="breaks CORTEX parser round-trip"):
        write_cortex_from_json(doc)


def test_cuerpo_body_with_stripped_brace_raises() -> None:
    """A cuerpo body with a line that strips to '}' (e.g. '  }  ') raises."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "BODY",
                "entries": [
                    {
                        "sigil": "DESC",
                        "name": "bad",
                        "body": "Some text\n  }  \nMore text",
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="breaks CORTEX parser round-trip"):
        write_cortex_from_json(doc)


def test_cuerpo_body_with_brace_in_text_does_not_raise() -> None:
    """A '}' embedded in a line with other text does NOT raise.

    Only a line that is *exactly* '}' (after stripping) breaks the parser.
    A '}' that appears inline with other content is safe.
    """
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "BODY",
                "entries": [
                    {
                        "sigil": "DESC",
                        "name": "ok",
                        "body": "code: x = {a: 1}\nnext line has } inline\nfinal line",
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert "code: x = {a: 1}" in text
    assert "next line has } inline" in text


def test_cuerpo_body_lone_brace_error_mentions_entry() -> None:
    """The ValueError message includes the sigil:name for diagnostics."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "BODY",
                "entries": [
                    {
                        "sigil": "DESC",
                        "name": "myentry",
                        "body": "text\n}\nmore",
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="DESC:myentry"):
        write_cortex_from_json(doc)


# ---------------------------------------------------------------------------
# OBS-002: List/tuple attr values don't round-trip as lists
# ---------------------------------------------------------------------------


def test_list_attr_value_converted_to_comma_string() -> None:
    """List attr values are converted to comma-separated strings.

    This avoids the double-escaping bug in _serialise_attrs where lists
    were JSON-encoded and then escaped again, producing garbled output.
    """
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "LIST",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {"tags": ["alpha", "beta", "gamma"]},
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    # Should be a clean quoted string, not JSON-encoded with escaped quotes
    assert 'tags:"alpha, beta, gamma"' in text
    # Should NOT contain the old double-escaped JSON form
    assert 'tags:"[\\"alpha\\", \\"beta\\", \\"gamma\\"]"' not in text


def test_tuple_attr_value_converted_to_comma_string() -> None:
    """Tuple attr values are also converted to comma-separated strings."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "TUPLE",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {"coords": (10, 20, 30)},
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert 'coords:"10, 20, 30"' in text


def test_list_attr_with_mixed_types() -> None:
    """List with mixed types (str, int) is joined as strings."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "MIXED",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {"items": ["hello", 42, True]},
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert 'items:"hello, 42, True"' in text


def test_list_attr_empty_list() -> None:
    """An empty list becomes an empty string."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "EMPTY_LIST",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {"tags": []},
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert 'tags:""' in text


def test_list_attr_preserves_other_attrs() -> None:
    """List conversion doesn't affect other non-list attrs in the same entry."""
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "MIXED_ATTRS",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {
                            "name": "brain",
                            "tags": ["a", "b"],
                            "level": 2,
                        },
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    assert 'name:"brain"' in text
    assert 'tags:"a, b"' in text
    assert "level:2" in text


@requires_parser
def test_roundtrip_list_attr_as_string() -> None:
    """List attr values round-trip as comma-separated strings (not lists).

    This documents the CORTEX format limitation: the parser does not support
    list syntax in attrs, so lists are converted to strings.
    """
    doc = {
        "glossary": {"comments": list(_GLOSSARY_COMMENTS)},
        "sections": [
            {
                "id": "$1",
                "title": "LIST_RT",
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "test",
                        "attrs": {"tags": ["alpha", "beta"]},
                    }
                ],
            }
        ],
    }
    text = write_cortex_from_json(doc)
    parsed = _parse_cortex(text)
    sec = next(s for s in parsed.sections if s.id == "$1")
    entry = sec.entries[0]
    # Round-trips as a string, not a list
    assert entry.value["tags"] == "alpha, beta"
    assert isinstance(entry.value["tags"], str)


# ---------------------------------------------------------------------------
# OBS-003: Malformed input raises raw exceptions → add validation
# ---------------------------------------------------------------------------


def test_none_document_raises_value_error() -> None:
    """Passing None as document raises ValueError, not TypeError."""
    with pytest.raises(ValueError, match="cannot be None"):
        write_cortex_from_json(None)  # type: ignore[arg-type]


def test_non_dict_document_raises_value_error() -> None:
    """Passing a non-dict (e.g. list) raises ValueError with type info."""
    with pytest.raises(ValueError, match="Expected dict, got list"):
        write_cortex_from_json([])  # type: ignore[arg-type]


def test_string_document_raises_value_error() -> None:
    """Passing a string raises ValueError with type info."""
    with pytest.raises(ValueError, match="Expected dict, got str"):
        write_cortex_from_json("not a dict")  # type: ignore[arg-type]


def test_int_document_raises_value_error() -> None:
    """Passing an int raises ValueError with type info."""
    with pytest.raises(ValueError, match="Expected dict, got int"):
        write_cortex_from_json(42)  # type: ignore[arg-type]


def test_section_not_dict_raises_value_error() -> None:
    """A section that is not a dict raises ValueError with index."""
    doc = {
        "glossary": {"comments": []},
        "sections": ["not a dict"],  # type: ignore[list-item]
    }
    with pytest.raises(ValueError, match="Section 0 must be a dict, got str"):
        write_cortex_from_json(doc)


def test_section_missing_id_raises_value_error() -> None:
    """A section missing the 'id' key raises ValueError."""
    doc = {
        "glossary": {"comments": []},
        "sections": [{"title": "NO_ID"}],  # type: ignore[dict-item]
    }
    with pytest.raises(ValueError, match="Section 0 missing required 'id' key"):
        write_cortex_from_json(doc)


def test_section_none_raises_value_error() -> None:
    """A section that is None raises ValueError."""
    doc = {
        "glossary": {"comments": []},
        "sections": [None],  # type: ignore[list-item]
    }
    with pytest.raises(ValueError, match="Section 0 must be a dict, got NoneType"):
        write_cortex_from_json(doc)


def test_entry_not_dict_raises_value_error() -> None:
    """An entry that is not a dict raises ValueError with index and section."""
    doc = {
        "glossary": {"comments": []},
        "sections": [
            {
                "id": "$1",
                "title": "BAD_ENTRY",
                "entries": ["not a dict"],  # type: ignore[list-item]
            }
        ],
    }
    with pytest.raises(ValueError, match=r"Entry 0 in section \$1 must be a dict, got str"):
        write_cortex_from_json(doc)


def test_entry_missing_sigil_raises_value_error() -> None:
    """An entry missing 'sigil' raises ValueError."""
    doc = {
        "glossary": {"comments": []},
        "sections": [
            {
                "id": "$1",
                "title": "BAD",
                "entries": [{"name": "test", "attrs": {"x": "1"}}],  # type: ignore[dict-item]
            }
        ],
    }
    with pytest.raises(ValueError, match=r"Entry 0 in section \$1 missing required 'sigil' key"):
        write_cortex_from_json(doc)


def test_entry_missing_name_raises_value_error() -> None:
    """An entry missing 'name' raises ValueError."""
    doc = {
        "glossary": {"comments": []},
        "sections": [
            {
                "id": "$1",
                "title": "BAD",
                "entries": [{"sigil": "ARQX", "attrs": {"x": "1"}}],  # type: ignore[dict-item]
            }
        ],
    }
    with pytest.raises(ValueError, match=r"Entry 0 in section \$1 missing required 'name' key"):
        write_cortex_from_json(doc)


def test_entry_none_raises_value_error() -> None:
    """An entry that is None raises ValueError."""
    doc = {
        "glossary": {"comments": []},
        "sections": [
            {
                "id": "$1",
                "title": "BAD",
                "entries": [None],  # type: ignore[list-item]
            }
        ],
    }
    with pytest.raises(ValueError, match=r"Entry 0 in section \$1 must be a dict, got NoneType"):
        write_cortex_from_json(doc)


def test_validation_error_for_second_section() -> None:
    """Validation error for section index 1 mentions the correct index."""
    doc = {
        "glossary": {"comments": []},
        "sections": [
            {"id": "$1", "title": "OK", "entries": []},
            {"title": "NO_ID"},  # type: ignore[dict-item]
        ],
    }
    with pytest.raises(ValueError, match="Section 1 missing required 'id' key"):
        write_cortex_from_json(doc)


def test_validation_error_for_second_entry() -> None:
    """Validation error for entry index 1 mentions the correct index."""
    doc = {
        "glossary": {"comments": []},
        "sections": [
            {
                "id": "$1",
                "title": "BAD",
                "entries": [
                    {"sigil": "ARQX", "name": "ok", "attrs": {"x": "1"}},
                    {"sigil": "ARQX", "attrs": {"x": "2"}},  # type: ignore[dict-item]
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match=r"Entry 1 in section \$1 missing required 'name' key"):
        write_cortex_from_json(doc)
