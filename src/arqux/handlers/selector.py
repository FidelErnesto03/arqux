"""Objective selector for the Amplified Autonomous Loop (BLP-005).

The loop's unit of work is the *cycle objective*, not the blueprint. This
module answers one question: **given what is true right now, which
objective should the loop act on next?**

Design constraints (BLP-005 §8, rules 26 to 30):

* **Truth comes from the index, not the claim.** A ``- [x]`` checkbox in §3
  is a *declaration*, not evidence. Rule R-09 treats a gate declared closed
  without verification as a defect, so this module derives completion from
  the blueprint states in §6 and treats the checkbox as an unverified
  claim. When the two disagree, the disagreement is reported.
* **A draft blueprint is not work.** Rule 27: a blueprint the loop created
  stays ``draft`` until Heimdall validates it. An objective whose only
  blueprints are drafts is therefore *blocked on validation*, not ready.
* **The selector proposes, the auditor disposes.** Selecting an objective
  never authorises anything. It only names the next target.
* **Order is declaration order.** Objectives are ranked by the order §3
  declares them, not by a computed score. Determinism beats cleverness when
  the loop must be able to explain itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Blueprint states that close an objective's contribution. ``cancelled``
# counts because a withdrawn blueprint is a decision, not a failure.
TERMINAL_STATES = frozenset({"done", "cancelled"})

# States that mean the blueprint is being worked on right now.
ACTIVE_STATES = frozenset({"ready", "in_progress", "review", "blocked"})

# BLP-005 CA-20 (Heimdall V-1, V-3). Every state the selector is willing to
# interpret. Anything outside this set is refused rather than guessed: a
# typo like ``en_revision_xx`` must stop the loop, never pass as work in
# flight. Failing open here would let the loop act on a blueprint whose
# real state nobody can read, which is the fabricated-progress defect this
# module exists to prevent.
KNOWN_STATES = TERMINAL_STATES | ACTIVE_STATES | frozenset({"draft"})

_OBJECTIVE_RE = re.compile(
    r"^-\s*\[(?P<mark>[ xX])\]\s*\*\*"
    r"(?P<oid>CYC-OBJ-\d+)"
    r"(?:\s*\([^)]*\))?:\s*"
    r"(?P<title>[^*]*?)\s*\.?\s*\*\*",
    re.MULTILINE,
)

_BLUEPRINTS_RE = re.compile(
    r"^\s*\*Blueprints:\*?\s*(?P<bids>.+?)\s*$",
    re.MULTILINE,
)

_BID_RE = re.compile(r"BLP-\d+")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SelectorError(Exception):
    """Raised when the manifest cannot be read as a cycle plan.

    ``code`` is stable and machine-readable: ``no_section`` when §3 or §6
    is missing or malformed, ``malformed_index`` when §6 has no usable
    header.
    """

    def __init__(self, message: str, code: str = "no_section") -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Objective:
    """One declared cycle objective from §3."""

    objective_id: str
    title: str
    blueprints: tuple[str, ...] = ()
    declared_done: bool = False


@dataclass(frozen=True)
class BlueprintRow:
    """One row of the §6 blueprint index."""

    blueprint_id: str
    title: str = ""
    status: str = ""
    priority: str = "medium"
    objective: str = ""
    governor: str = ""


@dataclass(frozen=True)
class Assessment:
    """The selector's verdict on a single objective.

    ``state`` is one of:

    ``met``        every linked blueprint reached a terminal state
    ``active``     at least one linked blueprint is being worked on
    ``awaiting_validation``  blueprints exist but are all still ``draft``
    ``needs_blueprint``      no blueprint serves this objective yet
    ``blocked``    a linked blueprint is ``blocked`` and none can proceed
    ``unknown_state``  a linked blueprint carries a state we cannot read
    """

    objective: Objective
    state: str
    detail: str = ""
    statuses: tuple[tuple[str, str], ...] = ()

    @property
    def satisfied(self) -> bool:
        return self.state == "met"

    @property
    def actionable(self) -> bool:
        """True when the loop may act on this objective."""
        return self.state in ("active", "awaiting_validation", "needs_blueprint")


@dataclass(frozen=True)
class Selection:
    """Result of a selection pass over one manifest."""

    assessment: Assessment | None
    reason: str
    detail: str = ""
    order: tuple[Assessment, ...] = field(default=())

    @property
    def objective_id(self) -> str | None:
        return self.assessment.objective.objective_id if self.assessment else None

    @property
    def found(self) -> bool:
        return self.assessment is not None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _section(manifest: str, number: int) -> str:
    pattern = re.compile(
        rf"(?:<!--\s*CYCLE:{number}\s*-->\s*)?"
        rf"(## §{number}:[^\n]*\n)(.*?)"
        rf"(?:<!--\s*/CYCLE:{number}\s*-->|\n## §\d+:|\Z)",
        re.DOTALL,
    )
    found = pattern.search(manifest)
    if not found:
        raise SelectorError(
            f"manifest has no §{number}", code="no_section"
        )
    return found.group(2)


def parse_objectives(manifest: str) -> tuple[Objective, ...]:
    """Parse §3 into objectives, in declaration order.

    Args:
        manifest: Full MANIFEST.md text.

    Returns:
        Objectives in the order §3 declares them.

    Raises:
        SelectorError: if §3 is absent or declares no objectives.
    """
    try:
        body = _section(manifest, 3)
    except SelectorError as exc:
        raise SelectorError("manifest has no §3", code="no_section") from exc

    matches = list(_OBJECTIVE_RE.finditer(body))
    if not matches:
        raise SelectorError(
            "§3 declares no objectives in the expected form",
            code="no_section",
        )

    objectives: list[Objective] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        block = body[match.start() : end]
        blp_match = _BLUEPRINTS_RE.search(block)
        bids = tuple(_BID_RE.findall(blp_match.group("bids"))) if blp_match else ()
        objectives.append(
            Objective(
                objective_id=match.group("oid"),
                title=match.group("title").strip(),
                blueprints=bids,
                declared_done=match.group("mark").lower() == "x",
            )
        )
    return tuple(objectives)


def parse_index(manifest: str) -> tuple[BlueprintRow, ...]:
    """Parse the §6 blueprint index.

    Columns are resolved by header name, so a manifest whose columns were
    written in a different order still parses.

    Args:
        manifest: Full MANIFEST.md text.

    Returns:
        One row per blueprint declared in §6.

    Raises:
        SelectorError: if §6 is absent or has no recognisable header.
    """
    try:
        body = _section(manifest, 6)
    except SelectorError as exc:
        raise SelectorError("manifest has no §6", code="no_section") from exc

    rows: list[BlueprintRow] = []
    header: dict[str, int] = {}
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if header:
                break
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") and c for c in cells):
            continue  # separator row
        if not header:
            header = {c.lower(): i for i, c in enumerate(cells)}
            if "blp id" not in header:
                header = {}
                continue
            continue
        if len(cells) <= header["blp id"]:
            continue
        bid = cells[header["blp id"]]
        if not _BID_RE.fullmatch(bid):
            continue

        def cell(name: str, header=header, cells=cells) -> str:
            index = header.get(name, -1)
            if 0 <= index < len(cells) and cells[index] not in ("", "—"):
                return cells[index]
            return ""

        rows.append(
            BlueprintRow(
                blueprint_id=bid,
                title=cell("título") or cell("titulo"),
                # Heimdall V-3: an empty cell stays empty. Defaulting it to
                # ``draft`` would silently block an objective on a guess.
                status=cell("estado"),
                priority=cell("prioridad") or "medium",
                objective=cell("objetivo"),
                governor=cell("gobernador"),
            )
        )
    if not header:
        raise SelectorError("§6 index has no usable header", code="malformed_index")
    return tuple(rows)


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


def _assess(objective: Objective, statuses: dict[str, str]) -> Assessment:
    linked = tuple((bid, statuses.get(bid, "missing")) for bid in objective.blueprints)

    if not linked:
        return Assessment(
            objective,
            "needs_blueprint",
            "no blueprint serves this objective yet (rule 26: create one in draft)",
            linked,
        )

    values = {status for _, status in linked}
    if "missing" in values:
        absent = ", ".join(bid for bid, status in linked if status == "missing")
        return Assessment(
            objective,
            "needs_blueprint",
            f"no index row for {absent}; rule 26 requires one in draft",
            linked,
        )
    unknown = sorted(values - KNOWN_STATES)
    if unknown:
        # Heimdall V-1: refuse to interpret what we cannot read.
        return Assessment(
            objective,
            "unknown_state",
            "unrecognised blueprint state(s) "
            + ", ".join(repr(u) for u in unknown)
            + "; the selector will not assume progress on an unreadable state",
            linked,
        )
    if values <= TERMINAL_STATES:
        return Assessment(
            objective,
            "met",
            "every linked blueprint reached a terminal state",
            linked,
        )
    if values & ACTIVE_STATES:
        blocked_only = values <= {"blocked"}
        return Assessment(
            objective,
            "blocked" if blocked_only else "active",
            "a linked blueprint is blocked" if blocked_only else "work is in flight",
            linked,
        )
    if values <= {"draft"}:
        return Assessment(
            objective,
            "awaiting_validation",
            "all linked blueprints are draft; rule 27 requires Heimdall validation",
            linked,
        )
    return Assessment(objective, "active", "unclassified blueprint states", linked)


def assess_objectives(
    manifest: str, statuses: dict[str, str] | None = None
) -> tuple[Assessment, ...]:
    """Assess every objective declared in §3.

    Args:
        manifest: Full MANIFEST.md text.
        statuses: Blueprint id to state. Defaults to the states read from
            §6. Pass an explicit map when the caller holds fresher state
            than the manifest, for example after a reconciliation.

    Returns:
        One assessment per objective, in declaration order.

    Raises:
        SelectorError: if §3 or §6 cannot be parsed.
    """
    objectives = parse_objectives(manifest)
    if statuses is None:
        statuses = {row.blueprint_id: row.status for row in parse_index(manifest)}
    return tuple(_assess(obj, statuses) for obj in objectives)


def select_next_objective(
    manifest: str, statuses: dict[str, str] | None = None
) -> Selection:
    """Choose the objective the loop should act on next.

    Selection is by declaration order: the first objective that is not
    satisfied and is actionable. An objective already in flight wins over
    one that still needs a blueprint, because finishing work in progress
    is worth more than starting more.

    Args:
        manifest: Full MANIFEST.md text.
        statuses: Blueprint id to state; defaults to §6.

    Returns:
        A :class:`Selection`. ``reason`` is one of ``selected``,
        ``cycle_complete``, or ``nothing_actionable``.

    Raises:
        SelectorError: if §3 or §6 cannot be parsed.
    """
    assessments = assess_objectives(manifest, statuses)

    if all(item.satisfied for item in assessments):
        return Selection(
            None,
            "cycle_complete",
            "every declared objective is satisfied",
            assessments,
        )

    for item in assessments:
        if item.actionable:
            return Selection(
                item, "selected", item.detail, assessments
            )

    return Selection(
        None,
        "nothing_actionable",
        "the remaining objectives are blocked; rule 32 requires escalation",
        assessments,
    )


def selection_summary(selection: Selection) -> dict[str, Any]:
    """Render a selection as a plain dict for PULSE records and replies.

    Args:
        selection: Result of :func:`select_next_objective`.

    Returns:
        A JSON-serialisable summary.
    """
    return {
        "objective": selection.objective_id,
        "reason": selection.reason,
        "detail": selection.detail,
        "state": selection.assessment.state if selection.assessment else None,
        "order": [
            {
                "objective": item.objective.objective_id,
                "title": item.objective.title,
                "state": item.state,
                "detail": item.detail,
                "blueprints": [
                    {"id": bid, "status": status} for bid, status in item.statuses
                ],
                "declared_done": item.objective.declared_done,
            }
            for item in selection.order
        ],
    }
