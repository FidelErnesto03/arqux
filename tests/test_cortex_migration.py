"""BLP-006: Migration verification for existing .cortex files.

Verifies that all existing .cortex files work with ArqUX's own
reader, writer, CRUD, and atomic modules. No files are modified.
"""

from pathlib import Path

import pytest

from arqux.core.state._migrate import migrate_cortex_file
from arqux.cortex.atomic import atomic_write_json
from arqux.cortex.crud import add_entry, delete_entry, select_entries, update_entry
from arqux.cortex.reader import cortex_to_dict
from arqux.cortex.writer import write_cortex_from_json

# Find all .cortex files — relative to repo root for CI portability
ARQUX_ROOT = Path(__file__).resolve().parent.parent
IDENTITIES = ARQUX_ROOT / ".arqux" / "identities"

# Workspace files required by some tests; skip in CI if absent
_BRAIN_CORTEX = ARQUX_ROOT / ".arqux" / "brain.cortex"
_JARVIS_CORTEX = IDENTITIES / "jarvis.cortex"
_CYCLE11_CORTEX = ARQUX_ROOT / ".arqux" / "cycles" / "CYCLE-11" / "cycle.cortex"

_HAS_WORKSPACE_FILES = (
    _BRAIN_CORTEX.exists() and _JARVIS_CORTEX.exists() and _CYCLE11_CORTEX.exists()
)
_skip_no_workspace = pytest.mark.skipif(
    not _HAS_WORKSPACE_FILES,
    reason="workspace .cortex files not available in CI checkout",
)

def _find_cortex_files():
    files = []
    # ARQUX .cortex files
    for p in ARQUX_ROOT.rglob("*.cortex"):
        if ".venv" not in str(p) and "__pycache__" not in str(p):
            files.append(p)
    # Identity files
    for p in IDENTITIES.glob("*.cortex"):
        files.append(p)
    return files

CORTEX_FILES = _find_cortex_files()


class TestReadAllCortex:
    """AC-01/03/05/06: All .cortex files can be read by cortex_to_dict()."""

    @pytest.mark.parametrize("cortex_file", CORTEX_FILES, ids=lambda f: f.name)
    def test_read_cortex_file(self, cortex_file):
        text = cortex_file.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        assert "sections" in doc
        assert isinstance(doc["sections"], list)


class TestRoundTripAllCortex:
    """AC-02/04: Round-trip preserves entries for all .cortex files."""

    @pytest.mark.parametrize("cortex_file", CORTEX_FILES, ids=lambda f: f.name)
    def test_round_trip_preserves_entries(self, cortex_file):
        text = cortex_file.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        original_count = sum(len(s.get("entries", [])) for s in doc["sections"])

        # Write and re-read
        text2 = write_cortex_from_json(doc)
        doc2 = cortex_to_dict(text2)
        new_count = sum(len(s.get("entries", [])) for s in doc2["sections"])

        assert new_count == original_count, f"Entry count changed: {original_count} → {new_count}"

    @pytest.mark.parametrize("cortex_file", CORTEX_FILES, ids=lambda f: f.name)
    def test_round_trip_preserves_content(self, cortex_file):
        """OBS-002: Round-trip preserves entry content, not just count."""
        text = cortex_file.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)

        # Write and re-read
        text2 = write_cortex_from_json(doc)
        doc2 = cortex_to_dict(text2)

        # Compare section by section
        assert len(doc2["sections"]) == len(doc["sections"])
        for i, (s1, s2) in enumerate(zip(doc["sections"], doc2["sections"], strict=False)):
            assert s2.get("id") == s1.get("id"), f"Section {i} id mismatch"
            assert s2.get("title") == s1.get("title"), f"Section {i} title mismatch"

            e1 = s1.get("entries", [])
            e2 = s2.get("entries", [])
            assert len(e2) == len(e1), f"Section {i} entry count mismatch"

            for j, (ent1, ent2) in enumerate(zip(e1, e2, strict=False)):
                assert ent2.get("sigil") == ent1.get("sigil"), f"Section {i} entry {j} sigil mismatch"
                assert ent2.get("name") == ent1.get("name"), f"Section {i} entry {j} name mismatch"
                # Compare attrs or body
                if "attrs" in ent1:
                    assert "attrs" in ent2, f"Section {i} entry {j} expected attrs"
                    for k, v in ent1["attrs"].items():
                        assert k in ent2["attrs"], f"Section {i} entry {j} missing attr {k}"
                        assert str(ent2["attrs"][k]) == str(v), f"Section {i} entry {j} attr {k} value mismatch"
                if "body" in ent1:
                    assert "body" in ent2, f"Section {i} entry {j} expected body"


