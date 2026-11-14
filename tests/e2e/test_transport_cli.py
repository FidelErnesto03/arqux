"""Transport and CLI contract suite — finding 2.8 and the 2026-10-11 dogfood
frictions (opaque error, no @file/stdin, no first-level project/cycle).

One canonical CLI contract: same handler surface, multiline payloads by
file/stdin, first-level sugar, non-zero exit codes on failure.
"""

from __future__ import annotations

from click.testing import CliRunner

from arqux.cli import main


def test_first_level_project_and_cycle_commands_exist():
    """2.5/2.8: `arqux project` and `arqux cycle` are real subcommands."""
    runner = CliRunner()
    for cmd in ("project", "cycle"):
        result = runner.invoke(main, [cmd, "--help"])
        assert result.exit_code == 0, result.output


def test_call_accepts_file_payload(tmp_path, governor_ctx):
    """2.8: multiline payloads travel via `@file`, not shell quoting."""
    doc = tmp_path / "doc.cortex"
    doc.write_text('$0\n\n$1: SINK\n\nREG:seed{kind:"probe"}\n', encoding="utf-8")

    value_file = tmp_path / "value.txt"
    value_file.write_text('kind:"from-file", note:"linea uno\nlinea dos"', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [
        "call", "cortex.entry.add",
        f"path={doc}", "section=$1", "sigil=REG", "name=fromfile",
        f"value=@{value_file}",
    ])
    assert result.exit_code == 0, result.output
    assert "REG:fromfile" in doc.read_text(encoding="utf-8")


def test_call_quiet_failure_sets_nonzero_exit(tmp_path):
    """2.11: a failing handler is a non-zero exit, never a silent success."""
    runner = CliRunner()
    result = runner.invoke(main, [
        "call", "cortex.entry.add",
        f"path={tmp_path / 'missing.cortex'}",
        "section=$1", "sigil=REG", "name=x", 'value=\'kind:"p"\'',
    ])
    assert result.exit_code != 0, result.output


def test_cycle_synthesize_reports_hint_for_unbraced_content(arqux_env):
    """2026-10-11 friction (1): `$1:text` explains the expected `$N:{body}`."""
    runner = CliRunner()
    result = runner.invoke(main, [
        "call", "cycle.synthesize",
        f"path={arqux_env.proj_root}",
        f"cycle_id={arqux_env.cycle_id}",
        "content=$1:texto sin llaves",
    ])
    text = (result.output or "").lower()
    assert result.exit_code != 0, result.output
    assert any(hint in text for hint in ("brace", "llave", "{", "section")), text


def test_status_command_runs_without_mcp(arqux_env):
    """The framework must be operable from the CLI alone (dogfood path)."""
    runner = CliRunner()
    result = runner.invoke(main, ["status", "--path", str(arqux_env.proj_root)])
    assert result.exit_code == 0, result.output


def test_blueprint_synthesize_schema_exposes_content():
    """HD-03 (audit 2026-11-13): the MCP schema dropped `content` while the
    implementation accepted it. Decision: expose it and apply it."""
    from arqux.handlers import REGISTRY
    from arqux.server import _validate_arguments

    spec = REGISTRY["blueprint.synthesize"]
    assert "content" in spec.input_schema["properties"], sorted(
        spec.input_schema["properties"]
    )
    assert _validate_arguments(
        "blueprint.synthesize", spec.input_schema,
        {"bp_id": "BLP-001", "content": "$1:{purpose}"},
    ) is None
