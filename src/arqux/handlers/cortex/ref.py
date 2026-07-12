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
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import find_project_root


def ref_handler(
    sigil: str,
    *,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Return the definition of a CORTEX sigil.

    Args:
        sigil: Sigil identifier (case-insensitive), e.g. ``"WRK"``, ``"lng"``.
        path: Optional path to project root (used only for PULSE recording).
        ctx: Permission context (used to identify the agent for PULSE).
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

    _record_pulse(path, ctx, sigil=sigil, action="cortex.ref")

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


def _record_pulse(
    path: str | None,
    ctx: PermissionContext | None,
    *,
    sigil: str,
    action: str,
) -> None:
    """Append a PULSE event for a cortex.ref call (best-effort)."""
    try:
        root = find_project_root(start=path)
        if root is None:
            return
        agent = (ctx or PermissionContext.from_env()).agent_id
        event_id = next_pulse_event_id(root)
        append_pulse_to_brain(
            root,
            event_id=event_id,
            task_id="-",
            kind="handler_call",
            agent=agent,
            payload=f"[{action}] sigil={sigil.upper()}",
        )
    except Exception:  # noqa: BLE001 — PULSE is best-effort
        pass
