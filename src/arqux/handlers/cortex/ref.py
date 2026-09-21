"""cortex.ref handler (BLP-003).

Returns the definition of a CORTEX sigil: its name, type, risk level,
cognitive layer, description, and (when available) the field list.

Sigil definitions are read from the local cache in
``arqux.cortex.sigils.SIGIL_CACHE``. The cache is seeded at import
time from the standard ARQUX sigils (declared in identity files and
templates) and optionally augmented with sigils discovered from the
CODEC-CORTEX library.

Usage::

    cortex.ref(sigil="WRK")
    cortex.ref(sigil="lng")  # case-insensitive

Returns OUT-WORK with the sigil definition or OUT-ERROR with code
``NOT_FOUND`` if the sigil is unknown.
"""

from __future__ import annotations

from ...cortex.sigils import get_sigil, list_sigils
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext


def ref_handler(
    sigil: str,
    *,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Return the definition of a CORTEX sigil.

    Strictly read-only (BLP-007): this handler must not mutate governance
    state — no PULSE writes, no brain updates.

    Args:
        sigil: Sigil identifier (case-insensitive), e.g. ``"WRK"``, ``"lng"``.
        path: Accepted for signature compatibility; not used.
        ctx: Permission context (not used — the handler writes nothing).
    """
    if not sigil or not isinstance(sigil, str):
        return CortexOUT.error("sigil is required", code="INVALID_ARGS")

    definition = get_sigil(sigil)
    if definition is None:
        return CortexOUT.error(
            f"unknown sigil: {sigil!r}",
            code="NOT_FOUND",
            sigil=sigil,
            known_sigils=list_sigils(),
        )

    return CortexOUT.work(
        f"cortex.ref ok sigil={sigil.upper()} name={definition.get('name', '')}",
        sigil=sigil.upper(),
        name=definition.get("name", ""),
        type=definition.get("type", "attrs"),
        risk=definition.get("risk", ""),
        layer=definition.get("layer", ""),
        description=definition.get("description", ""),
        fields=definition.get("fields", ""),
    )
