"""Tests for arqux.migrate — codec-version drift, census, diff (BLP-005)."""

from __future__ import annotations

from pathlib import Path

from arqux.migrate import (
    IMPLEMENTED_CODEC_VERSION,
    backup_file,
    declared_codec_version,
    diff_census,
    plan_migration,
    scan_codec_drift,
)


class TestDeclaredCodecVersion:
    def test_string_version(self):
        text = '$0:format{cortex:"0.1", encoding:"UTF-8"}\n$1: X\n'
        assert declared_codec_version(text) == "0.1"

    def test_numeric_version(self):
        text = "$0:format{cortex:1.0, encoding:\"UTF-8\"}\n$1: X\n"
        assert declared_codec_version(text) == "1.0"

    def test_no_declaration(self):
        assert declared_codec_version("$1: X\nAXM:a{v:1}\n") is None

    def test_non_format_line_ignored(self):
        text = 'AXM:a{note:"cortex:0.1 mention"}\n$1: X\n'
        assert declared_codec_version(text) is None


class TestScanCodecDrift:
    def _write(self, root: Path, rel: str, version: str | None) -> Path:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        decl = f'$0:format{{cortex:"{version}"}}\n' if version else ""
        p.write_text(decl + "$1: T\n", encoding="utf-8")
        return p

    def test_detects_old_version(self, tmp_path: Path):
        self._write(tmp_path, "brain.cortex", "0.1")
        self._write(tmp_path, "ok.cortex", "1.0")
        self._write(tmp_path, "unversioned.cortex", None)
        drift = scan_codec_drift(tmp_path)
        assert len(drift) == 1
        assert drift[0].declared == "0.1"
        assert drift[0].path.name == "brain.cortex"

    def test_clean_tree_passes(self, tmp_path: Path):
        self._write(tmp_path, "a.cortex", "1.0")
        assert scan_codec_drift(tmp_path) == []

    def test_nested_files_scanned(self, tmp_path: Path):
        self._write(tmp_path, "deep/nested/x.cortex", "0.1")
        drift = scan_codec_drift(tmp_path)
        assert len(drift) == 1


class TestDiffCensus:
    def test_identical_censuses_preserved(self):
        c = {"AXM:a": "h1", "LIM:b": "h2"}
        d = diff_census(c, dict(c))
        assert d.ok and d.preserved == 2 and not d.missing and not d.changed

    def test_missing_entry_detected(self):
        d = diff_census({"AXM:a": "h1", "AXM:b": "h2"}, {"AXM:a": "h1"})
        assert not d.ok and d.missing == ["AXM:b"]

    def test_changed_hash_detected(self):
        d = diff_census({"AXM:a": "h1"}, {"AXM:a": "hX"})
        assert not d.ok and d.changed == ["AXM:a"]

    def test_declared_transform_exempts(self):
        before = {"AXM:old": "h1", "AXM:keep": "h2"}
        after = {"AXM:new": "h3", "AXM:keep": "h2"}
        d = diff_census(before, after, declared_transforms={"AXM:old"})
        assert d.ok and d.added == ["AXM:new"]


class TestBackupFile:
    def test_creates_timestamped_copy(self, tmp_path: Path):
        src = tmp_path / "brain.cortex"
        src.write_text("data", encoding="utf-8")
        dst = backup_file(src)
        assert dst.exists() and dst.read_text() == "data"
        assert ".pre-migration-" in dst.name
        assert dst != src


class TestPlanMigration:
    def test_drifted_file_returns_plan(self, tmp_path: Path):
        p = tmp_path / "brain.cortex"
        p.write_text('$0:format{cortex:"0.1"}\n$1: T\n', encoding="utf-8")
        plan = plan_migration(p)
        assert plan is not None
        assert plan["from"] == "0.1"
        assert plan["to"] == IMPLEMENTED_CODEC_VERSION
        assert plan["skill"] == "cortex-migrate"
        assert "agent_transform_per_skill" in plan["deterministic_steps"]

    def test_current_file_returns_none(self, tmp_path: Path):
        p = tmp_path / "ok.cortex"
        p.write_text('$0:format{cortex:1.0}\n$1: T\n', encoding="utf-8")
        assert plan_migration(p) is None

    def test_unmapped_version_reports_error(self, tmp_path: Path):
        p = tmp_path / "x.cortex"
        p.write_text('$0:format{cortex:"9.9"}\n$1: T\n', encoding="utf-8")
        plan = plan_migration(p)
        assert plan is not None and "error" in plan
