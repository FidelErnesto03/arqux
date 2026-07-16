"""Universal Updater — template-agnostic segment writer.

Replaces content between ``<!-- TYPE:N -->`` and ``<!-- /TYPE:N -->`` markers,
preserving the ``## §N:`` header when the incoming content does not
provide one. Does NOT validate, parse, or decide — pure mechanical
block replacement.
"""

from __future__ import annotations

import re
from typing import ClassVar


class Updater:
    """Template-agnostic block updater.

    Replaces the content between ``<!-- TYPE:N -->`` and ``<!-- /TYPE:N -->``
    markers in *body* with *content*, preserving the ``## §N:`` header.

    Typical usage::

        updater = Updater("BLP")
        new_body = updater.replace(body, "3", "## §3: Preconditions\\n\\n...")

    If *content* starts with ``## §N:`` the existing header is replaced.
    Otherwise the header from the template is preserved and prepended.
    """

    _HEADER_RE: ClassVar[re.Pattern] = re.compile(r"## §\d+: .*")

    def __init__(self, type: str = "BLP") -> None:  # noqa: A002
        self.type = type

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def replace(self, body: str, segment_id: str, content: str) -> str:
        """Replace the ``<!-- TYPE:segment_id -->`` block with *content*.

        Returns the modified *body*. If the marker is not found, returns
        *body* unchanged.
        """
        open_tag = f"<!-- {self.type}:{segment_id} -->"
        close_tag = f"<!-- /{self.type}:{segment_id} -->"
        pattern = rf"{re.escape(open_tag)}.*?{re.escape(close_tag)}"

        match = re.search(pattern, body, re.DOTALL)
        if not match:
            return body  # segment not found — no-op

        existing_block = match.group(0)
        inner = existing_block[len(open_tag) : -len(close_tag)].strip()

        # Preserve the template's section header
        template_header = self._extract_header(inner)
        clean_content = content.strip()

        if template_header and not clean_content.startswith("## §"):
            clean_content = f"{template_header}\n\n{clean_content}"

        new_block = f"{open_tag}\n{clean_content}\n{close_tag}"
        return body.replace(existing_block, new_block, 1)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @classmethod
    def _extract_header(cls, text: str) -> str:
        """Return the ``## §N:`` header line, or empty string."""
        for line in text.split("\n"):
            stripped = line.strip()
            if cls._HEADER_RE.match(stripped):
                return stripped
        return ""
