"""Tests for identity.switch handler (BLP-011).

Covers AC-01..AC-07: happy path, IDENTITY_NOT_FOUND with live list,
dry_run without mutations, content CORTEX override, header with BLP,
PULSE audit and context preservation.
"""

from __future__ import annotations

from pathlib import Path

from arqux.constants import ARQUX_DIR
from arqux.handlers.identity import handler_schemas, switch
from arqux.handlers.session import context_get, context_set
from arqux.permissions import PermissionContext

_ALFRED = PermissionContext(agent_id="alfred", role="governor")

_META_BRAIN = """\
$0

# Sigil | Name | Type | Risk | Cognitive Layer | Description
# DOM   | dom   | attrs| M    | Semantic       | Project domain
# ARQX  | artifact|attrs| B   | Semantic       | Metadata

$0.1: ARQUX METADATA

ARQX:artifact{level:"3", name:"meta-brain", usage:"state", kind:"native"}

$2: PROJECTS

DOM:test-proj{name:"test-proj", path:"test-proj", domain:"test"}
"""

_BRAIN = """\
$0

# Sigil | Name | Type | Risk | Cognitive Layer | Description
# AUD   | aud   | attrs| M    | Semantic       | Audit pulse
# FCS   | focus | attrs| H    | Working        | Focus
# OBJ   | objective|attrs| H  | Working        | Objectives
# ARQX  | artifact|attrs| B   | Semantic       | Metadata

$0.1: ARQUX METADATA

ARQX:artifact{level:"0", name:"brain", usage:"state", kind:"native"}

$2: FOCUS

FCS:current{what:"test", priority:"medium", status:"current"}

$3: OBJECTIVES

OBJ:_{goal:"test session", status:"current", success:"pending"}

$6: PULSE
"""

_IDENTITY = """\
$0

$1: IDENTITY

IDN:{name}{{agent:"{name}", name:"{name}"}}

$2: AXIOMS

AXM:test{{name:"test", status:"current", body:"Test axiom"}}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bootstrap(tmp_path: Path, *, blp: str | None = None) -> tuple[Path, Path]:
    """Create a minimal governed workspace + project and set session context.

    Returns (ws_root, proj_root).
    """
    ws_root = tmp_path
    ws_arqux = tmp_path / ARQUX_DIR
    ws_arqux.mkdir(exist_ok=True)
    (ws_arqux / "meta-brain.cortex").write_text(_META_BRAIN, encoding="utf-8")
    (ws_arqux / "brain.cortex").write_text(_BRAIN, encoding="utf-8")

    identities = ws_arqux / "identities"
    identities.mkdir()
    for name in ("alfred", "jarvis", "heimdall", "seshat"):
        (identities / f"{name}.cortex").write_text(
            _IDENTITY.format(name=name), encoding="utf-8"
        )

    proj_root = tmp_path / "test-proj"
    proj_arqux = proj_root / ARQUX_DIR
    proj_arqux.mkdir(parents=True)
    (proj_arqux / "brain.cortex").write_text(_BRAIN, encoding="utf-8")

    out = context_set(
        project="test-proj", scope="CYCLE-01", blp=blp,
        path=str(ws_root), ctx=_ALFRED,
    )
    assert out.profile == "OUT-WORK", out.to_text()
    return ws_root, proj_root


def _ws_arqux(ws_root: Path) -> Path:
    return ws_root / ARQUX_DIR


# ---------------------------------------------------------------------------
# Registry smoke (R-05)
# ---------------------------------------------------------------------------


def test_identity_registry_exposes_switch() -> None:
    names = [s["name"] for s in handler_schemas]
    assert "identity.get" in names
    assert "identity.switch" in names


# ---------------------------------------------------------------------------
# AC-01 — happy path: contract + header, no direct reads by the agent
# ---------------------------------------------------------------------------


def test_switch_happy_path(tmp_path: Path) -> None:
    ws_root, proj_root = _bootstrap(tmp_path)
    result = switch("jarvis", path=str(proj_root), ctx=_ALFRED)

    assert result.profile == "OUT-WORK", result.to_text()
    assert result.fields["agent_id"] == "jarvis"
    assert result.fields["from_agent"] == "alfred"
    assert result.fields["header"] == "⬡ jarvis | test-proj | CYCLE-01"
    assert "jarvis" in result.fields["contract"]
    assert "alfred" in result.fields["available_identities"]
    assert result.fields["context_updated"] is True


# ---------------------------------------------------------------------------
# AC-02 — IDENTITY_NOT_FOUND with live available identities
# ---------------------------------------------------------------------------


def test_switch_without_path_uses_context_pointer(tmp_path: Path, monkeypatch) -> None:
    """E-2075: path is optional — the execution's context pointer resolves."""
    ws_root, _ = _bootstrap(tmp_path)
    monkeypatch.chdir(ws_root)
    result = switch("jarvis", ctx=_ALFRED)

    assert result.profile == "OUT-WORK", result.to_text()
    assert result.fields["agent_id"] == "jarvis"
    assert result.fields["header"] == "⬡ jarvis | test-proj | CYCLE-01"


