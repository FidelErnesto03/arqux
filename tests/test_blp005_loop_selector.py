"""Tests for the Amplified Loop objective selector (BLP-005 CA-20).

The selector's contract is narrow: it names the next objective the loop
should act on, and refuses to treat a declaration as evidence. These tests
pin both halves, because the second half is the one that matters — rule
R-09 exists precisely because a gate declared closed is not a gate.
"""

from __future__ import annotations

import pytest

from arqux.handlers.selector import (
    SelectorError,
    assess_objectives,
    parse_index,
    parse_objectives,
    select_next_objective,
    selection_summary,
)


def _manifest(objectives: str, index_rows: str) -> str:
    """Build a minimal but structurally complete cycle manifest."""
    return f"""---
cycle_id: CYCLE-T
---

# Manifiesto

## §3: Objetivos

<!-- CYCLE:3 -->
{objectives}
<!-- /CYCLE:3 -->

## §6: Blueprints (Índice)

<!-- CYCLE:6 -->
| BLP ID | Título | Estado | Prioridad | Objetivo | Gobernador |
|---|---|---|---|---|---|
{index_rows}
<!-- /CYCLE:6 -->

## §8: Reglas

<!-- CYCLE:8 -->
fin
<!-- /CYCLE:8 -->
"""


def _obj(oid: str, mark: str = " ", bids: str = "") -> str:
    """One objective in the canonical §3 form used by the real manifest."""
    line = f"- [{mark}] **{oid} (OBJ): Propósito de {oid}.**"
    if bids:
        line += f"\n  *Blueprints:* {bids}."
    return line


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parses_objectives_in_declaration_order() -> None:
    manifest = _manifest(
        _obj("CYC-OBJ-1", bids="BLP-001.") + "\n" + _obj("CYC-OBJ-2", bids="BLP-002."),
        "",
    )
    parsed = parse_objectives(manifest)
    assert [o.objective_id for o in parsed] == ["CYC-OBJ-1", "CYC-OBJ-2"]
    assert parsed[0].blueprints == ("BLP-001",)
    assert parsed[1].title.startswith("Propósito")


def test_parses_index_columns_by_header_name() -> None:
    manifest = _manifest(
        _obj("CYC-OBJ-1"),
        "| BLP-001 | Memory Core | done | high | CYC-OBJ-1 | alfred |\n",
    )
    rows = parse_index(manifest)
    assert len(rows) == 1
    assert rows[0].status == "done"
    assert rows[0].priority == "high"
    assert rows[0].objective == "CYC-OBJ-1"
    assert rows[0].governor == "alfred"


def test_missing_objectives_section_is_rejected() -> None:
    with pytest.raises(SelectorError):
        parse_objectives("## §6: something\n| BLP ID |\n|---|\n")


def test_missing_index_section_is_rejected() -> None:
    manifest = _manifest(_obj("CYC-OBJ-1"), "").replace(
        "## §6: Blueprints (Índice)", "## §X: Another Section"
    )
    with pytest.raises(SelectorError):
        parse_index(manifest)


# ---------------------------------------------------------------------------
# Truth beats declaration
# ---------------------------------------------------------------------------


def test_checkbox_x_is_not_treated_as_proof() -> None:
    """A checked objective whose blueprint is not done is not met."""
    manifest = _manifest(
        _obj("CYC-OBJ-1", mark="x", bids="BLP-001."),
        "| BLP-001 | Memory Core | in_progress | medium | CYC-OBJ-1 | alfred |\n",
    )
    assessment = assess_objectives(manifest)[0]
    assert assessment.objective.declared_done is True
    assert assessment.state == "active", "a claim must not satisfy an objective"
    assert assessment.satisfied is False


def test_objective_met_only_when_every_blueprint_is_terminal() -> None:
    manifest = _manifest(
        _obj("CYC-OBJ-1", bids="BLP-001, BLP-002."),
        "| BLP-001 | A | done | medium | CYC-OBJ-1 | alfred |\n"
        "| BLP-002 | B | in_progress | medium | CYC-OBJ-1 | alfred |\n",
    )
    assert assess_objectives(manifest)[0].state == "active"

    manifest = _manifest(
        _obj("CYC-OBJ-1", bids="BLP-001, BLP-002."),
        "| BLP-001 | A | done | medium | CYC-OBJ-1 | alfred |\n"
        "| BLP-002 | B | cancelled | medium | CYC-OBJ-1 | alfred |\n",
    )
    assert assess_objectives(manifest)[0].state == "met"


def test_cancelled_counts_as_terminal() -> None:
    manifest = _manifest(
        _obj("CYC-OBJ-1", bids="BLP-001."),
        "| BLP-001 | Withdrawn | cancelled | low | CYC-OBJ-1 | alfred |\n",
    )
    assert assess_objectives(manifest)[0].state == "met"


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def test_selects_first_unsatisfied_objective() -> None:
    manifest = _manifest(
        "\n".join([_obj("CYC-OBJ-1", bids="BLP-001."), _obj("CYC-OBJ-2", bids="BLP-002.")]),
        "| BLP-001 | A | done | medium | CYC-OBJ-1 | alfred |\n"
        "| BLP-002 | B | ready | medium | CYC-OBJ-2 | alfred |\n",
    )
    selection = select_next_objective(manifest)
    assert selection.objective_id == "CYC-OBJ-2"
    assert selection.reason == "selected"


def test_work_in_flight_wins_over_objective_needing_a_blueprint() -> None:
    manifest = _manifest(
        "\n".join([_obj("CYC-OBJ-1", bids="BLP-001."), _obj("CYC-OBJ-2")]),
        "| BLP-001 | A | in_progress | medium | CYC-OBJ-1 | alfred |\n",
    )
    selection = select_next_objective(manifest)
    assert selection.objective_id == "CYC-OBJ-1", "finish before starting new work"


