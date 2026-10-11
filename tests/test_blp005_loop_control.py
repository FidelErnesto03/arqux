"""Tests for Amplified Loop control (BLP-005 CA-21).

The loop is allowed to work without asking, but not without reporting and
not without stopping. These tests pin the three limits and the one
behaviour that is easy to get wrong: a control window is a courtesy, and
its expiry is not an approval.
"""

from __future__ import annotations

from arqux.handlers.loop_control import (
    BLUEPRINTS_PER_WINDOW,
    MAX_ATTEMPTS_PER_BLUEPRINT,
    MAX_BLUEPRINTS_PER_VALIDATION,
    LoopController,
    LoopState,
    check,
    record_attempt,
    summary,
)

# ---------------------------------------------------------------------------
# Attempt budget — rule 29
# ---------------------------------------------------------------------------


def test_attempt_budget_stops_a_deterministic_retry_loop() -> None:
    """Rule 29 promises three rounds; the budget must deliver three.

    Heimdall V-4: the original ``used >= limit`` check refused the last
    permitted attempt, so a limit of three ran two rounds.
    """
    ctrl = LoopController()
    rounds = [ctrl.attempt("BLP-005") for _ in range(MAX_ATTEMPTS_PER_BLUEPRINT)]
    assert [v.action for v in rounds] == ["continue"] * MAX_ATTEMPTS_PER_BLUEPRINT

    verdict = ctrl.attempt("BLP-005")
    assert verdict.action == "escalate"
    assert verdict.reason == "attempt_budget_exhausted"
    assert "32" in verdict.detail, "escalation must name the rule"


def test_attempts_are_counted_per_blueprint() -> None:
    ctrl = LoopController()
    for _ in range(2):
        ctrl.attempt("BLP-001")
    ctrl.attempt("BLP-002")
    assert ctrl.state.attempts_for("BLP-001") == 2
    assert ctrl.state.attempts_for("BLP-002") == 1


def test_attempt_state_is_not_mutated_in_place() -> None:
    """Immutable state means a PULSE record captures what actually happened."""
    state = LoopState()
    record_attempt(state, "BLP-001")
    assert state.attempts_for("BLP-001") == 0


# ---------------------------------------------------------------------------
# Validation budget — rule 30
# ---------------------------------------------------------------------------


def test_validation_budget_escalates_after_five_unvalidated_closures() -> None:
    ctrl = LoopController()
    for _ in range(MAX_BLUEPRINTS_PER_VALIDATION - 1):
        ctrl.close(validated=False)
    verdict = ctrl.close(validated=False)
    assert verdict.action == "escalate"
    assert verdict.reason == "validation_budget_exhausted"


def test_validated_closure_does_not_consume_the_validation_budget() -> None:
    ctrl = LoopController()
    for _ in range(10):
        ctrl.close(validated=True)
    assert ctrl.state.without_validation == 0


def test_escalation_outranks_a_due_window() -> None:
    """Exhausting the validation budget is more urgent than a checkpoint."""
    # Both limits come due on the same closure: the third unvalidated
    # blueprint trips the window cadence and the validation budget.
    ctrl = LoopController(
        LoopState(
            closed=BLUEPRINTS_PER_WINDOW - 1,
            without_validation=MAX_BLUEPRINTS_PER_VALIDATION - 1,
        )
    )
    verdict = ctrl.close(validated=False)
    assert verdict.action == "escalate"


def test_a_validated_closure_resets_the_unvalidated_run() -> None:
    """Rule 30 counts an unbroken run, not the cycle's whole history."""
    ctrl = LoopController(LoopState(without_validation=3))
    ctrl.close(validated=True)
    assert ctrl.state.without_validation == 0


# ---------------------------------------------------------------------------
# Control window — CP-07
# ---------------------------------------------------------------------------


def test_window_opens_after_three_closed_blueprints() -> None:
    ctrl = LoopController()
    actions = [ctrl.close().action for _ in range(BLUEPRINTS_PER_WINDOW)]
    assert actions == ["continue", "continue", "open_window"]


def test_window_counter_resets_when_the_window_opens() -> None:
    ctrl = LoopController()
    for _ in range(BLUEPRINTS_PER_WINDOW):
        ctrl.close()
    assert ctrl.state.closed == 0, "the cadence must restart, not accumulate forever"
    assert ctrl.state.windows == 1


def test_window_expiry_is_not_an_approval_gate() -> None:
    """CP-07: the window is courtesy. Nothing blocks after it lapses."""
    ctrl = LoopController()
    for _ in range(BLUEPRINTS_PER_WINDOW):
        ctrl.close()
    ctrl.window_lapsed()
    assert ctrl.due().action == "continue"
    assert ctrl.close().action == "continue"


def test_check_reports_a_due_window_before_new_work_starts() -> None:
    """A loop due to yield should yield before opening a fresh blueprint."""
    state = LoopState(closed=BLUEPRINTS_PER_WINDOW)
    verdict = check(state)
    assert verdict.action == "open_window"
    assert verdict.yields is True


def test_check_is_quiet_when_nothing_is_due() -> None:
    verdict = check(LoopState())
    assert verdict.action == "continue"
    assert verdict.yields is False


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def test_summary_shows_the_countdown_explicitly() -> None:
    state = LoopState(closed=1, without_validation=2, attempts={"BLP-005": 2})
    data = summary(state)
    assert data["window"] == f"1/{BLUEPRINTS_PER_WINDOW}"
    assert data["attempts"] == {"BLP-005": 2}
    assert data["without_validation"] == 2


def test_summary_flags_a_due_window_rather_than_a_bare_number() -> None:
    data = summary(LoopState(closed=BLUEPRINTS_PER_WINDOW))
    assert data["window"] == "due"