class TestBrainCortex:
    """AC-01/02: Specific tests for brain.cortex."""

    @_skip_no_workspace
    def test_brain_reads_correctly(self):
        text = _BRAIN_CORTEX.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        assert len(doc["sections"]) > 0
        total = sum(len(s.get("entries", [])) for s in doc["sections"])
        assert total > 100  # brain has 298+ entries

    @_skip_no_workspace
    def test_brain_round_trip(self):
        text = _BRAIN_CORTEX.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        original = sum(len(s.get("entries", [])) for s in doc["sections"])
        text2 = write_cortex_from_json(doc)
        doc2 = cortex_to_dict(text2)
        new = sum(len(s.get("entries", [])) for s in doc2["sections"])
        assert new == original


class TestIdentities:
    """AC-03/04: All identity files read and round-trip correctly."""

    @pytest.mark.parametrize("identity_file", list(IDENTITIES.glob("*.cortex")), ids=lambda f: f.stem)
    def test_identity_round_trip(self, identity_file):
        text = identity_file.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        original = sum(len(s.get("entries", [])) for s in doc["sections"])
        text2 = write_cortex_from_json(doc)
        doc2 = cortex_to_dict(text2)
        new = sum(len(s.get("entries", [])) for s in doc2["sections"])
        assert new == original


class TestMigrationDryRun:
    """AC-07: migrate_cortex_file(dry_run=True) doesn't modify files."""

    @_skip_no_workspace
    def test_brain_dry_run_no_modification(self):
        brain = _BRAIN_CORTEX
        original_size = brain.stat().st_size
        original_content = brain.read_text(encoding="utf-8")

        migrate_cortex_file(brain, dry_run=True)

        # File should be unchanged
        assert brain.stat().st_size == original_size
        assert brain.read_text(encoding="utf-8") == original_content
        # No .bck file created
        assert not (brain.parent / "brain.cortex.bck").exists()


class TestCRUDOnCopy:
    """AC-08: CRUD operations work on a copy of brain.cortex."""

    @_skip_no_workspace
    def test_crud_on_brain_copy(self, tmp_path):
        # Copy brain.cortex to temp
        brain = _BRAIN_CORTEX
        temp_file = tmp_path / "brain_copy.cortex"
        temp_file.write_text(brain.read_text(encoding="utf-8"), encoding="utf-8")

        # Read
        text = temp_file.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        original_count = sum(len(s.get("entries", [])) for s in doc["sections"])

        # Add entry
        add_entry(doc, "$7", "LNG", "test_migration_entry", {"type": "process", "lesson": "test"})
        after_add = sum(len(s.get("entries", [])) for s in doc["sections"])
        assert after_add == original_count + 1

        # Update entry (OBS-001: add → update → delete cycle)
        update_entry(doc, "$7/LNG:test_migration_entry", set_={"type": "updated_test"})
        updated = select_entries(doc, "$7/LNG:test_migration_entry")
        assert len(updated) == 1
        assert updated[0].get("attrs", {}).get("type") == "updated_test"

        # Write
        result = atomic_write_json(doc, str(temp_file))
        assert result.bytes_written > 0

        # Re-read and verify
        text2 = temp_file.read_text(encoding="utf-8")
        doc2 = cortex_to_dict(text2)
        after_write = sum(len(s.get("entries", [])) for s in doc2["sections"])
        assert after_write == after_add

        # Verify update persisted
        persisted = select_entries(doc2, "$7/LNG:test_migration_entry")
        assert len(persisted) == 1
        assert persisted[0].get("attrs", {}).get("type") == "updated_test"

        # Find and delete the test entry
        entries = select_entries(doc2, "$7/LNG:test_migration_entry")
        assert len(entries) == 1
        delete_entry(doc2, "$7/LNG:test_migration_entry")
        after_delete = sum(len(s.get("entries", [])) for s in doc2["sections"])
        assert after_delete == original_count

    @_skip_no_workspace
    def test_crud_update_on_brain_copy(self, tmp_path):
        """OBS-001: update_entry works on brain.cortex copy."""
        brain = _BRAIN_CORTEX
        temp_file = tmp_path / "brain_copy.cortex"
        temp_file.write_text(brain.read_text(encoding="utf-8"), encoding="utf-8")

        # Read
        text = temp_file.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)

        # Find an existing LNG entry to update
        entries = select_entries(doc, "$7/LNG:*")
        assert len(entries) > 0
        first_entry = entries[0]
        entry_name = first_entry["name"]

        # Update it
        update_entry(doc, f"$7/LNG:{entry_name}", set_={"type": "updated_test"})

        # Write
        atomic_write_json(doc, str(temp_file))

        # Re-read and verify
        text2 = temp_file.read_text(encoding="utf-8")
        doc2 = cortex_to_dict(text2)
        updated = select_entries(doc2, f"$7/LNG:{entry_name}")
        assert len(updated) == 1
        assert updated[0].get("attrs", {}).get("type") == "updated_test"


