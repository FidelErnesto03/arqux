"""BLP-003: the authority boundary — recall yields context, never permissions.

§7.1 and L-SEC-04: nothing a recall returns may authorize a tool or elevate
privilege. Only explicit, governed permissions grant access; recall results
are ignored by design, so a memory that *claims* authority has none.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

_FORBIDDEN_PAYLOAD_FIELDS = (
    "permission",
    "permissions",
    "grant",
    "grants",
    "authorize",
    "authorization",
    "tool",
    "tools",
    "token",
)


class AuthorityViolation(RuntimeError):
    """Raised when recalled content tries to carry authority."""


class AuthorityBoundary:
    """The single gate that decides tool access. Recall has no voice here."""

    def can_use_tool(
        self,
        tool: str,
        *,
        recall_results: Iterable[Any] = (),
        permissions: Iterable[str] = (),
    ) -> bool:
        # Only explicit, governed permissions authorize. ``recall_results`` is
        # accepted so callers are explicit about what they are NOT using:
        # context is not authority.
        return tool in set(permissions)

    def assert_recall_grants_nothing(self, recall_result: Any) -> None:
        """Reject a recall result whose payload smuggles an authority field."""
        record = getattr(recall_result, "record", None)
        if record is None:
            return
        for field in getattr(record, "payload", {}):
            if str(field).lower() in _FORBIDDEN_PAYLOAD_FIELDS:
                raise AuthorityViolation(
                    f"recall payload carries an authority field: {field!r}"
                )