def test_switch_not_found_lists_identities(tmp_path: Path) -> None:
    _, proj_root = _bootstrap(tmp_path)
    result = switch("noexiste", path=str(proj_root), ctx=_ALFRED)

    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "IDENTITY_NOT_FOUND"
    available = result.fields.get("available_identities", [])
    assert "alfred" in available
    assert "jarvis" in available


def test_switch_requires_agent_id(tmp_path: Path) -> None:
    _, proj_root = _bootstrap(tmp_path)
    result = switch(path=str(proj_root), ctx=_ALFRED)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "INVALID_ARGS"


# ---------------------------------------------------------------------------
# AC-03 — handoff record + PULSE identity_switch audit
# ---------------------------------------------------------------------------


def test_switch_registers_handoff_and_pulse(tmp_path: Path) -> None:
    ws_root, proj_root = _bootstrap(tmp_path)
    switch("jarvis", path=str(proj_root), ctx=_ALFRED)

    # GRADIENT-12: pending handoffs are HND:<to> entries in the brain's
    # ACTIVE_CONTEXT — the handoffs/ directory is retired.
    brain = (proj_root / ARQUX_DIR / "brain.cortex").read_text(encoding="utf-8")
    assert not (proj_root / ARQUX_DIR / "handoffs").exists()
    assert "HND:jarvis" in brain
    assert 'from:"alfred"' in brain
    assert 'to:"jarvis"' in brain

    # The audit pulse lives in the session timelog $5 EVENTS (GRADIENT-12).
    timelogs = list((proj_root / ARQUX_DIR / "timelog").glob("*.cortex"))
    assert timelogs, "no session timelog found"
    tl_text = "\n".join(t.read_text(encoding="utf-8") for t in timelogs)
    assert "identity_switch" in tl_text


# ---------------------------------------------------------------------------
# AC-04 + AC-07 — context.cortex updated, project/scope/BLP preserved
# ---------------------------------------------------------------------------


def test_switch_updates_context_preserving_scope(tmp_path: Path) -> None:
    ws_root, proj_root = _bootstrap(tmp_path, blp="BLP-011")
    before = context_get(path=str(proj_root), ctx=_ALFRED)

    result = switch("heimdall", path=str(proj_root), ctx=_ALFRED)
    assert result.fields["header"] == "⬡ heimdall | test-proj | CYCLE-01 | BLP-011"

    after = context_get(path=str(proj_root), ctx=_ALFRED)
    assert after.fields["agent"] == "heimdall"
    assert after.fields["project"] == before.fields["project"]
    assert after.fields["scope"] == before.fields["scope"]
    assert after.fields["blp"] == before.fields["blp"]
    assert after.fields["project_root"] == before.fields["project_root"]


# ---------------------------------------------------------------------------
# AC-05 — dry_run mutates nothing
# ---------------------------------------------------------------------------


