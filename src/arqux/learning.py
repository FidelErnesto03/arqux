"""Learning adapter — bridges Arqux governance state with CODEC-CORTEX Learning Engine (CLE).

The adapter translates between Arqux's ``.arqux/brain.cortex`` sections dict
and the CODEC-CORTEX ``CortexDocument`` / ``Entry`` objects that the learning
engine operates on.  The policy file ``learn-policies.cortex`` (stored in
``.arqux/``) controls scoring thresholds, elevation rules, and protected sigils.

Pipeline (contextual line)::

    read_brain() ─→ sections dict
        │
        ▼  _build_brain_doc()
    CortexDocument ─→ Entry objects
        │
        ▼  rebuild_index()
    LearnIndex ─→ ScoreRecord per entry
        │
        ▼  detect_candidates()
    Candidates ─→ SES→LNG, LNG→KNW proposals
        │
        ▼  plan_patch() → apply_patch()
    Elevated brain.cortex

BLP-038 extends this module with the BEHAVIORAL line:

    LessonStore.append(LNG) ─→ <agent>.lessons.cortex (Nivel 0)
        │
        ▼  elevate(behavioral)
    AXM/LIM in <agent>.cortex §1 IDENTITY (Nivel 1)

The three lines (Conductual, Procedimental, Contextual) share the same
``elevate()`` entry point but differ in source/target containers and sigils.
"""
from __future__ import annotations

import fcntl
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .constants import (
    ARQUX_DIR,
    BRAIN_CORTEX,
    BRAIN_SECTION_LESSONS,
    BRAIN_SECTION_PULSE,
    W003_LEARNING_DEBT_BEHAVIORAL,
)
from .migrator import migrate_lessons_file

logger = logging.getLogger(__name__)

_HAS_CLE: bool = False
try:
    from cortex.core.ast import CortexDocument, Entry
    from cortex.core.parser import parse_cortex
    from cortex.core.writer import write_cortex
    from cortex.learning.index import rebuild_index
    from cortex.learning.policy import parse_policy_document
    from cortex.learning.candidates import detect_candidates
    from cortex.learning.elevation import plan_patch, apply_patch, render_diff
    from cortex.learning.errors import LearningError

    _HAS_CLE = True
except ImportError:
    CortexDocument = None  # type: ignore
    Entry = None  # type: ignore


POLICY_FILENAME = "learn-policies.cortex"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_project_root(path: str | None) -> Path | None:
    """Find the project root (parent of .arqux/) from ``path`` or cwd."""
    from .state import find_project_root
    result = find_project_root(start=path)
    if result is None:
        return None
    # find_project_root returns .arqux/ path. Return its parent.
    return result.parent


def _load_policies(project_root: Path) -> Any | None:
    """Load learn-policies.cortex from ``.arqux/``.

    Returns a ``LearningPolicySet`` or ``None`` (policy invalid). If the
    project-local policy is missing, fall back to the packaged default so
    migrated projects can still run cortex.learn before policy seeding.
    """
    if not _HAS_CLE:
        return None
    policy_path = _resolve_policy_path(project_root)
    if not policy_path.exists():
        return None
    from cortex.core.parser import parse_cortex
    doc = parse_cortex(policy_path.read_text(encoding="utf-8"))
    if not doc:
        return None
    return parse_policy_document(doc)


def _resolve_policy_path(project_root: Path) -> Path:
    """Return project policy path or packaged default fallback."""
    project_policy = project_root / ARQUX_DIR / POLICY_FILENAME
    if project_policy.exists():
        return project_policy
    return Path(__file__).resolve().parent / "templates" / POLICY_FILENAME


def _build_brain_doc(project_root: Path) -> CortexDocument | None:
    """Build a CortexDocument from the project's brain.cortex sections.

    Uses the existing ``formats._build_brain_doc()`` to convert sections
    dict → CortexDocument so the learning engine can process it.
    """
    from .state import read_brain
    from .formats import _build_brain_doc as _build_doc
    from cortex.core.ast import CortexDocument as CDoc

    fm, sections, _ = read_brain(project_root)
    doc = CDoc()
    _build_doc(doc, fm, sections)
    return doc


