"""Loop control for the Amplified Autonomous Loop (BLP-005 CA-21).

The selector decides *what* to work on. This module decides *when to stop
and check in*. An autonomous loop that never surfaces its state is
indistinguishable from a loop that has silently gone wrong.

Three limits, from §8 of the manifest:

* **Attempts per blueprint** (rule 29, three). A deterministic failure
  retried forever is a hung loop wearing the costume of a busy one.
* **Blueprints per validation** (rule 30, five). Work may accumulate, but
  not indefinitely without Heimdall ruling on it.
* **Control window** (CP-07, every three closed blueprints, twenty
  seconds). The window is a *courtesy*, not an approval gate. It gives
  the Architect a moment to redirect, and it expires on its own. Absent
  intervention, the loop continues.

This module holds the arithmetic only. It performs no waiting, no sleeping
and no I/O, so the caller owns the clock. That split keeps the rules
testable without making tests slow.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

#: Rule 29. Retries of a single blueprint before the loop escalates.
MAX_ATTEMPTS_PER_BLUEPRINT = 3

#: Rule 30. Blueprints that may close without a Heimdall ruling.
MAX_BLUEPRINTS_PER_VALIDATION = 5

#: CP-07. Closed blueprints between control windows.
BLUEPRINTS_PER_WINDOW = 3

#: CP-07. How long a window stays open, in seconds.
WINDOW_SECONDS = 20


class LoopControlError(Exception):
    """Raised when loop control state is inconsistent."""

    def __init__(self, message: str, code: str = "invalid_state") -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Verdict:
    """What the loop should do after consulting this module.

    ``action`` is one of:

    ``continue``      keep working; nothing is due
    ``open_window``   surface the window and yield the turn
    ``escalate``      a hard limit was reached; rule 32 requires the Architect
    """

    action: str
    reason: str = ""
    detail: str = ""
    state: LoopState | None = None

    @property
    def yields(self) -> bool:
        """True when the caller must yield the turn instead of continuing."""
        return self.action in ("open_window", "escalate")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoopState:
    """Immutable loop bookkeeping.

    Frozen because a control rule that cannot be reasoned about after the
    fact is not a control. Callers transition with :func:`with_*` helpers
    rather than mutating in place, so a PULSE record can capture the exact
    state that produced a verdict.

    Attributes:
        closed: Blueprints closed since the last control window.
        without_validation: Blueprints closed without a Heimdall ruling.
        attempts: Per-blueprint attempt counters.
        windows: Control windows opened so far.
        lapsed: Control windows that expired without intervention.
    """

    closed: int = 0
    without_validation: int = 0
    attempts: dict[str, int] = field(default_factory=dict)
    windows: int = 0
    lapsed: int = 0

    def attempts_for(self, blueprint_id: str) -> int:
        return self.attempts.get(blueprint_id, 0)


def _with(state: LoopState, **changes: Any) -> LoopState:
    # Copy the attempt map so a new state never shares mutable state with
    # the old one, while still honouring an explicit replacement.
    changes.setdefault("attempts", dict(state.attempts))
    return replace(state, **changes)


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------


def record_attempt(
    state: LoopState, blueprint_id: str, limit: int = MAX_ATTEMPTS_PER_BLUEPRINT
) -> Verdict:
    """Count one attempt at a blueprint and judge the retry budget.

    Args:
        state: Current loop state.
        blueprint_id: Blueprint being attempted.
        limit: Maximum attempts before escalation.

    Returns:
        A :class:`Verdict`. ``escalate`` once the limit is reached, so the
        loop stops re-running a deterministic failure (R-16).
    """
    used = state.attempts_for(blueprint_id) + 1
    new_state = _with(state, attempts={**state.attempts, blueprint_id: used})
    # Heimdall V-4: escalate only *after* the budget is spent. The previous
    # ``used >= limit`` refused the last permitted attempt, so a limit of
    # three ran two rounds while the rule promised three.
    if used > limit:
        return Verdict(
            "escalate",
            "attempt_budget_exhausted",
            f"{blueprint_id} reached {used}/{limit} attempts; rule 32 requires "
            f"the Architect before a deterministic failure is retried again",
            new_state,
        )
    return Verdict(
        "continue",
        "attempt_recorded",
        f"{blueprint_id} attempt {used}/{limit}",
        new_state,
    )


def record_close(
    state: LoopState, validated: bool = True, window_every: int = BLUEPRINTS_PER_WINDOW
) -> Verdict:
    """Count a closed blueprint and report whether a window is due.

    A validated close does not count against the validation budget but
    still counts toward the window cadence: the Architect sees progress
    either way.

    Args:
        state: Current loop state.
        validated: Whether Heimdall ruled the blueprint conforme first.
        window_every: Closed blueprints between windows.

    Returns:
        A :class:`Verdict`. ``escalate`` takes precedence over
        ``open_window``: exhausting the validation budget is more urgent
        than a routine checkpoint.
    """
    closed = state.closed + 1
    pending = 0 if validated else state.without_validation + 1
    new_state = _with(state, closed=closed, without_validation=pending)

    if pending >= MAX_BLUEPRINTS_PER_VALIDATION:
        return Verdict(
            "escalate",
            "validation_budget_exhausted",
            f"{pending} blueprints closed without a Heimdall ruling; rule 30 "
            f"stops the loop at {MAX_BLUEPRINTS_PER_VALIDATION}",
            new_state,
        )
    if closed >= window_every:
        return Verdict(
            "open_window",
            "window_due",
            f"{closed} blueprints closed; CP-07 opens a {WINDOW_SECONDS}s window",
            _with(new_state, closed=0, windows=new_state.windows + 1),
        )
    return Verdict(
        "continue",
        "progress",
        f"{closed}/{window_every} blueprints toward the next window",
        new_state,
    )


def note_window_closed(state: LoopState) -> LoopState:
    """Record that the control window expired without intervention.

    CP-07 defines the window as a courtesy: its expiry is a normal event,
    not an approval. This records the expiry so the cadence and the PULSE
    trail agree.

    Heimdall V-5: this function used to return its argument unchanged
    while promising to record the closure. A function whose name claims a
    record and writes none is worse than no function, because callers
    trust the name.

    Args:
        state: State as returned by :func:`record_close`.

    Returns:
        The state with ``lapsed`` incremented.
    """
    return _with(state, lapsed=state.lapsed + 1)


def check(state: LoopState, window_every: int = BLUEPRINTS_PER_WINDOW) -> Verdict:
    """Ask whether the loop must stop right now.

    Useful before selecting new work, so a loop that is due to yield does
    so before it opens a fresh blueprint.

    Args:
        state: Current loop state.
        window_every: Closed blueprints between windows.

    Returns:
        A :class:`Verdict`; ``continue`` when nothing is due.
    """
    if state.without_validation >= MAX_BLUEPRINTS_PER_VALIDATION:
        return Verdict(
            "escalate",
            "validation_budget_exhausted",
            f"{state.without_validation} blueprints closed without a ruling",
            state,
        )
    if state.closed >= window_every:
        return Verdict(
            "open_window",
            "window_due",
            f"{state.closed} blueprints closed and no window opened yet",
            state,
        )
    return Verdict("continue", "clear", "no limit reached", state)


def summary(state: LoopState, window_every: int = BLUEPRINTS_PER_WINDOW) -> dict[str, Any]:
    """Render loop state as a plain dict for §7 and PULSE records.

    Args:
        state: Current loop state.
        window_every: Closed blueprints between windows.

    Returns:
        A JSON-serialisable summary with an explicit ``window`` line so
        the manifest shows the countdown rather than implying it.
    """
    return {
        "closed_since_window": state.closed,
        "window_every": window_every,
        "windows_opened": state.windows,
        "windows_lapsed": state.lapsed,
        "without_validation": state.without_validation,
        "validation_limit": MAX_BLUEPRINTS_PER_VALIDATION,
        "attempts": dict(state.attempts),
        "window": (
            "due" if state.closed >= window_every else f"{state.closed}/{window_every}"
        ),
    }


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


class LoopController:
    """Holds loop state across a sequence of transitions.

    The module-level functions are pure: each returns the next state in
    its verdict, and the caller must thread it. That is right for tests
    and audits, but it is also easy to get wrong — call the function, read
    ``verdict.action``, discard ``verdict.state``, and the retry budget
    silently resets on every call. A safety limit that fails open is not a
    safety limit.

    This controller makes the correct usage the easy one: state is held
    internally and advanced on every transition, so a caller cannot lose
    the budget by ignoring a return value.
    """

    def __init__(
        self, state: LoopState | None = None, window_every: int = BLUEPRINTS_PER_WINDOW
    ) -> None:
        self.state = state or LoopState()
        self.window_every = window_every

    def attempt(self, blueprint_id: str) -> Verdict:
        """Record an attempt and advance the stored state."""
        verdict = record_attempt(self.state, blueprint_id)
        self.state = verdict.state
        return verdict

    def close(self, validated: bool = True) -> Verdict:
        """Record a closed blueprint and advance the stored state."""
        verdict = record_close(self.state, validated, self.window_every)
        self.state = verdict.state
        return verdict

    def due(self) -> Verdict:
        """Ask whether the loop must yield, without advancing state."""
        return check(self.state, self.window_every)

    def window_lapsed(self) -> None:
        """Acknowledge that a control window expired unattended."""
        self.state = note_window_closed(self.state)

    def summary(self) -> dict[str, Any]:
        """Render the stored state for §7 and PULSE records."""
        return summary(self.state, self.window_every)
