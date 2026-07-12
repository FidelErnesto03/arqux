"""Lesson store and behavioral learning infrastructure (BLP-038)."""
from __future__ import annotations

import fcntl
import re
from pathlib import Path
from typing import Any, Callable

from ...constants import ARQUX_DIR, W003_LEARNING_DEBT_BEHAVIORAL
from ._common import _HAS_CLE, logger
from ._models import (
    Lesson,
    LessonNotFoundError,
    InsufficientConfidenceError,
    InvalidLessonStatusError,
    ContainerIdentityError,
    AgentIdentityError,
    _LNG_RE,
    _parse_lng_attrs,
    _now_epoch,
)

# --- LessonStore (Nivel 0 behavioral container) ------------------------------

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
        """Create the file with ARQX:artifact metadata if it does not exist.

        Uses CortexDocument + write_cortex() from CODEC-CORTEX (BLP-042).
        No write_text() bypass.
        """
        if self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not _HAS_CLE:
            # Degradación controlada si CODEC-CORTEX no está disponible.
            body = (
                f"$0\n"
                f"GSIG:LNG:lesson|attrs|M|Episodic|Learned lesson or pattern\n\n"
                f"$1: LESSONS\n"
            )
            self.path.write_text(body, encoding="utf-8")
            return

        from cortex.core.ast import CortexDocument, Section, Entry, SigilDef

        doc = CortexDocument()
        # $0 glossary
        sec0 = Section(id="$0", title="")
        doc.sections.append(sec0)
        doc.glossary.add_sigil(SigilDef(
            sigil="LNG", name="lesson", type="attrs",
            risk="M", layer="Episodic",
            description="Learned lesson or pattern",
        ))
        # $19: ARQUX METADATA
        sec01 = Section(id="$19", title="ARQUX METADATA")
        sec01.entries.append(Entry(
            "$19", sigil="ARQX", name="artifact", type="attrs",
            value={"level": 0, "name": f"{self.agent}-lessons",
                   "usage": "lesson", "kind": "native", "agent": self.agent},
        ))
        doc.sections.append(sec01)
        # $1: LESSONS
        sec1 = Section(id="$1", title="LESSONS")
        doc.sections.append(sec1)

        from ._common import write_cortex

        cortex_text = write_cortex(doc)
        self.path.write_text(cortex_text, encoding="utf-8")

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
