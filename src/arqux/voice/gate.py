"""Mention gate: the agent speaks only when explicitly addressed."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .config import DEFAULT_MENTION_PATTERNS


class MentionGate:
    """Detects explicit address to the agent in a transcript line.

    Modes:
      * ``always``  — every utterance is addressed (1:1 voice mode)
      * ``mention`` — only utterances containing a pattern match
    """

    def __init__(self, patterns: Iterable[str] | None = None,
                 mode: str = "mention"):
        self.mode = mode
        pats = list(patterns or DEFAULT_MENTION_PATTERNS)
        self._res = [re.compile(p, re.IGNORECASE) for p in pats]

    def set_patterns(self, patterns: Iterable[str]) -> None:
        self._res = [re.compile(p, re.IGNORECASE) for p in patterns]

    def set_mode(self, mode: str) -> None:
        assert mode in ("always", "mention")
        self.mode = mode

    def check(self, text: str) -> dict:
        """Return {addressed, match} for an utterance."""
        if self.mode == "always":
            return {"addressed": True, "match": None}
        for rx in self._res:
            m = rx.search(text)
            if m:
                return {"addressed": True, "match": m.group(0)}
        return {"addressed": False, "match": None}