def _hash_text(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _preview_hash(diff: str) -> str:
    """Stable approval token for an exact learning elevation preview."""
    return _hash_text(diff)


def _planned_entry(target: Any) -> tuple[str, str, dict[str, Any]]:
    """Return the entry that would be written for a learning candidate."""
    new_sigil = target.target
    new_name = getattr(target, "candidate_id", "elevated")
    new_value = {
        "topic": "elevated_knowledge",
        "content": str(getattr(target, "source_entries", [])),
        "status": "active",
    }
    return new_sigil, new_name, new_value


def _validate_elevation_payload(
    new_sigil: str,
    new_value: dict[str, Any],
    diff: str,
) -> list[str]:
    """Return blocking problems in a proposed learning elevation."""
    problems: list[str] = []
    serialized_values = [str(v).strip() for v in new_value.values()]
    if any(v in {"", "[]", "{}", "None"} for v in serialized_values):
        problems.append("proposed elevation contains empty fields")
    generic_markers = [
        "elevated_outcome",
        'input:""',
        'output:""',
        'date:""',
        'input=""',
        'output=""',
        'date=""',
    ]
    if any(marker in diff for marker in generic_markers):
        problems.append("proposed elevation contains generic or placeholder content")
    if new_sigil not in {"SES", "LNG", "KNW"}:
        problems.append(f"unexpected elevation target: {new_sigil}")
    return problems


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_brain(
    project_root: Path,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Scan the project brain through the learning engine.

    Returns a dict with:
        - entries: list of scored entries (id, sigil, hotness, promotion, risk, priority, action)
        - candidates: list of detected elevation candidates
        - count: total entries scanned
        - engine: available or unavailable
    """
    result: dict[str, Any] = {
        "engine": "unavailable",
        "count": 0,
        "entries": [],
        "candidates": [],
    }

    if not _HAS_CLE:
        return result
    result["engine"] = "available"

    try:
        # 1. Load brain and policies
        brain_doc = _build_brain_doc(project_root)
        if not brain_doc:
            return {**result, "error": "could_not_build_document"}

        policy_set = _load_policies(project_root)
        if not policy_set:
            return {**result, "error": "policies_not_found"}

        # 2. Brain hash (simple fingerprint)
        brain_path = project_root / ARQUX_DIR / BRAIN_CORTEX
        brain_hash = _hash_text(brain_path.read_text(encoding="utf-8"))
        policy_path = _resolve_policy_path(project_root)
        policy_hash = _hash_text(policy_path.read_text(encoding="utf-8"))

        # 3. Rebuild index — this runs all scoring
        index = rebuild_index(
            brain_doc,
            policy_set,
            brain_hash,
            policy_hash,
        )

        # 4. Build entry list
        entries = []
        for eid, record in sorted(index.entries.items(), key=lambda x: x[1].read_priority):
            entries.append({
                "id": eid,
                "fingerprint": record.fingerprint,
                "hotness": record.hotness_score,
                "promotion": record.promotion_score,
                "risk": record.risk_weight,
                "priority": record.read_priority,
                "action": record.suggested_action,
                "signals": record.signals,
            })
        result["count"] = len(entries)
        result["entries"] = entries

        # 5. Detect candidates
        if verbose:
            candidates = detect_candidates(brain_doc, index, policy_set)
            result["candidates"] = [
                {
                    "id": c.candidate_id,
                    "source": c.source_entries,
                    "target": c.target,
                    "promotion_score": c.promotion_score,
                    "hotness_score": c.hotness_score,
                }
                for c in candidates
            ]

    except Exception as exc:
        return {**result, "error": str(exc)}

    return result


def list_candidates(
    project_root: Path,
) -> list[dict[str, Any]]:
    """List elevation candidates for the project."""
    if not _HAS_CLE:
        return []

    try:
        brain_doc = _build_brain_doc(project_root)
        if not brain_doc:
            return []

        policy_set = _load_policies(project_root)
        if not policy_set:
            return []

        brain_path = project_root / ARQUX_DIR / BRAIN_CORTEX
        brain_hash = _hash_text(brain_path.read_text(encoding="utf-8"))
        policy_path = _resolve_policy_path(project_root)
        policy_hash = _hash_text(policy_path.read_text(encoding="utf-8"))

        index = rebuild_index(brain_doc, policy_set, brain_hash, policy_hash)
        candidates = detect_candidates(brain_doc, index, policy_set)

        return [
            {
                "id": c.candidate_id,
                "source": c.source_entries,
                "target": c.target,
                "promotion_score": c.promotion_score,
                "hotness_score": c.hotness_score,
            }
            for c in candidates
        ]
    except Exception:
        return []


def elevate_candidate(
    project_root: Path,
    candidate_id: str,
    *,
    dry_run: bool = True,
    confirm_hash: str | None = None,
) -> dict[str, Any]:
    """Elevate a candidate (SES→LNG or LNG→KNW).

    When ``dry_run=True`` (default), returns the diff without applying.
    When ``dry_run=False``, applies the elevation to brain.cortex.
    """
    if not _HAS_CLE:
        return {"error": "learning engine unavailable"}

    try:
        brain_doc = _build_brain_doc(project_root)
        if not brain_doc:
            return {"error": "could_not_build_document"}

        policy_set = _load_policies(project_root)
        if not policy_set:
            return {"error": "policies_not_found"}

        # Rebuild index and find the candidate
        brain_path = project_root / ARQUX_DIR / BRAIN_CORTEX
        brain_hash = _hash_text(brain_path.read_text(encoding="utf-8"))
        policy_path = _resolve_policy_path(project_root)
        policy_hash = _hash_text(policy_path.read_text(encoding="utf-8"))

        index = rebuild_index(brain_doc, policy_set, brain_hash, policy_hash)
        candidates = detect_candidates(brain_doc, index, policy_set)

        target = None
        for c in candidates:
            if c.candidate_id == candidate_id:
                target = c
                break
        if target is None:
            return {"error": f"candidate {candidate_id!r} not found"}

        # Plan the patch
        patch = plan_patch(brain_doc, policy_set, target)
        if patch.mode == "block":
            return {"error": f"elevation blocked by policy: {patch.block_reason}"}

        diff = render_diff(brain_doc, patch)
        preview_hash = _preview_hash(diff)

        new_sigil = patch.new_entry_sigil or target.target
        new_name = patch.new_entry_name
        new_value = patch.new_entry_value
        if not new_name or not new_value:
            fallback_sigil, fallback_name, fallback_value = _planned_entry(target)
            new_sigil = new_sigil or fallback_sigil
            new_name = new_name or fallback_name
            new_value = new_value or fallback_value

        validation_errors = _validate_elevation_payload(new_sigil, new_value, diff)

        if dry_run:
            return {
                "mode": "dry_run",
                "diff": diff,
                "candidate": candidate_id,
                "preview_hash": preview_hash,
                "validation_errors": validation_errors,
            }

        if confirm_hash != preview_hash:
            return {
                "error": (
                    "preview approval required before applying elevation. "
                    "Run dry-run, review the exact diff, then pass confirm_hash."
                ),
                "preview_hash": preview_hash,
                "diff": diff,
            }

        if validation_errors:
            return {
                "error": "unsafe elevation blocked: " + "; ".join(validation_errors),
                "preview_hash": preview_hash,
                "diff": diff,
            }

        # Apply manually: add the elevated entry to KNOWLEDGE section.
        from .state import read_brain, write_brain_sections
        from .formats import _build_brain_doc as _build_doc

        # Read current brain, add to KNOWLEDGE section
        fm, sections, _ = read_brain(project_root)
        knw_line = f"{new_sigil}:{new_name} " + " ".join(f'{k}="{v}"' for k, v in new_value.items())
        existing = sections.get("KNOWLEDGE", "").strip()
        if existing:
            sections["KNOWLEDGE"] = existing + "\n" + knw_line
        else:
            sections["KNOWLEDGE"] = knw_line
        write_brain_sections(project_root, fm, sections)

        return {"mode": "applied", "diff": diff, "candidate": candidate_id, "preview_hash": preview_hash}

    except Exception as exc:
        return {"error": str(exc)}


def build_profile(
    project_root: Path,
) -> dict[str, Any]:
    """Produce a load priority profile (P0-P5) for the project brain."""
    scan = scan_brain(project_root)
    if "entries" not in scan:
        return {"error": "scan_failed", "engine": scan.get("engine", "unavailable")}

    profile: dict[str, int] = {}
    for entry in scan["entries"]:
        p = entry.get("priority", "P3")
        profile[p] = profile.get(p, 0) + 1

    return {
        "engine": scan.get("engine", "unavailable"),
        "total": scan.get("count", 0),
        "profile": dict(sorted(profile.items())),
    }


# ===========================================================================
# BLP-038: Three Lines of Learning — Behavioral + Procedural channels
# ===========================================================================
#
# The existing scan_brain/elevate_candidate functions above are the CONTEXTUAL
# line (brain.cortex $6 → $10). BLP-038 adds two parallel lines that share
# the same conceptual motor but operate on different containers:
#
#   BEHAVIORAL  → <agent>.lessons.cortex (Nivel 0) → <agent>.cortex §1 IDENTITY
#                 sigils: LNG → AXM | LIM
#                 governance: Alfred (Governor) approves every elevation
#
#   PROCEDURAL  → <name>.skill.md (Nivel 2) → <name>.skill.md (same file)
#                 sigils: STP → CNST | CLAIM
#                 governance: Alfred (Governor) approves every elevation
#
# All three lines are accessible via the unified ``elevate()`` function.


# --- Exceptions (BLP-038 §10) ----------------------------------------------

class LessonNotFoundError(Exception):
    """Raised when a lesson_id cannot be found in the LessonStore."""

class InsufficientConfidenceError(Exception):
    """Raised when a lesson's confidence/occurrences are below thresholds.

    Per BLP-038 §11: elevation requires ``occurrences >= 2`` AND
    ``confidence >= 0.7``.
    """

class InvalidLessonStatusError(Exception):
    """Raised when a lesson is already ``elevated`` or ``expired``."""

class ContainerIdentityError(Exception):
    """Raised when the source/target container cannot be resolved."""

class AgentIdentityError(Exception):
    """Raised when an unknown agent name is provided."""


# --- Lesson sigil parser ----------------------------------------------------

_LNG_RE = re.compile(
    r"LNG:(?P<name>[^\s{]+)\s*\{(?P<attrs>[^}]*)\}",
    re.DOTALL,
)


def _parse_lng_attrs(attrs_text: str) -> dict[str, str]:
    """Parse a sigil attrs body into a dict (key → original-case value)."""
    result: dict[str, str] = {}
    for m in re.finditer(
        r'(\w+)\s*:\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^,}\s]+)',
        attrs_text,
    ):
        key = m.group(1)
        val = m.group(2)
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        result[key] = val
    return result


def _now_epoch() -> int:
    return int(time.time())


# --- Lesson data ------------------------------------------------------------

@dataclass
class Lesson:
    """A single behavioral lesson entry (sigilo LNG)."""
    lesson_id: str
    agent: str
    context: str
    pattern: str
    evidence_ref: str = ""
    confidence: float = 0.0
    occurrences: int = 1
    ttl: int = 30          # cycles
    status: str = "raw"    # raw | elevated | discarded | expired
    captured_at: int = 0
    line: str = "behavioral"  # which line this lesson belongs to

    def to_sigil(self) -> str:
        """Render this lesson as an ``LNG:<id>{...}`` line."""
        return (
            f"LNG:{self.lesson_id}{{"
            f'type:"{self.line}", '
            f"confidence:{self.confidence}, "
            f"occurrences:{self.occurrences}, "
            f"ttl:{self.ttl}, "
            f'status:"{self.status}"'
            "}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "lesson_id": self.lesson_id,
            "agent": self.agent,
            "context": self.context,
            "pattern": self.pattern,
            "evidence_ref": self.evidence_ref,
            "confidence": self.confidence,
            "occurrences": self.occurrences,
            "ttl": self.ttl,
            "status": self.status,
            "captured_at": self.captured_at,
            "line": self.line,
        }


# --- LessonStore (Nivel 0 behavioral container) ----------------------------

#: Default thresholds per BLP-038 §11 (Decision de Elevación).
DEFAULT_MIN_OCCURRENCES: int = 2
DEFAULT_MIN_CONFIDENCE: float = 0.70
#: Default TTL in cycles before W003_LEARNING_DEBT_BEHAVIORAL is emitted.
DEFAULT_TTL_CYCLES: int = 30


class LessonStore:
    """Append-only repository of LNG lessons for one agent (BLP-038).

    Each store lives at ``.arqux/identities/<agent>.lessons.cortex`` (Nivel 0
    PACKAGE) and is owned by exactly one agent. The store is APPEND-ONLY:
    agents can capture new lessons but cannot modify or delete existing ones
    (Rule 3 — Acumulación Append-Only). Only the Governor can mark lessons
    as ``elevated`` or ``discarded`` via ``elevate()``.

    The store uses a file-lock (``fcntl``) to guarantee integrity under
    concurrent capture from multiple agent instances (R-03 mitigation).

    Hook contracts (BLP-038 §8):
        - ``on_capture(lesson)`` — invoked after a lesson is appended.
        - ``on_elevate(lesson)`` — invoked after a lesson is marked elevated.
        - ``on_expire(lesson)`` — invoked when TTL is exceeded.
    """

    def __init__(
        self,
        path: Path | str,
        *,
        agent: str,
        min_occurrences: int = DEFAULT_MIN_OCCURRENCES,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        self.path = Path(path)
        self.agent = agent
        self.min_occurrences = min_occurrences
        self.min_confidence = min_confidence
        self._hooks: dict[str, list[Callable[[Lesson], None]]] = {
            "on_capture": [],
            "on_elevate": [],
            "on_expire": [],
        }

    # --- Hook registration ---

    def add_hook(self, event: str, callback: Callable[[Lesson], None]) -> None:
        if event not in self._hooks:
            raise ValueError(f"Unknown hook event: {event!r}")
        self._hooks[event].append(callback)

    def _fire(self, event: str, lesson: Lesson) -> None:
        for cb in self._hooks.get(event, []):
            try:
                cb(lesson)
            except Exception as exc:  # noqa: BLE001
                logger.warning("hook %s failed: %s", event, exc)

    # --- Container initialization ---

    def ensure_container(self) -> None:
        """Create the file with §0 METADATA if it does not exist."""
        if self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write an empty container with §0 METADATA + minimal $0 glossary.
        body = (
            f"$0\n"
            f"GSIG:LNG:lesson|attrs|M|Episodic|Learned lesson or pattern\n\n"
            f"$1: LESSONS\n"
        )
        self.path.write_text(body, encoding="utf-8")
        # Migrate (inject §0 METADATA). Idempotent.
        migrate_lessons_file(self.path, agent=self.agent)

    # --- Capture (BLP-038 §9 Captura) ---

    def append_lesson(
        self,
        *,
        context: str,
        pattern: str,
        evidence_ref: str = "",
        confidence: float = 0.0,
        occurrences: int = 1,
        ttl: int = DEFAULT_TTL_CYCLES,
        lesson_id: str | None = None,
    ) -> Lesson:
        """Append a new LNG lesson to the store (Rule 3 — Append-Only).

        Returns the captured Lesson. Fires ``on_capture`` hook.
        """
        self.ensure_container()
        if lesson_id is None:
            lesson_id = self._next_lesson_id()

        lesson = Lesson(
            lesson_id=lesson_id,
            agent=self.agent,
            context=context,
            pattern=pattern,
            evidence_ref=evidence_ref,
            confidence=float(confidence),
            occurrences=int(occurrences),
            ttl=int(ttl),
            status="raw",
            captured_at=_now_epoch(),
            line="behavioral",
        )

        # File-lock for concurrent safety (R-03).
        with self.path.open("a+", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                # Re-append glossary marker if file is empty.
                content = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
                if not content.strip():
                    fh.write("$1: LESSONS\n")
                # Write the LNG line + body.
                fh.write("\n")
                fh.write(lesson.to_sigil() + "\n")
                fh.write(f'- context: "{context}"\n')
                fh.write(f'- pattern: "{pattern}"\n')
                if evidence_ref:
                    fh.write(f'- evidence_ref: "{evidence_ref}"\n')
                fh.flush()
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

        self._fire("on_capture", lesson)
        return lesson

    # --- Read ---

    def list_lessons(self, *, include_expired: bool = False) -> list[Lesson]:
        """Return all lessons in the store, optionally including expired ones."""
        if not self.path.exists():
            return []
        text = self.path.read_text(encoding="utf-8")
        lessons: list[Lesson] = []
        for m in _LNG_RE.finditer(text):
            attrs = _parse_lng_attrs(m.group("attrs"))
            name = m.group("name")
            # Look for the bullet lines following this sigil.
            tail_start = m.end()
            tail_end = tail_start + 500  # cap search window
            tail = text[tail_start:tail_end]
            context = ""
            pattern = ""
            evidence_ref = ""
            cm = re.search(r'- context:\s*"([^"]*)"', tail)
            if cm:
                context = cm.group(1)
            pm = re.search(r'- pattern:\s*"([^"]*)"', tail)
            if pm:
                pattern = pm.group(1)
            em = re.search(r'- evidence_ref:\s*"([^"]*)"', tail)
            if em:
                evidence_ref = em.group(1)
            try:
                confidence = float(attrs.get("confidence", "0"))
            except ValueError:
                confidence = 0.0
            try:
                occurrences = int(attrs.get("occurrences", "1"))
            except ValueError:
                occurrences = 1
            try:
                ttl_val = int(attrs.get("ttl", str(DEFAULT_TTL_CYCLES)))
            except ValueError:
                ttl_val = DEFAULT_TTL_CYCLES
            lesson = Lesson(
                lesson_id=name,
                agent=self.agent,
                context=context,
                pattern=pattern,
                evidence_ref=evidence_ref,
                confidence=confidence,
                occurrences=occurrences,
                ttl=ttl_val,
                status=attrs.get("status", "raw"),
                captured_at=0,
                line=attrs.get("type", "behavioral"),
            )
            if not include_expired and lesson.status == "expired":
                continue
            lessons.append(lesson)
        return lessons

    def get_lesson(self, lesson_id: str) -> Lesson:
        """Return the lesson with ``lesson_id`` or raise LessonNotFoundError."""
        for lesson in self.list_lessons(include_expired=True):
            if lesson.lesson_id == lesson_id:
                return lesson
        raise LessonNotFoundError(f"Lesson {lesson_id!r} not found in {self.path}")

    # --- Elevation eligibility (BLP-038 §11) ---

    def can_elevate(self, lesson: Lesson) -> tuple[bool, str]:
        """Check if a lesson meets the elevation thresholds.

        Returns (can_elevate, reason). ``reason`` is "" when can_elevate.
        """
        if lesson.status == "elevated":
            return False, "lesson is already elevated"
        if lesson.status == "discarded":
            return False, "lesson is discarded"
        if lesson.status == "expired":
            return False, "lesson is expired"
        if lesson.occurrences < self.min_occurrences:
            return False, (
                f"occurrences {lesson.occurrences} < {self.min_occurrences} threshold"
            )
        if lesson.confidence < self.min_confidence:
            return False, (
                f"confidence {lesson.confidence} < {self.min_confidence} threshold"
            )
        return True, ""

    def mark_elevated(self, lesson_id: str) -> Lesson:
        """Mark a lesson as ``elevated`` (only Governor should call this)."""
        lesson = self.get_lesson(lesson_id)
        if lesson.status == "elevated":
            raise InvalidLessonStatusError(f"{lesson_id} already elevated")
        can, reason = self.can_elevate(lesson)
        if not can:
            raise InsufficientConfidenceError(reason)
        # Rewrite the sigil line in-place.
        self._rewrite_lesson_status(lesson_id, "elevated")
        lesson.status = "elevated"
        self._fire("on_elevate", lesson)
        return lesson

    def mark_discarded(self, lesson_id: str) -> Lesson:
        """Mark a lesson as ``discarded`` (Governor rejects elevation)."""
        lesson = self.get_lesson(lesson_id)
        self._rewrite_lesson_status(lesson_id, "discarded")
        lesson.status = "discarded"
        return lesson

    def _rewrite_lesson_status(self, lesson_id: str, new_status: str) -> None:
        """Rewrite the status attribute of an LNG sigil in-place."""
        if not self.path.exists():
            return
        text = self.path.read_text(encoding="utf-8")

        def _replace(m: re.Match) -> str:
            name = m.group("name")
            if name != lesson_id:
                return m.group(0)
            attrs = m.group("attrs")
            # Replace status:"..." with the new status.
            new_attrs = re.sub(
                r'status:\s*"[^"]*"',
                f'status:"{new_status}"',
                attrs,
            )
            return f"LNG:{name}{{{new_attrs}}}"

        new_text = _LNG_RE.sub(_replace, text)
        self.path.write_text(new_text, encoding="utf-8")

    # --- TTL / Debt check (Rule 5 — Caducidad) ---

    def check_expired(self, *, current_cycle: int = 0) -> list[Lesson]:
        """Detect ``raw`` lessons whose TTL has expired; emit W003 warnings.

        ``current_cycle`` is the current cycle index (used to compute age in
        cycles). The TTL field on each lesson is the number of cycles it
        may remain ``raw`` before becoming debt.
        """
        expired: list[Lesson] = []
        for lesson in self.list_lessons(include_expired=True):
            if lesson.status != "raw":
                continue
            if current_cycle >= lesson.ttl:
                # Mark expired.
                self._rewrite_lesson_status(lesson.lesson_id, "expired")
                lesson.status = "expired"
                expired.append(lesson)
                logger.warning(
                    "%s: lesson %s of agent %s expired (ttl=%d, cycle=%d)",
                    W003_LEARNING_DEBT_BEHAVIORAL,
                    lesson.lesson_id, self.agent, lesson.ttl, current_cycle,
                )
                self._fire("on_expire", lesson)
        return expired

    # --- Migration (BLP-038 T-038.5) ---

    def import_from_brain(
        self,
        brain_path: Path | str,
        *,
        agent_map: dict[str, str] | None = None,
    ) -> list[Lesson]:
        """Migrate behavioral LNG lessons from a project brain to this store.

        Reads the ``$6 LESSONS`` section of ``brain_path``, extracts any LNG
        entries that look behavioral (or unclassified — defaults to the
        store's agent), and appends them here. The brain is left untouched
        (the caller is responsible for cleaning the brain afterwards).

        Returns the list of migrated lessons.
        """
        brain_p = Path(brain_path)
        if not brain_p.exists():
            raise FileNotFoundError(f"Brain not found: {brain_p}")
        text = brain_p.read_text(encoding="utf-8")

        # Extract the $6 LESSONS section.
        section_match = re.search(
            r"\$6\s*:?\s*LESSONS?\s*\n(.*?)(?=\$\d+\s*:?\s*[A-Z_]|\Z)",
            text, re.DOTALL,
        )
        if not section_match:
            return []
        section_body = section_match.group(1)

        migrated: list[Lesson] = []
        for m in _LNG_RE.finditer(section_body):
            attrs = _parse_lng_attrs(m.group("attrs"))
            name = m.group("name")
            tail = section_body[m.end():m.end() + 500]
            cm = re.search(r'- context:\s*"([^"]*)"', tail)
            pm = re.search(r'- pattern:\s*"([^"]*)"', tail)
            try:
                confidence = float(attrs.get("confidence", "0"))
            except ValueError:
                confidence = 0.0
            try:
                occurrences = int(attrs.get("occurrences", "1"))
            except ValueError:
                occurrences = 1
            try:
                ttl_val = int(attrs.get("ttl", str(DEFAULT_TTL_CYCLES)))
            except ValueError:
                ttl_val = DEFAULT_TTL_CYCLES
            lesson = Lesson(
                lesson_id=name,
                agent=self.agent,
                context=cm.group(1) if cm else "",
                pattern=pm.group(1) if pm else "",
                confidence=confidence,
                occurrences=occurrences,
                ttl=ttl_val,
                status="raw",
                captured_at=_now_epoch(),
                line="behavioral",
            )
            # Append (without re-firing on_capture, since this is migration).
            self.ensure_container()
            with self.path.open("a", encoding="utf-8") as fh:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                try:
                    fh.write("\n")
                    fh.write(lesson.to_sigil() + "\n")
                    fh.write(f'- context: "{lesson.context}"\n')
                    fh.write(f'- pattern: "{lesson.pattern}"\n')
                    fh.flush()
                finally:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            migrated.append(lesson)
        return migrated

    # --- Internals ---

    def _next_lesson_id(self) -> str:
        """Generate the next sequential lesson id: ``lsn-001``, ``lsn-002``..."""
        existing = self.list_lessons(include_expired=True)
        max_n = 0
        for lesson in existing:
            m = re.match(r"lsn-(\d+)", lesson.lesson_id)
            if m:
                max_n = max(max_n, int(m.group(1)))
        return f"lsn-{max_n + 1:03d}"


# --- Unified elevation API (BLP-038 §8/§10) --------------------------------

#: Allowed contract types per line.
_CONTRACT_TYPES_BEHAVIORAL = {"AXIOM", "LIMIT"}
_CONTRACT_TYPES_PROCEDURAL = {"CNST", "CLAIM"}
_CONTRACT_TYPES_CONTEXTUAL = {"KNW"}


@dataclass
class BlueprintDraft:
    """A proposed elevation that has passed thresholds but not yet applied.

    The Governor reviews the draft and decides whether to ``apply()`` it.
    """
    line: str            # behavioral | procedural | contextual
    source: str          # source container path
    target: str          # target container path/section
    contract_type: str   # AXIOM | LIMIT | CNST | CLAIM | KNW
    lesson_id: str
    sigil_to_write: str  # AXM | LIM | CNST | CLAIM | KNW
    content: dict[str, Any]
    evidence_refs: list[str] = field(default_factory=list)


def _resolve_behavioral_paths(
    agent: str, *, project_root: Path | None = None,
) -> tuple[Path, Path]:
    """Resolve (source=lessons.cortex, target=<agent>.cortex) paths.

    Both files live under ``.arqux/identities/``.
    """
    if not agent:
        raise AgentIdentityError("agent name must be non-empty")
    identities_dir = Path(project_root or Path.cwd()) / ARQUX_DIR / "identities"
    if not identities_dir.exists():
        # Fall back to packaged identities (read-only).
        from .constants import IDENTITIES_DIR
        identities_dir = IDENTITIES_DIR
    source = identities_dir / f"{agent}.lessons.cortex"
    target = identities_dir / f"{agent}.cortex"
    if not target.exists():
        raise AgentIdentityError(
            f"Target identity file does not exist: {target}. "
            f"Known agents: alfred, jarvis, seshat, heimdall, executor, "
            f"governor, auditor."
        )
    return source, target


def elevate(
    *,
    source: str,
    target: str,
    contract_type: str,
    lesson_id: str,
    line: str = "behavioral",
    agent: str | None = None,
    project_root: Path | None = None,
    dry_run: bool = True,
    apply: bool = False,  # noqa: A002 — apply is the BLP-038 verb
) -> dict[str, Any]:
    """Unified elevation motor for the three lines (BLP-038 §8/§11).

    Parameters
    ----------
    source : str
        Path to the LessonStore source container.
    target : str
        Path to the destination container (and optionally a section).
    contract_type : str
        AXIOM | LIMIT (behavioral) | CNST | CLAIM (procedural) | KNW (contextual).
    lesson_id : str
        The sigil name to elevate (e.g. ``lsn-042``).
    line : str
        ``behavioral`` | ``procedural`` | ``contextual``. Selects thresholds.
    agent : str, optional
        Required for behavioral — the agent that owns the lessons store.
    project_root : Path, optional
        Used to resolve identities directory when source/target are bare names.
    dry_run : bool
        When True (default), returns the draft without applying.
    apply : bool
        When True, applies the elevation (requires Governor approval at the
        CLI/handler layer).

    Returns
    -------
    dict
        ``{mode, line, draft, applied?}`` — see BLP-038 §10 contracts.
    """
    line_norm = line.lower().strip()
    if line_norm not in {"behavioral", "procedural", "contextual"}:
        raise ValueError(f"Unknown line: {line!r}")

    contract_norm = contract_type.upper().strip()

    # Validate contract_type per line.
    if line_norm == "behavioral" and contract_norm not in _CONTRACT_TYPES_BEHAVIORAL:
        raise ValueError(
            f"Behavioral line only accepts contracts "
            f"{_CONTRACT_TYPES_BEHAVIORAL}; got {contract_norm!r}"
        )
    if line_norm == "procedural" and contract_norm not in _CONTRACT_TYPES_PROCEDURAL:
        raise ValueError(
            f"Procedural line only accepts contracts "
            f"{_CONTRACT_TYPES_PROCEDURAL}; got {contract_norm!r}"
        )
    if line_norm == "contextual" and contract_norm not in _CONTRACT_TYPES_CONTEXTUAL:
        raise ValueError(
            f"Contextual line only accepts contracts "
            f"{_CONTRACT_TYPES_CONTEXTUAL}; got {contract_norm!r}"
        )

    # --- Behavioral line ---
    if line_norm == "behavioral":
        if not agent:
            raise AgentIdentityError(
                "agent is required for the behavioral line"
            )
        src_path = Path(source)
        if not src_path.exists():
            # Try resolving via agent name.
            src_path, _ = _resolve_behavioral_paths(agent, project_root=project_root)
        store = LessonStore(src_path, agent=agent)
        lesson = store.get_lesson(lesson_id)
        can, reason = store.can_elevate(lesson)
        if not can:
            raise InsufficientConfidenceError(
                f"Cannot elevate {lesson_id}: {reason}"
            )
        sigil_to_write = "AXM" if contract_norm == "AXIOM" else "LIM"
        draft = BlueprintDraft(
            line="behavioral",
            source=str(src_path),
            target=target,
            contract_type=contract_norm,
            lesson_id=lesson_id,
            sigil_to_write=sigil_to_write,
            content={
                "name": lesson_id,
                "body": lesson.pattern,
                "status": "current",
                "source_lesson": lesson_id,
            },
            evidence_refs=[lesson.evidence_ref] if lesson.evidence_ref else [],
        )
        if dry_run and not apply:
            return {"mode": "dry_run", "line": "behavioral", "draft": draft.to_dict() if hasattr(draft, "to_dict") else _draft_to_dict(draft)}
        # Apply: Governor has confirmed. Mark lesson as elevated.
        store.mark_elevated(lesson_id)
        # Note: the actual write to <agent>.cortex §1 IDENTITY is performed
        # by IdentityManager.elevate_to_identity() (BLP-039).
        return {
            "mode": "applied",
            "line": "behavioral",
            "draft": _draft_to_dict(draft),
            "lesson_status": "elevated",
            "next_step": (
                f"call IdentityManager.elevate_to_identity(agent={agent!r}, "
                f"lesson_id={lesson_id!r}, contract_type={contract_norm!r}) "
                f"to write the {sigil_to_write} sigil into {target}"
            ),
        }

    # --- Procedural line ---
    if line_norm == "procedural":
        src_path = Path(source)
        if not src_path.exists():
            raise ContainerIdentityError(f"Source skill not found: {src_path}")
        # For procedural, source == target (in-file elevation STP→CNST/CLAIM).
        # The actual mutation is delegated to the skill handlers (BLP-040).
        sigil_to_write = contract_norm  # CNST or CLAIM
        draft = BlueprintDraft(
            line="procedural",
            source=str(src_path),
            target=target or str(src_path),
            contract_type=contract_norm,
            lesson_id=lesson_id,
            sigil_to_write=sigil_to_write,
            content={
                "name": lesson_id,
                "body": "(procedural elevation — see skill file)",
                "status": "current",
            },
        )
        if dry_run and not apply:
            return {"mode": "dry_run", "line": "procedural", "draft": _draft_to_dict(draft)}
        return {
            "mode": "applied",
            "line": "procedural",
            "draft": _draft_to_dict(draft),
            "note": "procedural elevation mutates the skill file in-place",
        }

    # --- Contextual line ---
    # Delegate to the existing elevate_candidate (preserved untouched).
    if project_root is None:
        resolved = _resolve_project_root(None)
        if resolved is None:
            raise ContainerIdentityError(
                "Could not resolve project_root for contextual elevation"
            )
        project_root = resolved
    # The existing contextual elevator is candidate-based; we expose a thin
    # adapter that maps lesson_id → candidate_id.
    result = elevate_candidate(
        project_root,
        lesson_id,
        dry_run=dry_run and not apply,
    )
    return {
        "mode": result.get("mode", "dry_run"),
        "line": "contextual",
        "result": result,
    }


def _draft_to_dict(draft: BlueprintDraft) -> dict[str, Any]:
    return {
        "line": draft.line,
        "source": draft.source,
        "target": draft.target,
        "contract_type": draft.contract_type,
        "lesson_id": draft.lesson_id,
        "sigil_to_write": draft.sigil_to_write,
        "content": draft.content,
        "evidence_refs": draft.evidence_refs,
    }