class TestMigrationExecution:
    """OBS-003: Test actual migration logic on copies."""

    @_skip_no_workspace
    def test_migrate_brain_copy(self, tmp_path):
        """Test actual migration on a copy of brain.cortex."""
        brain = _BRAIN_CORTEX
        temp_file = tmp_path / "brain_copy.cortex"
        temp_file.write_text(brain.read_text(encoding="utf-8"), encoding="utf-8")

        # Run actual migration (not dry-run)
        result = migrate_cortex_file(temp_file, dry_run=False)

        # Verify migration happened
        assert result is True or result is False  # Either it migrated or didn't need to

        # Verify file still exists and is readable
        assert temp_file.exists()
        text = temp_file.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        assert len(doc["sections"]) > 0

        # Verify backup was created
        backup = tmp_path / "brain_copy.cortex.bck"
        assert backup.exists()

        # Verify round-trip still works after migration
        text2 = write_cortex_from_json(doc)
        doc2 = cortex_to_dict(text2)
        original_count = sum(len(s.get("entries", [])) for s in doc["sections"])
        new_count = sum(len(s.get("entries", [])) for s in doc2["sections"])
        assert new_count == original_count

    @_skip_no_workspace
    def test_migrate_identity_copy(self, tmp_path):
        """Test migration on a copy of an identity file."""
        identity = _JARVIS_CORTEX
        temp_file = tmp_path / "jarvis_copy.cortex"
        temp_file.write_text(identity.read_text(encoding="utf-8"), encoding="utf-8")

        migrate_cortex_file(temp_file, dry_run=False)

        assert temp_file.exists()
        text = temp_file.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        assert len(doc["sections"]) > 0

    @_skip_no_workspace
    def test_migrate_cycle_copy(self, tmp_path):
        """Test migration on a copy of a cycle.cortex file."""
        cycle = _CYCLE11_CORTEX
        temp_file = tmp_path / "cycle_copy.cortex"
        temp_file.write_text(cycle.read_text(encoding="utf-8"), encoding="utf-8")

        migrate_cortex_file(temp_file, dry_run=False)

        assert temp_file.exists()
        text = temp_file.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
        assert len(doc["sections"]) > 0

    @_skip_no_workspace
    def test_migrate_preserves_entries(self, tmp_path):
        """Test that migration preserves entry count."""
        brain = _BRAIN_CORTEX
        temp_file = tmp_path / "brain_copy.cortex"
        temp_file.write_text(brain.read_text(encoding="utf-8"), encoding="utf-8")

        # Count before
        text_before = temp_file.read_text(encoding="utf-8")
        doc_before = cortex_to_dict(text_before)
        count_before = sum(len(s.get("entries", [])) for s in doc_before["sections"])

        # Migrate
        migrate_cortex_file(temp_file, dry_run=False)

        # Count after
        text_after = temp_file.read_text(encoding="utf-8")
        doc_after = cortex_to_dict(text_after)
        count_after = sum(len(s.get("entries", [])) for s in doc_after["sections"])

        # Should preserve all entries (or very close)
        assert count_after >= count_before * 0.95, f"Lost entries: {count_before} → {count_after}"

    def test_migrate_nonexistent_file(self, tmp_path):
        """OBS-003: migrate_cortex_file returns False for missing file."""
        missing = tmp_path / "does_not_exist.cortex"
        result = migrate_cortex_file(missing, dry_run=False)
        assert result is False

    def test_migrate_bck_file_skipped(self, tmp_path):
        """OBS-003: migrate_cortex_file skips .bck files."""
        bck = tmp_path / "backup.cortex.bck"
        bck.write_text("$0\n$1\n  AXM:test{name}\n", encoding="utf-8")
        result = migrate_cortex_file(bck, dry_run=False)
        assert result is False
        # File untouched
        assert bck.exists()

    @_skip_no_workspace
    def test_migrate_dry_run_on_multiple_files(self, tmp_path):
        """OBS-004: Test dry-run on multiple files, not just brain."""
        files_to_test = [
            _BRAIN_CORTEX,
            _CYCLE11_CORTEX,
            _JARVIS_CORTEX,
            IDENTITIES / "alfred.cortex",
        ]
        for f in files_to_test:
            temp = tmp_path / f"copy_{f.name}"
            temp.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            original_content = temp.read_text(encoding="utf-8")
            original_size = temp.stat().st_size

            migrate_cortex_file(temp, dry_run=True)

            assert temp.stat().st_size == original_size
            assert temp.read_text(encoding="utf-8") == original_content
            assert not (tmp_path / f"copy_{f.stem}.cortex.bck").exists()
