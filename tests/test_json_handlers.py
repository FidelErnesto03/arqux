"""Tests for BLP-004: arqux.cortex.json_handlers — JSON-facing CRUD handlers.

Covers:
  1. cortex_write_json writes valid CORTEX
  2. cortex_read_json returns dict
  3. entry_add_json adds entry to existing file
  4. entry_update_json updates entry
  5. entry_delete_json deletes entry
  6. entry_list_json lists entries
  7. Round-trip: write → read → add → read → update → read → delete → read
  8. create_section=True in entry_add_json
  9. Works with temp files (tmp_path fixture)
 10. Error handling: file not found, invalid input
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.cortex.json_handlers import (
    cortex_read_json,
    cortex_write_json,
    entry_add_json,
    entry_delete_json,
    entry_list_json,
    entry_update_json,
)
from arqux.cortex.reader import cortex_to_dict

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DOC = {
    "glossary": {
        "header": "$0",
        "comments": ["# Test document"],
    },
    "sections": [
        {
            "id": "$1",
            "title": "TEST",
            "comments": [],
            "entries": [
                {"sigil": "LNG", "name": "test", "attrs": {"type": "process"}},
            ],
        },
        {
            "id": "$2",
            "title": "RULES",
            "comments": [],
            "entries": [
                {"sigil": "AXM", "name": "rule1", "body": "First rule\nSecond rule"},
            ],
        },
    ],
}


@pytest.fixture
def cortex_file(tmp_path):
    """Create a sample .cortex file and return its path."""
    path = tmp_path / "test.cortex"
    cortex_write_json(str(path), SAMPLE_DOC)
    return str(path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCortexWriteJson:
    """Test 1: cortex_write_json writes valid CORTEX."""

    def test_write_returns_metadata(self, tmp_path):
        path = str(tmp_path / "out.cortex")
        result = cortex_write_json(path, SAMPLE_DOC)
        assert result["path"] == path
        assert result["bytes_written"] > 0
        assert "backup" in result
        assert "dry_run" in result

    def test_write_creates_file(self, tmp_path):
        path = str(tmp_path / "out.cortex")
        cortex_write_json(path, SAMPLE_DOC)
        assert Path(path).exists()

    def test_write_produces_valid_cortex(self, tmp_path):
        path = str(tmp_path / "out.cortex")
        cortex_write_json(path, SAMPLE_DOC)
        text = Path(path).read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        assert len(doc["sections"]) == 2

    def test_write_creates_backup_on_overwrite(self, tmp_path):
        path = str(tmp_path / "out.cortex")
        cortex_write_json(path, SAMPLE_DOC)
        # Write again — should create backup
        result = cortex_write_json(path, SAMPLE_DOC)
        assert result["backup"] is not None
        assert Path(result["backup"]).exists()


class TestCortexReadJson:
    """Test 2: cortex_read_json returns dict."""

    def test_read_returns_dict(self, cortex_file):
        result = cortex_read_json(cortex_file)
        assert isinstance(result, dict)
        assert "path" in result
        assert "doc" in result
        assert "sections" in result
        assert "entries" in result

    def test_read_returns_correct_counts(self, cortex_file):
        result = cortex_read_json(cortex_file)
        assert result["sections"] == 2
        assert result["entries"] == 2  # one in each section

    def test_read_doc_has_glossary(self, cortex_file):
        result = cortex_read_json(cortex_file)
        doc = result["doc"]
        assert "glossary" in doc
        assert doc["glossary"]["header"] == "$0"

    def test_read_path_matches(self, cortex_file):
        result = cortex_read_json(cortex_file)
        assert result["path"] == cortex_file

    def test_read_json_with_section_filter(self, cortex_file):
        result = cortex_read_json(cortex_file, section="$1")
        assert result["sections"] == 1
        assert result["entries"] == 1  # only the entry in $1
        sections = result["doc"]["sections"]
        assert len(sections) == 1
        assert sections[0]["id"] == "$1"
        assert sections[0]["entries"][0]["sigil"] == "LNG"


class TestEntryAddJson:
    """Test 3: entry_add_json adds entry to existing file."""

    def test_add_attrs_entry(self, cortex_file):
        result = entry_add_json(
            cortex_file, "$1", "ARQX", "new_entry",
            attrs={"level": "3"},
        )
        assert result["added"] == "ARQX:new_entry"
        # Verify it was written
        read_result = cortex_read_json(cortex_file)
        entries = read_result["doc"]["sections"][0]["entries"]
        assert len(entries) == 2
        assert entries[1]["sigil"] == "ARQX"
        assert entries[1]["name"] == "new_entry"

    def test_add_body_entry(self, cortex_file):
        result = entry_add_json(
            cortex_file, "$2", "WK", "workflow",
            body="Step A\nStep B",
        )
        assert result["added"] == "WK:workflow"
        read_result = cortex_read_json(cortex_file)
        entries = read_result["doc"]["sections"][1]["entries"]
        assert len(entries) == 2
        assert entries[1]["body"] == "Step A\nStep B"

    def test_add_returns_metadata(self, cortex_file):
        result = entry_add_json(
            cortex_file, "$1", "LNG", "x", attrs={"v": "1"},
        )
        assert "path" in result
        assert "bytes_written" in result
        assert "backup" in result

    def test_add_with_both_attrs_and_body_raises(self, cortex_file):
        with pytest.raises(ValueError, match="mutually exclusive"):
            entry_add_json(
                cortex_file, "$1", "LNG", "x",
                attrs={"v": "1"},
                body="some body text",
            )


class TestEntryUpdateJson:
    """Test 4: entry_update_json updates entry."""

    def test_update_attrs(self, cortex_file):
        entry_update_json(
            cortex_file, "$1/LNG:test",
            set_={"status": "active"},
        )
        result = cortex_read_json(cortex_file)
        entry = result["doc"]["sections"][0]["entries"][0]
        assert entry["attrs"]["status"] == "active"
        # Original attr preserved
        assert entry["attrs"]["type"] == "process"

    def test_update_body(self, cortex_file):
        entry_update_json(
            cortex_file, "$2/AXM:rule1",
            replace_body="New rule text",
        )
        result = cortex_read_json(cortex_file)
        entry = result["doc"]["sections"][1]["entries"][0]
        assert entry["body"] == "New rule text"

    def test_update_append_body(self, cortex_file):
        entry_update_json(
            cortex_file, "$2/AXM:rule1",
            replace_body="\nThird rule",
            append=True,
        )
        result = cortex_read_json(cortex_file)
        entry = result["doc"]["sections"][1]["entries"][0]
        assert "First rule" in entry["body"]
        assert "Third rule" in entry["body"]

    def test_update_returns_selector(self, cortex_file):
        result = entry_update_json(
            cortex_file, "$1/LNG:test",
            set_={"x": "y"},
        )
        assert result["selector"] == "$1/LNG:test"


class TestEntryDeleteJson:
    """Test 5: entry_delete_json deletes entry."""

    def test_delete_entry(self, cortex_file):
        result = entry_delete_json(cortex_file, "$1/LNG:test")
        assert result["deleted_count"] == 1
        read_result = cortex_read_json(cortex_file)
        entries = read_result["doc"]["sections"][0]["entries"]
        assert len(entries) == 0

    def test_delete_returns_metadata(self, cortex_file):
        result = entry_delete_json(cortex_file, "$1/LNG:test")
        assert "path" in result
        assert "bytes_written" in result
        assert "backup" in result
        assert result["selector"] == "$1/LNG:test"

    def test_delete_nonexistent_raises(self, cortex_file):
        with pytest.raises(ValueError, match="No entries match"):
            entry_delete_json(cortex_file, "$1/LNG:nonexistent")


class TestEntryListJson:
    """Test 6: entry_list_json lists entries."""

    def test_list_all_entries(self, cortex_file):
        result = entry_list_json(cortex_file)
        assert result["count"] == 2
        assert len(result["entries"]) == 2

    def test_list_by_section(self, cortex_file):
        result = entry_list_json(cortex_file, section="$1")
        assert result["count"] == 1
        assert result["entries"][0]["sigil"] == "LNG"

    def test_list_by_sigil(self, cortex_file):
        result = entry_list_json(cortex_file, sigil="AXM")
        assert result["count"] == 1
        assert result["entries"][0]["name"] == "rule1"

    def test_list_empty_filter(self, cortex_file):
        result = entry_list_json(cortex_file, sigil="NONexistent")
        assert result["count"] == 0


class TestFullRoundTrip:
    """Test 7: Round-trip write → read → add → read → update → read → delete → read."""

    def test_full_roundtrip(self, tmp_path):
        path = str(tmp_path / "roundtrip.cortex")

        # Write
        cortex_write_json(path, SAMPLE_DOC)

        # Read
        r = cortex_read_json(path)
        assert r["entries"] == 2

        # Add
        entry_add_json(path, "$1", "ARQX", "new", attrs={"v": "1"})
        r = cortex_read_json(path)
        assert r["entries"] == 3

        # Update
        entry_update_json(path, "$1/ARQX:new", set_={"v": "2"})
        r = cortex_read_json(path)
        entry = r["doc"]["sections"][0]["entries"][1]
        assert entry["attrs"]["v"] == "2"

        # Delete
        entry_delete_json(path, "$1/ARQX:new")
        r = cortex_read_json(path)
        assert r["entries"] == 2

        # Verify original entries still intact
        entries = r["doc"]["sections"][0]["entries"]
        assert len(entries) == 1
        assert entries[0]["name"] == "test"


class TestCreateSection:
    """Test 8: create_section=True in entry_add_json."""

    def test_create_section_true(self, cortex_file):
        entry_add_json(
            cortex_file, "$99", "LNG", "new_section_entry",
            attrs={"type": "test"},
            create_section=True,
        )
        result = cortex_read_json(cortex_file)
        assert result["sections"] == 3
        new_sec = result["doc"]["sections"][2]
        assert new_sec["id"] == "$99"
        assert len(new_sec["entries"]) == 1

    def test_create_section_false_raises(self, cortex_file):
        with pytest.raises(ValueError, match="not found"):
            entry_add_json(
                cortex_file, "$99", "LNG", "x",
                attrs={"v": "1"},
                create_section=False,
            )


class TestTempFiles:
    """Test 9: Works with temp files (tmp_path fixture)."""

    def test_write_read_temp(self, tmp_path):
        path = str(tmp_path / "temp_test.cortex")
        cortex_write_json(path, SAMPLE_DOC)
        assert Path(path).exists()
        result = cortex_read_json(path)
        assert result["sections"] == 2

    def test_add_to_temp_file(self, tmp_path):
        path = str(tmp_path / "temp2.cortex")
        cortex_write_json(path, SAMPLE_DOC)
        entry_add_json(path, "$1", "LNG", "x", attrs={"v": "1"})
        result = cortex_read_json(path)
        assert result["entries"] == 3

    def test_multiple_writes_temp(self, tmp_path):
        path = str(tmp_path / "multi.cortex")
        cortex_write_json(path, SAMPLE_DOC)
        for i in range(5):
            entry_add_json(path, "$1", "LNG", f"entry_{i}", attrs={"idx": i})
        result = cortex_read_json(path)
        assert result["entries"] == 7  # 2 original + 5 added


class TestErrorHandling:
    """Test 10: Error handling: file not found, invalid input."""

    def test_read_nonexistent_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            cortex_read_json(str(tmp_path / "nonexistent.cortex"))

    def test_add_to_nonexistent_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            entry_add_json(
                str(tmp_path / "nonexistent.cortex"),
                "$1", "LNG", "x", attrs={"v": "1"},
            )

    def test_update_nonexistent_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            entry_update_json(
                str(tmp_path / "nonexistent.cortex"),
                "$1/LNG:test", set_={"v": "1"},
            )

    def test_delete_nonexistent_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            entry_delete_json(
                str(tmp_path / "nonexistent.cortex"),
                "$1/LNG:test",
            )

    def test_list_nonexistent_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            entry_list_json(str(tmp_path / "nonexistent.cortex"))

    def test_add_without_attrs_or_body_raises(self, cortex_file):
        with pytest.raises(ValueError):
            entry_add_json(cortex_file, "$1", "LNG", "x")

    def test_update_no_match_raises(self, cortex_file):
        with pytest.raises(ValueError, match="No entries match"):
            entry_update_json(
                cortex_file, "$1/LNG:nonexistent",
                set_={"v": "1"},
            )

    def test_update_type_mismatch_raises(self, cortex_file):
        # Try set_ on a cuerpo entry
        with pytest.raises(ValueError, match="Cannot set_"):
            entry_update_json(
                cortex_file, "$2/AXM:rule1",
                set_={"v": "1"},
            )

    def test_delete_no_match_raises(self, cortex_file):
        with pytest.raises(ValueError, match="No entries match"):
            entry_delete_json(cortex_file, "$1/LNG:nonexistent")
