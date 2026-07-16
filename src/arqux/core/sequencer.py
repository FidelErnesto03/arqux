"""Universal Sequencer — template-agnostic segment scanner.

Reads any body with ``<!-- TYPE:N -->`` markers and reports the next
pending segment. Does NOT write, validate, or modify the body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class Segment:
    """A single segment delimited by ``<!-- TYPE:N -->`` markers."""

    id: str  # numeric segment ID (e.g. "1", "2")
    header: str  # the ``## §N: Title`` line, or empty
    body: str  # raw content between open and close markers
    pending_markers: list[str] = field(default_factory=list)
    has_content: bool = False
    template: str = ""  # raw body with ``_..._`` markers preserved

    def __post_init__(self) -> None:
        if not self.template:
            self.template = self.body


@dataclass
class SequenceResult:
    """Result of a full ``Sequencer.scan()`` call."""

    total: int = 0
    completed: int = 0
    pending: list[Segment] = field(default_factory=list)

    @property
    def next_pending(self) -> Segment | None:
        """The first pending segment (lowest ID with unfilled markers)."""
        return self.pending[0] if self.pending else None


class Sequencer:
    """Template-agnostic sequencer.

    Scans any body with ``<!-- TYPE:N -->`` markers and ``## §N:`` headers.
    The *type* parameter sets the marker prefix (e.g. ``"BLP"``, ``"CYCLE"``).

    Typical usage::

        seq = Sequencer("BLP")
        result = seq.scan(body)
        if result.next_pending:
            print(f"Next: §{result.next_pending.id}")
    """

    _MARKER_IN_BODY: ClassVar[re.Pattern] = re.compile(r"_([A-Z][^_]{3,}?)_")
    _HEADER_RE: ClassVar[re.Pattern] = re.compile(r"## §\d+: .*")

    def __init__(self, type: str = "BLP") -> None:  # noqa: A002
        self.type = type
        self._open_re = re.compile(
            rf"<!--\s*{re.escape(type)}:(.+?)\s*-->",
        )
        self._close_re = re.compile(
            rf"<!--\s*/{re.escape(type)}:(.+?)\s*-->",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self, body: str) -> SequenceResult:
        """Scan *body* and return the state of all segments."""
        segments = self._extract_segments(body)
        pending: list[Segment] = []
        for seg in segments:
            markers = self._MARKER_IN_BODY.findall(seg.body)
            filtered = [m for m in markers if m not in ("texto", "marcador")]
            seg.pending_markers = filtered
            body_lines = seg.body.strip().split("\n")
            has_content_beyond_header = any(
                line.strip() and not self._HEADER_RE.match(line.strip())
                for line in body_lines
            )
            seg.has_content = has_content_beyond_header
            if filtered or not has_content_beyond_header:
                pending.append(seg)

        return SequenceResult(
            total=len(segments),
            completed=len(segments) - len(pending),
            pending=pending,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _extract_segments(self, body: str) -> list[Segment]:
        """Extract all ``<!-- TYPE:N -->`` segments from *body*.

        Segments are returned in document order (the order they appear
        in the body, which typically matches §1, §2, …).
        """
        segments: list[Segment] = []
        pos = 0
        while pos < len(body):
            open_match = self._open_re.search(body, pos)
            if not open_match:
                break
            seg_id = open_match.group(1)
            inner_start = open_match.end()

            close_match = self._close_re.search(body, inner_start)
            if not close_match:
                break
            inner_end = close_match.start()
            pos = close_match.end()

            inner = body[inner_start:inner_end].strip()
            header = self._extract_header(inner)
            segments.append(
                Segment(
                    id=seg_id,
                    header=header,
                    body=inner,
                    template=inner,
                ),
            )
        return segments

    @classmethod
    def _extract_header(cls, text: str) -> str:
        """Return the ``## §N:`` header line, or empty string."""
        for line in text.split("\n"):
            stripped = line.strip()
            if cls._HEADER_RE.match(stripped):
                return stripped
        return ""
