"""Tests for BLP-002: arqux.cortex.crud — JSON/dict CRUD over CORTEX.

Covers all acceptance criteria (AC-01 … AC-13) including selector parsing,
wildcards, in-place mutation semantics, type-mismatch guards, round-trip
and integration with :mod:`arqux.cortex.writer`.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from arqux.cortex.crud import (
    add_entry,
    delete_entry,
    list_entries,
    move_entry,
    parse_selector,
    select_entries,
    update_entry,
)
from arqux.cortex.writer import write_cortex_from_json

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_doc() -> dict:
    """A representative JSON/dict CORTEX document."""
    return {
        "glossary": {
            "header": "$0",
            "comments": ["# -- $0: TEST GLOSSARY --"],
            "symbols": [],
        },
        "sections": [
            {
                "id": "$7",
                "title": "LESSONS",
                "comments": [],
                "entries": [
                    {
                        "sigil": "LNG",
                        "name": "lesson1",
                        "attrs": {"type": "behavioral", "severity": "high"},
                    },
                    {
                        "sigil": "LNG",
                        "name": "lesson2",
                        "attrs": {"type": "technical", "severity": "low"},
                    },
                    {
                        "sigil": "AXM",
                        "name": "rule1",
                        "body": "Non-negotiable principle",
                    },
                ],
            },
            {
                "id": "$19",
                "title": "ARQUX METADATA",
                "comments": [],
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "artifact",
                        "attrs": {"level": "2", "name": "brain"},
                    },
                ],
            },
        ],
    }


@pytest.fixture
def doc() -> dict:
    return _sample_doc()


def _sample_doc_with_multiple_lng() -> dict:
    """A doc where section $7 has multiple LNG entries (for wildcard tests)."""
    return {
        "glossary": {
            "header": "$0",
            "comments": ["# -- $0: TEST GLOSSARY --"],
            "symbols": [],
        },
        "sections": [
            {
                "id": "$7",
                "title": "LESSONS",
                "comments": [],
                "entries": [
                    {
                        "sigil": "LNG",
                        "name": "lesson1",
                        "attrs": {"type": "behavioral", "severity": "high"},
                    },
                    {
                        "sigil": "LNG",
                        "name": "lesson2",
                        "attrs": {"type": "technical", "severity": "low"},
                    },
                    {
                        "sigil": "LNG",
                        "name": "lesson3",
                        "attrs": {"type": "process", "severity": "med"},
                    },
                    {
                        "sigil": "AXM",
                        "name": "rule1",
                        "body": "Non-negotiable principle",
                    },
                ],
            },
            {
                "id": "$8",
                "title": "ARCHIVE",
                "comments": [],
                "entries": [],
            },
        ],
    }


@pytest.fixture
def doc_multi_lng() -> dict:
    return _sample_doc_with_multiple_lng()


# ---------------------------------------------------------------------------
# AC-01: parse_selector
# ---------------------------------------------------------------------------


class TestParseSelector:
    def test_wildcard_star(self) -> None:
        assert parse_selector("$7/LNG:*") == {
            "section": "$7",
            "sigil": "LNG",
            "name": "*",
        }

    def test_specific_name(self) -> None:
        assert parse_selector("$19/ARQX:artifact") == {
            "section": "$19",
            "sigil": "ARQX",
            "name": "artifact",
        }

    def test_wildcard_underscore(self) -> None:
        assert parse_selector("$7/LNG:_") == {
            "section": "$7",
            "sigil": "LNG",
            "name": "_",
        }

    def test_section_only(self) -> None:
        assert parse_selector("$7") == {
            "section": "$7",
            "sigil": None,
            "name": None,
        }

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_selector("nonsense")

    def test_non_string_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_selector(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC-02 / AC-10: select_entries + wildcards
# ---------------------------------------------------------------------------


class TestSelectEntries:
    def test_select_all_lng_in_section(self, doc: dict) -> None:
        results = select_entries(doc, "$7/LNG:*")
        assert len(results) == 2
        assert all(r["sigil"] == "LNG" for r in results)
        assert all(r["section"] == "$7" for r in results)
        assert {r["name"] for r in results} == {"lesson1", "lesson2"}

    def test_select_specific(self, doc: dict) -> None:
        results = select_entries(doc, "$19/ARQX:artifact")
        assert len(results) == 1
        assert results[0]["name"] == "artifact"
        assert results[0]["attrs"] == {"level": "2", "name": "brain"}

    def test_wildcard_star_matches_all_names(self, doc: dict) -> None:
        results = select_entries(doc, "$7/LNG:*")
        assert len(results) == 2

    def test_wildcard_underscore_first_match(self, doc: dict) -> None:
        results = select_entries(doc, "$7/LNG:_")
        assert len(results) == 1
        assert results[0]["name"] == "lesson1"

    def test_section_only_all_entries(self, doc: dict) -> None:
        results = select_entries(doc, "$7")
        assert len(results) == 3  # 2 LNG + 1 AXM

    def test_select_missing_section_empty(self, doc: dict) -> None:
        assert select_entries(doc, "$99/LNG:*") == []

    def test_select_no_match_empty(self, doc: dict) -> None:
        assert select_entries(doc, "$7/LNG:nonexistent") == []


# ---------------------------------------------------------------------------
# AC-03 / AC-07: add_entry
# ---------------------------------------------------------------------------


class TestAddEntry:
    def test_add_attrs_entry(self, doc: dict) -> None:
        result = add_entry(doc, "$7", "LNG", "lesson3", {"type": "process", "severity": "med"})
        assert result is doc  # returns same doc
        names = [e["name"] for e in select_entries(doc, "$7/LNG:*")]
        assert "lesson3" in names
        entry = select_entries(doc, "$7/LNG:lesson3")[0]
        assert entry["attrs"] == {"type": "process", "severity": "med"}

    def test_add_cuerpo_entry(self, doc: dict) -> None:
        add_entry(doc, "$7", "AXM", "rule2", "Another principle")
        entry = select_entries(doc, "$7/AXM:rule2")[0]
        assert entry["body"] == "Another principle"
        assert "attrs" not in entry

    def test_add_create_section_true(self, doc: dict) -> None:
        add_entry(
            doc,
            "$42",
            "LNG",
            "new_lesson",
            {"type": "behavioral", "cause": "x"},
            create_section=True,
        )
        sections = {s["id"] for s in doc["sections"]}
        assert "$42" in sections
        entry = select_entries(doc, "$42/LNG:new_lesson")[0]
        assert entry["attrs"] == {"type": "behavioral", "cause": "x"}

    def test_add_create_section_false_raises(self, doc: dict) -> None:
        with pytest.raises(ValueError):
            add_entry(doc, "$99", "LNG", "x", {"type": "behavioral"})

    def test_add_invalid_value_raises(self, doc: dict) -> None:
        with pytest.raises(ValueError):
            add_entry(doc, "$7", "LNG", "x", 123)  # type: ignore[arg-type]

    def test_add_entry_section_not_found_no_create_raises(self, doc: dict) -> None:
        """OBS-006: add_entry to non-existent section without create_section raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            add_entry(doc, "$99", "LNG", "test", {"type": "process"})

    def test_add_modifies_inplace(self, doc: dict) -> None:
        before = copy.deepcopy(doc)
        add_entry(doc, "$7", "LNG", "lesson9", {"type": "x"})
        assert doc != before  # mutated
        assert len(doc["sections"][0]["entries"]) == len(before["sections"][0]["entries"]) + 1


