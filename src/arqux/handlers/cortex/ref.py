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

from typing import Any

from ...cortex.sigils import get_sigil, list_sigils
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext

#: Standard brain.cortex section map (templates/brain.cortex, v0.7 standard):
#: section id → title → sigils that live in it.
BRAIN_SECTION_MAP: dict[str, dict[str, Any]] = {
    "$0": {"title": "GLOSSARY", "sigils": []},
    "$19": {"title": "ARQUX METADATA", "sigils": ["ARQX"]},
    "$1": {"title": "IDENTITY", "sigils": ["IDN", "DOM"]},
    "$2": {"title": "FOCUS", "sigils": ["FCS"]},
    "$3": {"title": "OBJECTIVES", "sigils": ["OBJ"]},
    "$4": {"title": "SESSIONS", "sigils": ["SES"]},
    "$5": {"title": "HANDOFFS", "sigils": ["HDL"]},
    "$6": {"title": "PULSE", "sigils": ["AUD"]},
    "$7": {"title": "LESSONS", "sigils": ["LNG"]},
    "$8": {"title": "ACTIVE_CONTEXT", "sigils": ["WRK"]},
    "$9": {"title": "RISKS", "sigils": ["RSK"]},
    "$10": {"title": "KNOWLEDGE", "sigils": ["KNW"]},
    "$11": {"title": "CONCURRENCY", "sigils": ["ERR"]},
    "$12": {"title": "PACKAGES", "sigils": []},
}


def ref_handler(
    sigil: str | None = None,
    *,
    sections: bool = False,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Return the definition of a CORTEX sigil.

    With ``sections=True`` returns the standard brain.cortex section map
    (section id → title → sigils) instead of a sigil definition.

    Strictly read-only (BLP-007): this handler must not mutate governance
    state — no PULSE writes, no brain updates.

    Args:
        sigil: Sigil identifier (case-insensitive), e.g. ``"WRK"``, ``"lng"``.
        sections: When True, return the standard brain section map instead
            of a sigil definition.
        path: Accepted for signature compatibility; not used.
        ctx: Permission context (not used — the handler writes nothing).
    """
    if sections:
        return CortexOUT.work(
            f"cortex.ref ok sections={len(BRAIN_SECTION_MAP)}",
            sections=BRAIN_SECTION_MAP,
            source="templates/brain.cortex (standard section map)",
        )

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
