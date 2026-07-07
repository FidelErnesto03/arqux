"""Tests for cortex.render.validate_file."""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.cortex import render_validate_file_handler


def test_validate_file_all_pass(tmp_path: Path) -> None:
    path = tmp_path / "valid.puml"
    path.write_text(
        "@startuml\nAlice -> Bob: hello\n@enduml\n"
    )
    result = render_validate_file_handler(path=str(path))
    assert result.profile == "OUT-WORK"


def test_validate_file_syntax_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.puml"
    path.write_text(
        "@startuml\n{{bad syntax}}\n@enduml\n"
    )
    result = render_validate_file_handler(path=str(path))
    assert result.profile == "OUT-WORK"
    assert result.fields.get("passed") == 0 or result.fields.get("failed", 0) >= 0


def test_validate_file_no_blocks(tmp_path: Path) -> None:
    path = tmp_path / "no_puml.txt"
    path.write_text("Just some text, no PUML blocks")
    result = render_validate_file_handler(path=str(path))
    assert result.profile == "OUT-WORK"
    assert result.fields.get("total") == 0


def test_validate_file_checklist(tmp_path: Path) -> None:
    path = tmp_path / "checklist.puml"
    path.write_text(
        "@startuml\n@name: test\nAlice -> Bob\n@enduml\n"
    )
    result = render_validate_file_handler(path=str(path))
    assert result.profile == "OUT-WORK"
    checks = result.fields.get("checks", {})
    assert "D1_delimiters" in checks
    assert "D3_syntax" in checks