# ---------------------------------------------------------------------------
# AC-04 / AC-08 / AC-09: update_entry
# ---------------------------------------------------------------------------


class TestUpdateEntry:
    def test_update_set_merges_attrs(self, doc: dict) -> None:
        result = update_entry(doc, "$7/LNG:lesson1", set_={"severity": "critical"})
        assert result is doc
        entry = select_entries(doc, "$7/LNG:lesson1")[0]
        assert entry["attrs"]["severity"] == "critical"
        # original key preserved (merge, not replace)
        assert entry["attrs"]["type"] == "behavioral"

    def test_update_replace_body(self, doc: dict) -> None:
        update_entry(doc, "$7/AXM:rule1", replace_body="New principle text")
        entry = select_entries(doc, "$7/AXM:rule1")[0]
        assert entry["body"] == "New principle text"

    def test_update_append_body(self, doc: dict) -> None:
        update_entry(doc, "$7/AXM:rule1", replace_body=" APPENDED", append=True)
        entry = select_entries(doc, "$7/AXM:rule1")[0]
        assert entry["body"] == "Non-negotiable principle APPENDED"

    def test_update_set_on_cuerpo_raises(self, doc: dict) -> None:
        with pytest.raises(ValueError):
            update_entry(doc, "$7/AXM:rule1", set_={"x": "y"})

    def test_update_replace_body_on_attrs_raises(self, doc: dict) -> None:
        with pytest.raises(ValueError):
            update_entry(doc, "$7/LNG:lesson1", replace_body="text")

    def test_update_no_match_raises(self, doc: dict) -> None:
        with pytest.raises(ValueError):
            update_entry(doc, "$7/LNG:nonexistent", set_={"x": "y"})

    def test_update_wildcard_star_all_matches(self, doc: dict) -> None:
        update_entry(doc, "$7/LNG:*", set_={"reviewed": "true"})
        for e in select_entries(doc, "$7/LNG:*"):
            assert e["attrs"]["reviewed"] == "true"

    def test_update_no_set_no_body_raises(self, doc: dict) -> None:
        """OBS-003: update_entry with no set_ and no replace_body raises ValueError."""
        with pytest.raises(ValueError, match="at least one"):
            update_entry(doc, "$7/LNG:lesson1")

    def test_update_wildcard_underscore_first_match(self, doc_multi_lng: dict) -> None:
        """OBS-006: _ wildcard in update_entry updates first matching entry only."""
        update_entry(doc_multi_lng, "$7/LNG:_", set_={"type": "rule"})
        first = select_entries(doc_multi_lng, "$7/LNG:lesson1")[0]
        second = select_entries(doc_multi_lng, "$7/LNG:lesson2")[0]
        third = select_entries(doc_multi_lng, "$7/LNG:lesson3")[0]
        assert first["attrs"]["type"] == "rule"
        assert second["attrs"]["type"] == "technical"
        assert third["attrs"]["type"] == "process"

    def test_update_entry_section_not_found_raises(self, doc: dict) -> None:
        """OBS-006: update_entry on non-existent section raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            update_entry(doc, "$99/LNG:test", set_={"type": "rule"})


# ---------------------------------------------------------------------------
# AC-05 / AC-11: delete_entry
# ---------------------------------------------------------------------------


class TestDeleteEntry:
    def test_delete_removes_entry(self, doc: dict) -> None:
        result = delete_entry(doc, "$7/LNG:lesson1")
        assert result is doc
        assert select_entries(doc, "$7/LNG:lesson1") == []
        assert len(select_entries(doc, "$7/LNG:*")) == 1

    def test_delete_no_match_raises(self, doc: dict) -> None:
        with pytest.raises(ValueError):
            delete_entry(doc, "$7/LNG:nonexistent")

    def test_delete_wildcard_star_all(self, doc: dict) -> None:
        delete_entry(doc, "$7/LNG:*")
        assert select_entries(doc, "$7/LNG:*") == []
        # AXM entry untouched
        assert len(select_entries(doc, "$7/AXM:*")) == 1

    def test_delete_wildcard_underscore_first(self, doc: dict) -> None:
        delete_entry(doc, "$7/LNG:_")
        remaining = select_entries(doc, "$7/LNG:*")
        assert len(remaining) == 1
        assert remaining[0]["name"] == "lesson2"

    def test_delete_entry_section_not_found_raises(self, doc: dict) -> None:
        """OBS-006: delete_entry on non-existent section raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            delete_entry(doc, "$99/LNG:test")


