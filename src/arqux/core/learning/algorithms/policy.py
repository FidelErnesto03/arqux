"""Policy loading and lookup for the learning engine (BLP-003).

Supports the 6 configuration blocks required by BLP-003 (THR, PRT, POL,
fibonacci_thresholds, cooling, detection, feedback, protected_patterns)
plus elevation rules (``POL`` sigil with from/to/tier/threshold).

Policies are safety-critical: malformed input raises (never silently accepted).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..errors import LE011_PolicyParseError
from .conditions import make_evaluator, parse_condition


@dataclass(frozen=True)
class Thresholds:
    observed: int = 1
    repeated: int = 2
    pattern: int = 3
    candidate: int = 5
    ask_user: int = 8
    strong_candidate: int = 13
    critical: int = 21


@dataclass
class FibonacciThresholds:
    series: list[int] = field(default_factory=lambda: [1, 1, 2, 3, 5, 8, 13, 21])


@dataclass
class CoolingPolicy:
    enabled: bool = True
    sessions: int = 3


@dataclass
class DetectionPolicy:
    min_cluster_size: int = 2
    max_candidates: int = 10


@dataclass
class FeedbackPolicy:
    record: bool = True


@dataclass
class ProtectedPatterns:
    patterns: list[str] = field(default_factory=list)


@dataclass
class ProtectedTargets:
    sigils: list[str] = field(
        default_factory=lambda: ["IDN", "AXM", "CNST:blocking", "CLAIM", "LIM"]
    )


@dataclass
class Gate:
    name: str
    condition: str = ""


@dataclass
class PolicyEntry:
    """One POL elevation rule or block."""

    source: str = ""
    target: str = ""
    tier: int = 1
    threshold: int = 1
    action: str = "propose"
    when: str | None = None
    name: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.when:
            # Parse eagerly so invalid conditions fail at load time.
            parse_condition(self.when)

    def matches(self, ctx: dict[str, Any] | None = None) -> bool:
        if not self.when:
            return True
        try:
            return make_evaluator(self.when)(ctx or {})
        except Exception:  # noqa: BLE001
            return False


@dataclass
class LearningPolicySet:
    entries: list[PolicyEntry] = field(default_factory=list)
    thresholds: Thresholds = field(default_factory=Thresholds)
    fibonacci_thresholds: FibonacciThresholds = field(default_factory=FibonacciThresholds)
    cooling: CoolingPolicy = field(default_factory=CoolingPolicy)
    detection: DetectionPolicy = field(default_factory=DetectionPolicy)
    feedback: FeedbackPolicy = field(default_factory=FeedbackPolicy)
    protected_patterns: ProtectedPatterns = field(default_factory=ProtectedPatterns)
    protected_targets: ProtectedTargets = field(default_factory=ProtectedTargets)

    def for_source(self, sigil: str) -> list[PolicyEntry]:
        return [p for p in self.entries if p.source == sigil]

    @classmethod
    def from_list(cls, rows: list[dict[str, Any]]) -> LearningPolicySet:
        parsed: list[PolicyEntry] = []
        for row in rows:
            try:
                tier = int(row.get("tier", 1))
                threshold = int(row.get("threshold", 1))
            except (TypeError, ValueError) as exc:
                raise LE011_PolicyParseError(
                    "POL entry tier/threshold must be integers", cause=str(exc)
                ) from exc
            parsed.append(
                PolicyEntry(
                    source=str(row.get("from", "")),
                    target=str(row.get("to", "")),
                    tier=tier,
                    threshold=threshold,
                    action=str(row.get("action", "propose")),
                    when=row.get("when"),
                    name=str(row.get("name", "")),
                    attrs=dict(row),
                )
            )
        return cls(parsed)


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "y", "on"}
    return default


def parse_policy_document(doc: dict[str, Any]) -> LearningPolicySet:
    """Parse a cortex_to_dict policy document into a LearningPolicySet.

    Policies are safety-critical and must never be silently accepted.
    """
    if not isinstance(doc, dict):
        raise LE011_PolicyParseError("policy document must be a dict", cause="invalid_root")

    rows: list[dict[str, Any]] = []
    ps = LearningPolicySet()

    for section in doc.get("sections", []):
        for entry in section.get("entries", []):
            sigil = str(entry.get("sigil", "")).upper()
            attrs = entry.get("attrs") if isinstance(entry.get("attrs"), dict) else {}
            name = str(entry.get("name", "")).lower()

            if sigil == "POL" and attrs:
                # Block-style config entries (POL:fibonacci_thresholds etc.)
                # configure the policy set but are not elevation rules.
                block_names = {
                    "fibonacci_thresholds", "fibonacci", "cooling",
                    "detection", "feedback", "protected_patterns",
                }
                if name not in block_names and "from" in attrs and "to" in attrs:
                    rows.append(attrs)
                # fall through to block-name handling as well
            if sigil == "THR":
                ps.thresholds = Thresholds(
                    observed=_to_int(attrs.get("observed", ps.thresholds.observed), ps.thresholds.observed),
                    repeated=_to_int(attrs.get("repeated", ps.thresholds.repeated), ps.thresholds.repeated),
                    pattern=_to_int(attrs.get("pattern", ps.thresholds.pattern), ps.thresholds.pattern),
                    candidate=_to_int(attrs.get("candidate", ps.thresholds.candidate), ps.thresholds.candidate),
                    ask_user=_to_int(attrs.get("ask_user", ps.thresholds.ask_user), ps.thresholds.ask_user),
                    strong_candidate=_to_int(attrs.get("strong_candidate", ps.thresholds.strong_candidate), ps.thresholds.strong_candidate),
                    critical=_to_int(attrs.get("critical", ps.thresholds.critical), ps.thresholds.critical),
                )
                continue
            if sigil == "PRT":
                raw = attrs.get("sigils") or attrs.get("targets") or attrs.get("protected")
                if isinstance(raw, str):
                    ps.protected_targets = ProtectedTargets([s.strip() for s in raw.split(",") if s.strip()])
                elif isinstance(raw, list):
                    ps.protected_targets = ProtectedTargets([str(s) for s in raw])
                continue

            # Block-style configuration entries (name-based)
            if name in {"fibonacci_thresholds", "fibonacci"}:
                series = attrs.get("series") or attrs.get("values")
                if isinstance(series, str):
                    ps.fibonacci_thresholds = FibonacciThresholds([int(x.strip()) for x in series.split(",") if x.strip()])
                elif isinstance(series, list):
                    ps.fibonacci_thresholds = FibonacciThresholds([int(x) for x in series])
                continue
            if name == "cooling":
                ps.cooling = CoolingPolicy(
                    enabled=_to_bool(attrs.get("enabled", ps.cooling.enabled)),
                    sessions=_to_int(attrs.get("sessions", ps.cooling.sessions), ps.cooling.sessions),
                )
                continue
            if name == "detection":
                ps.detection = DetectionPolicy(
                    min_cluster_size=_to_int(attrs.get("min_cluster_size", ps.detection.min_cluster_size), ps.detection.min_cluster_size),
                    max_candidates=_to_int(attrs.get("max_candidates", ps.detection.max_candidates), ps.detection.max_candidates),
                )
                continue
            if name == "feedback":
                ps.feedback = FeedbackPolicy(record=_to_bool(attrs.get("record", ps.feedback.record)))
                continue
            if name == "protected_patterns":
                raw = attrs.get("patterns") or attrs.get("sigils") or ""
                if isinstance(raw, str):
                    ps.protected_patterns = ProtectedPatterns([s.strip() for s in raw.split(",") if s.strip()])
                elif isinstance(raw, list):
                    ps.protected_patterns = ProtectedPatterns([str(s) for s in raw])

    ps.entries = LearningPolicySet.from_list(rows).entries
    return ps


def score_for_sigil(sigil: str) -> int:
    """Map a sigil to its learning 'tier weight'."""
    return {
        "KNW": 4,
        "LNG": 3,
        "SES": 2,
        "OBJ": 2,
        "FCS": 2,
        "WRK": 1,
    }.get(sigil, 0)


__all__ = [
    "CoolingPolicy",
    "DetectionPolicy",
    "FeedbackPolicy",
    "FibonacciThresholds",
    "Gate",
    "LearningPolicySet",
    "PolicyEntry",
    "ProtectedPatterns",
    "ProtectedTargets",
    "Thresholds",
    "parse_policy_document",
    "score_for_sigil",
]