def test_switch_dry_run_mutates_nothing(tmp_path: Path) -> None:
    ws_root, proj_root = _bootstrap(tmp_path)
    ws_arqux = _ws_arqux(ws_root)
    # The workspace context pointer lives in meta-brain ACTIVE_CONTEXT
    # (WRK:current) — context.cortex is retired (GRADIENT-12).
    ctx_before = (ws_arqux / "meta-brain.cortex").read_text(encoding="utf-8")
    brain_before = (proj_root / ARQUX_DIR / "brain.cortex").read_text(encoding="utf-8")

    result = switch("jarvis", path=str(proj_root), ctx=_ALFRED, dry_run=True)

    assert result.profile == "OUT-WORK"
    assert result.fields["dry_run"] is True
    assert result.fields["context_updated"] is False
    assert result.fields["header"] == "⬡ jarvis | test-proj | CYCLE-01"
    assert (ws_arqux / "meta-brain.cortex").read_text(encoding="utf-8") == ctx_before
    assert (proj_root / ARQUX_DIR / "brain.cortex").read_text(encoding="utf-8") == brain_before
    assert not (proj_root / ARQUX_DIR / "handoffs").exists()


# ---------------------------------------------------------------------------
# AC-06 — content CORTEX override (meta-handler pattern)
# ---------------------------------------------------------------------------


def test_switch_content_cortex_overrides_agent(tmp_path: Path) -> None:
    _, proj_root = _bootstrap(tmp_path)
    result = switch(
        content='agent_id:seshat,summary:"sesion de prueba"',
        path=str(proj_root), ctx=_ALFRED,
    )

    assert result.profile == "OUT-WORK", result.to_text()
    assert result.fields["agent_id"] == "seshat"


# ---------------------------------------------------------------------------
# Reversibility — switch back to alfred (§13 Verificación 3)
# ---------------------------------------------------------------------------


def test_switch_is_reversible(tmp_path: Path) -> None:
    _, proj_root = _bootstrap(tmp_path)
    switch("jarvis", path=str(proj_root), ctx=_ALFRED)
    back = switch("alfred", path=str(proj_root), ctx=_ALFRED)

    assert back.profile == "OUT-WORK"
    assert back.fields["header"] == "⬡ alfred | test-proj | CYCLE-01"
    after = context_get(path=str(proj_root), ctx=_ALFRED)
    assert after.fields["agent"] == "alfred"


# ---------------------------------------------------------------------------
# I002 — repeated switches must never duplicate HND:<to> entries
# ---------------------------------------------------------------------------


def test_switch_repeated_targets_do_not_duplicate_hnd(tmp_path: Path) -> None:
    """I002: each switch to the same agent used to append a second HND:<to>,
    which then blocked every later brain write with I002_DUPLICATE_IDEA_ADDRESS."""
    _, proj_root = _bootstrap(tmp_path)
    brain_path = proj_root / ARQUX_DIR / "brain.cortex"

    for target in ("jarvis", "heimdall", "jarvis", "heimdall"):
        out = switch(target, path=str(proj_root), ctx=_ALFRED)
        assert out.profile == "OUT-WORK", out.to_text()

    brain = brain_path.read_text(encoding="utf-8")
    assert brain.count("HND:jarvis") == 1
    assert brain.count("HND:heimdall") == 1

    # The latest handoff for each target wins (pending handoff is state):
    # exactly one entry per target, addressed as $7/HND:<to>.
    from arqux.core.state._crud import crud_read

    for target in ("jarvis", "heimdall"):
        found = crud_read(brain_path, f"$7/HND:{target}")
        assert len(found["entries"]) == 1, f"HND:{target} duplicated"

    # The brain must stay addressable after the switches (the actual failure
    # mode of I002: later writes/read selectors fail with
    # I002_DUPLICATE_IDEA_ADDRESS). The fixture brain carries pre-existing
    # E032 errors, so check for duplicate diagnostics specifically.
    from arqux.core.state._crud import cortex_verify

    diags = cortex_verify(brain_path).get("diagnostics", [])
    assert not any("I002" in d or "Duplicate" in d for d in diags), diags