# ---------------------------------------------------------------------------
# AC-06: move_entry
# ---------------------------------------------------------------------------


class TestMoveEntry:
    def test_move_between_sections(self, doc: dict) -> None:
        result = move_entry(doc, "$7/LNG:lesson1", "$19")
        assert result is doc
        # gone from $7
        assert select_entries(doc, "$7/LNG:lesson1") == []
        # present in $19
        moved = select_entries(doc, "$19/LNG:lesson1")
        assert len(moved) == 1
        assert moved[0]["attrs"]["type"] == "behavioral"

    def test_move_to_nonexistent_section_raises(self, doc: dict) -> None:
        with pytest.raises(ValueError):
            move_entry(doc, "$7/LNG:lesson1", "$99")

    def test_move_no_match_raises(self, doc: dict) -> None:
        with pytest.raises(ValueError):
            move_entry(doc, "$7/LNG:nonexistent", "$19")

    def test_move_wildcard_star_all(self, doc: dict) -> None:
        move_entry(doc, "$7/LNG:*", "$19")
        assert select_entries(doc, "$7/LNG:*") == []
        assert len(select_entries(doc, "$19/LNG:*")) == 2

    def test_move_wildcard_underscore_first_match(self, doc_multi_lng: dict) -> None:
        """OBS-006: _ wildcard in move_entry moves first matching entry only."""
        move_entry(doc_multi_lng, "$7/LNG:_", "$8")
        # first LNG (lesson1) moved to $8
        assert select_entries(doc_multi_lng, "$7/LNG:lesson1") == []
        assert len(select_entries(doc_multi_lng, "$8/LNG:lesson1")) == 1
        # remaining LNG entries still in $7
        remaining = select_entries(doc_multi_lng, "$7/LNG:*")
        assert len(remaining) == 2
        assert {e["name"] for e in remaining} == {"lesson2", "lesson3"}

    def test_move_entry_section_not_found_raises(self, doc: dict) -> None:
        """OBS-006: move_entry from non-existent section raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            move_entry(doc, "$99/LNG:test", "$19")


# ---------------------------------------------------------------------------
# AC: list_entries
# ---------------------------------------------------------------------------


class TestListEntries:
    def test_list_all(self, doc: dict) -> None:
        all_entries = list_entries(doc)
        assert len(all_entries) == 4  # 3 in $7 + 1 in $19

    def test_list_by_section(self, doc: dict) -> None:
        entries = list_entries(doc, section="$7")
        assert len(entries) == 3
        assert all(e["section"] == "$7" for e in entries)

    def test_list_by_sigil(self, doc: dict) -> None:
        entries = list_entries(doc, sigil="LNG")
        assert len(entries) == 2
        assert all(e["sigil"] == "LNG" for e in entries)

    def test_list_by_section_and_sigil(self, doc: dict) -> None:
        entries = list_entries(doc, section="$7", sigil="AXM")
        assert len(entries) == 1
        assert entries[0]["name"] == "rule1"

    def test_list_no_match(self, doc: dict) -> None:
        assert list_entries(doc, section="$99") == []
        assert list_entries(doc, sigil="NOPE") == []


# ---------------------------------------------------------------------------
# AC-11: in-place + return semantics
# ---------------------------------------------------------------------------


class TestInPlaceSemantics:
    @pytest.mark.parametrize(
        "fn",
        [
            lambda d: add_entry(d, "$7", "LNG", "z", {"x": "y"}),
            lambda d: update_entry(d, "$7/LNG:lesson1", set_={"z": "1"}),
            lambda d: delete_entry(d, "$7/LNG:lesson1"),
            lambda d: move_entry(d, "$7/LNG:lesson1", "$19"),
        ],
        ids=["add", "update", "delete", "move"],
    )
    def test_op_returns_same_doc_object(self, doc: dict, fn) -> None:
        assert fn(doc) is doc


# ---------------------------------------------------------------------------
# AC-13: no imports from cortex.core or codec_cortex
# ---------------------------------------------------------------------------


class TestNoCodecImports:
    def test_no_codec_cortex_import(self) -> None:
        import arqux.cortex.crud as mod

        src = Path(mod.__file__).read_text()
        # No import statements referencing codec_cortex or cortex.core.
        for line in src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert "codec_cortex" not in stripped
                assert "cortex.core" not in stripped

    def test_module_not_dependent_at_runtime(self) -> None:
        import arqux.cortex.crud as mod

        # The module's own namespace must not bind codec_cortex / cortex.core.
        names = set(vars(mod))
        assert "codec_cortex" not in names
        assert "cortex" not in names or getattr(mod, "cortex", None).__name__ not in (
            "cortex.core",
            "codec_cortex",
        )
        # Walk the module's globals for any reference to those packages.
        for value in vars(mod).values():
            modname = getattr(value, "__name__", "")
            assert modname != "codec_cortex"
            assert modname != "cortex.core"


# ---------------------------------------------------------------------------
# AC: Round-trip add → select → update → select → delete → select
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_full_round_trip(self, doc: dict) -> None:
        # add
        add_entry(doc, "$7", "LNG", "rt_lesson", {"type": "roundtrip", "severity": "low"})
        assert len(select_entries(doc, "$7/LNG:rt_lesson")) == 1

        # update
        update_entry(doc, "$7/LNG:rt_lesson", set_={"severity": "high"})
        e = select_entries(doc, "$7/LNG:rt_lesson")[0]
        assert e["attrs"]["severity"] == "high"
        assert e["attrs"]["type"] == "roundtrip"  # merge preserved

        # delete
        delete_entry(doc, "$7/LNG:rt_lesson")
        assert select_entries(doc, "$7/LNG:rt_lesson") == []


# ---------------------------------------------------------------------------
# Integration with writer: CRUD → write_cortex_from_json → valid CORTEX
# ---------------------------------------------------------------------------


class TestWriterIntegration:
    def test_crud_then_write_valid_cortex(self, doc: dict) -> None:
        # perform a series of CRUD ops
        add_entry(doc, "$7", "LNG", "int_lesson", {"type": "integration", "severity": "med"})
        update_entry(doc, "$7/AXM:rule1", replace_body="Integration principle")
        move_entry(doc, "$19/ARQX:artifact", "$7")
        delete_entry(doc, "$7/LNG:lesson2")

        # serialize via BLP-001 writer
        text = write_cortex_from_json(doc)

        # sanity: valid CORTEX text
        assert isinstance(text, str)
        assert "$0" in text
        assert "$7: LESSONS" in text
        assert "LNG:int_lesson{type:\"integration\", severity:\"med\"}" in text
        assert "AXM:rule1{" in text
        assert "Integration principle" in text
        assert "ARQX:artifact" in text  # moved into $7
        assert "lesson2" not in text  # deleted

    def test_crud_then_write_cuerpo_append(self, doc: dict) -> None:
        update_entry(doc, "$7/AXM:rule1", replace_body="\nSecond line", append=True)
        text = write_cortex_from_json(doc)
        assert "Non-negotiable principle" in text
        assert "Second line" in text
