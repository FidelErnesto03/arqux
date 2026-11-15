"""REQ M2 regression tests (nicho.md): REQ-07 sync-harnesses + drift-check,
REQ-08 wake --identity, REQ-09 review/from-hcortex, REQ-10 enforce levels.
"""

from __future__ import annotations

import re
from pathlib import Path

from click.testing import CliRunner

from arqux.adapters.harness import drift_report, sync_harnesses
from arqux.cli import main
from arqux.core.policy_engine import (
    ERR_MISSING_ENFORCE,
    load_rules,
    validate_policy_text,
)
from arqux.core.state._crud import cortex_verify, cortex_write
from arqux.handlers import project, workspace
from arqux.review import from_hcortex, review_report
from arqux.wake import available_identities, wake_payload


def _project(tmp_path: Path, governor_ctx) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    proj = ws / "proj"
    proj.mkdir()
    workspace.init_workspace(path=str(ws), ctx=governor_ctx)
    project.init_project(name="proj", path=str(proj), ctx=governor_ctx)
    return proj


# ---------------------------------------------------------------------------
# REQ-10 — enforce levels


def test_policy_requires_enforce_level() -> None:
    text = (
        "$0\n\n$0:format{cortex:1.0, encoding:UTF-8}\n\n"
        "$1: RULES\n\n"
        'RUL:r{name:"r", on:"*", check:"secret_pattern"}\n'
    )
    errors = validate_policy_text(text)
    assert any(ERR_MISSING_ENFORCE in e for e in errors)


def test_secret_hook_blocks_write(tmp_path: Path, governor_ctx) -> None:
    proj = _project(tmp_path, governor_ctx)
    brain = proj / ".arqux" / "brain.cortex"
    poisoned = brain.read_text(encoding="utf-8") + (
        'KNW:leak{name:"leak", topic:"t", status:"current", '
        'content:"' + "ghp_" + "1" * 28 + '"}\n'
    )
    result = cortex_write(brain, poisoned)
    assert "error" in result
    assert any("POLICY_BLOCK" in d for d in result["diagnostics"])

    clean = brain.read_text(encoding="utf-8") + (
        'KNW:ok{name:"ok", topic:"t", status:"current", content:"no secret"}\n'
    )
    assert "error" not in cortex_write(brain, clean)


def test_verify_flags_missing_enforce(tmp_path: Path, governor_ctx) -> None:
    proj = _project(tmp_path, governor_ctx)
    pol = proj / ".arqux" / "learn-policies.cortex"
    pol.write_text(
        pol.read_text(encoding="utf-8").replace(', enforce:"CODE"}', "}", 1),
        encoding="utf-8",
    )
    report = cortex_verify(pol)
    assert not report["valid"]
    assert any(ERR_MISSING_ENFORCE in d for d in report["diagnostics"])


def test_template_rules_carry_enforce(tmp_path: Path, governor_ctx) -> None:
    proj = _project(tmp_path, governor_ctx)
    rules = load_rules(proj)
    assert rules
    assert {r.enforce for r in rules} <= {"CODE", "PROMPT", "HUMAN"}
    assert any(r.check == "secret_pattern" for r in rules)


# ---------------------------------------------------------------------------
# REQ-07 — harness projections + drift


def test_sync_harnesses_writes_all_targets(tmp_path: Path, governor_ctx) -> None:
    proj = _project(tmp_path, governor_ctx)
    result = sync_harnesses(proj)
    assert len(result["targets"]) == 4
    for rel in result["targets"]:
        text = (proj / rel).read_text(encoding="utf-8")
        assert f"source_hash:{result['source_hash']}" in text
        assert "arqux:managed" in text


def test_drift_check_detects_manual_edit(tmp_path: Path, governor_ctx) -> None:
    proj = _project(tmp_path, governor_ctx)
    sync_harnesses(proj)
    assert all(d.status == "ok" for d in drift_report(proj))

    claude = proj / "CLAUDE.md"
    claude.write_text(claude.read_text() + "\nhuman edit\n")
    report = {d.target: d for d in drift_report(proj)}
    assert report["CLAUDE.md"].status == "drift"
    assert "human edit" in report["CLAUDE.md"].diff

    (proj / "GEMINI.md").unlink()
    report = {d.target: d for d in drift_report(proj)}
    assert report["GEMINI.md"].status == "missing"


def test_drift_check_cli_exit_code(tmp_path: Path, governor_ctx) -> None:
    proj = _project(tmp_path, governor_ctx)
    runner = CliRunner()
    assert runner.invoke(
        main, ["sync-harnesses", "--path", str(proj)]
    ).exit_code == 0
    assert runner.invoke(
        main, ["drift-check", "--path", str(proj)]
    ).exit_code == 0
    (proj / "CLAUDE.md").write_text("tampered\n")
    result = runner.invoke(main, ["drift-check", "--path", str(proj)])
    assert result.exit_code == 1
    assert "DRIFT_DETECTED" in result.output


# ---------------------------------------------------------------------------
# REQ-08 — wake


def test_wake_payload_valid_cortex(tmp_path: Path, governor_ctx) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    workspace.init_workspace(path=str(ws), ctx=governor_ctx)
    idents = available_identities(ws)
    assert "governor" in idents or idents  # identities dir seeded by init

    payload = wake_payload(idents[0] if idents else "governor", ws, None)
    assert payload.startswith("$0")
    assert "$0:format{cortex:1.0" in payload
    assert "$2: REGISTRY" in payload and "$4: RULES" in payload
    # budget: < 1500 tokens ≈ < 6000 chars
    assert len(payload) < 6000


def test_wake_rejects_unknown_identity(tmp_path: Path, governor_ctx) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    workspace.init_workspace(path=str(ws), ctx=governor_ctx)
    runner = CliRunner()
    result = runner.invoke(
        main, ["wake", "--identity", "nonexistent", "--path", str(ws)]
    )
    assert result.exit_code == 1
    assert "Valid contracts" in result.output


# ---------------------------------------------------------------------------
# REQ-09 — review / from-hcortex


def test_review_report_and_recompile(tmp_path: Path, governor_ctx) -> None:
    import os

    from arqux.handlers import cycle

    proj = _project(tmp_path, governor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(proj)
        cycle.create_cycle(name="R")
    finally:
        os.chdir(cwd)

    md = review_report(proj, "CYCLE-01")
    assert "| Field | Value |" in md
    assert "<!-- HCORTEX" in md
    # no raw sigil lines in the human header region
    header = md.split("## Evidence")[0]
    assert not re.search(r"^[A-Z]{2,4}:\w+\{", header, re.M)

    result = from_hcortex(_write_md(tmp_path, md))
    assert result["errors"] == []
    assert result["loss_count"] == 0
    assert result["entries"] >= 1


def _write_md(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "review.md"
    p.write_text(text, encoding="utf-8")
    return p