def test_objective_without_blueprint_is_actionable() -> None:
    manifest = _manifest(_obj("CYC-OBJ-1"), "")
    selection = select_next_objective(manifest)
    assert selection.objective_id == "CYC-OBJ-1"
    assert selection.assessment.state == "needs_blueprint"


def test_draft_blueprint_waits_for_validation() -> None:
    """Rule 27: a loop-created draft is never ready until Heimdall rules."""
    manifest = _manifest(
        _obj("CYC-OBJ-1", bids="BLP-001."),
        "| BLP-001 | Created by loop | draft | medium | CYC-OBJ-1 | alfred |\n",
    )
    assessment = assess_objectives(manifest)[0]
    assert assessment.state == "awaiting_validation"
    assert "Heimdall" in assessment.detail


def test_blocked_objective_is_not_actionable_and_reports_escalation() -> None:
    manifest = _manifest(
        _obj("CYC-OBJ-1", bids="BLP-001."), "| BLP-001 | A | blocked | high | CYC-OBJ-1 | alfred |\n"
    )
    selection = select_next_objective(manifest)
    assert selection.found is False
    assert selection.reason == "nothing_actionable"
    assert "32" in selection.detail


def test_cycle_complete_when_every_objective_is_terminal() -> None:
    manifest = _manifest(
        "\n".join([_obj("CYC-OBJ-1", bids="BLP-001."), _obj("CYC-OBJ-2", bids="BLP-002.")]),
        "| BLP-001 | A | done | medium | CYC-OBJ-1 | alfred |\n"
        "| BLP-002 | B | done | medium | CYC-OBJ-2 | alfred |\n",
    )
    selection = select_next_objective(manifest)
    assert selection.reason == "cycle_complete"
    assert selection.objective_id is None


def test_explicit_statuses_override_manifest_index() -> None:
    """The caller may hold fresher state than the manifest on disk."""
    manifest = _manifest(
        _obj("CYC-OBJ-1", bids="BLP-001."), "| BLP-001 | A | draft | medium | CYC-OBJ-1 | alfred |\n"
    )
    assert assess_objectives(manifest)[0].state == "awaiting_validation"
    fresh = assess_objectives(manifest, {"BLP-001": "done"})
    assert fresh[0].state == "met"


def test_blueprint_missing_from_index_is_not_assumed_done() -> None:
    manifest = _manifest(_obj("CYC-OBJ-1", bids="BLP-999."), "")
    assert assess_objectives(manifest)[0].state == "needs_blueprint"


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def test_summary_is_serialisable_and_carries_the_order() -> None:
    manifest = _manifest(
        "\n".join([_obj("CYC-OBJ-1", bids="BLP-001."), _obj("CYC-OBJ-2", bids="BLP-002.")]),
        "| BLP-001 | A | done | medium | CYC-OBJ-1 | alfred |\n"
        "| BLP-002 | B | ready | medium | CYC-OBJ-2 | alfred |\n",
    )
    summary = selection_summary(select_next_objective(manifest))
    assert summary["objective"] == "CYC-OBJ-2"
    assert [item["objective"] for item in summary["order"]] == ["CYC-OBJ-1", "CYC-OBJ-2"]
    assert summary["order"][1]["blueprints"] == [{"id": "BLP-002", "status": "ready"}]


def test_summary_survives_a_cycle_with_no_selection() -> None:
    manifest = _manifest(
        _obj("CYC-OBJ-1", bids="BLP-001."), "| BLP-001 | A | blocked | high | CYC-OBJ-1 | a |\n"
    )
    summary = selection_summary(select_next_objective(manifest))
    assert summary["objective"] is None
    assert summary["state"] is None
    assert summary["reason"] == "nothing_actionable"

# ---------------------------------------------------------------------------
# Heimdall HD findings: the selector must fail closed
# ---------------------------------------------------------------------------


def test_v1_unrecognised_state_is_refused_not_assumed_progress() -> None:
    """HD-V1: a state we cannot read must stop the loop, not pass as work.

    The original code fell through to ``active`` for anything unhandled,
    so a typo like ``en_revision_xx`` read as work in flight. Failing open
    is the fabricated-progress defect the module exists to prevent.
    """
    manifest = _manifest(
        _obj("CYC-OBJ-1", bids="BLP-001."),
        "| BLP-001 | T | en_revision_xx | medium | CYC-OBJ-1 | a |\n",
    )
    assessment = assess_objectives(manifest)[0]
    assert assessment.state == "unknown_state"
    assert assessment.actionable is False
    assert "en_revision_xx" in assessment.detail


def test_v1_unknown_state_blocks_selection() -> None:
    manifest = _manifest(
        _obj("CYC-OBJ-1", bids="BLP-001."),
        "| BLP-001 | T | ??? | medium | CYC-OBJ-1 | a |\n",
    )
    selection = select_next_objective(manifest)
    assert selection.found is False
    assert selection.reason == "nothing_actionable"


def test_v3_empty_state_cell_is_not_silently_read_as_draft() -> None:
    """HD-V3: an empty cell must not guess. It must refuse."""
    manifest = _manifest(
        _obj("CYC-OBJ-1", bids="BLP-001."),
        "| BLP-001 | T |  | medium | CYC-OBJ-1 | a |\n",
    )
    assessment = assess_objectives(manifest)[0]
    assert assessment.state == "unknown_state"
    assert assessment.actionable is False
