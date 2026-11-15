"""Elevation planning (native, governed)."""
from __future__ import annotations

from typing import Any

from ..protocol import LearningDocument
from ..sections import section_for_sigil
from .aggregate import aggregate_value
from .patch import Patch

_PROTECTED_SIGILS = {"CNST", "IDN", "AXM", "CLAIM", "LIM"}


def _derive_name(candidate: Any) -> str:
    source_entries = list(getattr(candidate, "source_entries", []) or [])
    if not source_entries:
        return f"elevated_{str(getattr(candidate, 'target', 'knw')).lower()}"
    first = source_entries[0]
    name = first.split(":", 1)[1] if ":" in first else first
    parts = name.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return name


def _is_protected(source_sigil: str, attrs: dict[str, Any] | None) -> bool:
    sig = str(source_sigil or "")
    if sig in _PROTECTED_SIGILS:
        if attrs is None:
            return True
        if sig == "CNST":
            return str(attrs.get("severity", "")).lower() == "blocking"
        return True
    return False


def plan_patch(
    document: LearningDocument,
    policy_set: Any,
    candidate: Any,
    *,
    policy_id: str | None = None,
    admin_confirmed: bool = False,
    user_confirmed: bool = False,
) -> Patch:
    source_entries = list(getattr(candidate, "source_entries", []) or [])
    target = str(getattr(candidate, "target", "KNW"))
    source_sigil = source_entries[0].split(":", 1)[0] if source_entries else ""
    src_attrs: dict[str, Any] | None = None
    for _sec, e in document.iter_entries():
        if f"{e.sigil}:{e.name}" == (source_entries[0] if source_entries else None):
            src_attrs = e.value if isinstance(e.value, dict) else None
            break

    dest_section = section_for_sigil(target, document) \
        or section_for_sigil("WRK", document) or "$7"
    reason = getattr(candidate, "reason", None) or f"elevate {source_sigil}→{target}"
    promotion_score = int(getattr(candidate, "promotion_score", 0) or 0)

    if _is_protected(source_sigil, src_attrs):
        return Patch(
            source_entries=source_entries,
            target_layer=target,
            target_section=dest_section,
            new_entry_sigil=target,
            new_entry_name=_derive_name(candidate),
            new_entry_value={},
            reason=f"protected sigil {source_sigil} cannot be elevated by common policy",
            policy_id=policy_id,
            promotion_score=promotion_score,
            affected_files=[".arqux/brain.cortex"],
            mode="block",
        )

    new_value = aggregate_value(document, source_entries, target)
    mode = "propose"

    # Admin gate / policy decisions (best-effort, native contract).
    try:
        entries = list(getattr(policy_set, "entries", ()) or [])
        chosen = None
        for e in entries:
            if policy_id and getattr(e, "policy_id", None) == policy_id:
                chosen = e
                break
        if chosen is None and entries:
            # pick first matching source->target rule if present
            for e in entries:
                if getattr(e, "source", None) == source_sigil and getattr(e, "target", None) == target:
                    chosen = e
                    break
        if chosen is not None:
            requires = getattr(chosen, "requires", None)
            action = getattr(chosen, "action", "propose")
            if requires == "admin_policy":
                mode = "apply" if admin_confirmed else "propose"
            elif action == "block":
                return Patch(
                    source_entries=source_entries,
                    target_layer=target,
                    target_section=dest_section,
                    new_entry_sigil=target,
                    new_entry_name=_derive_name(candidate),
                    new_entry_value=new_value,
                    reason="policy blocks elevation",
                    policy_id=policy_id or getattr(chosen, "policy_id", None),
                    promotion_score=promotion_score,
                    affected_files=[".arqux/brain.cortex"],
                    mode="block",
                )
            elif action == "apply" and (user_confirmed or admin_confirmed):
                mode = "apply"
            else:
                mode = "propose"
        elif any(getattr(e, "action", None) == "block" for e in entries):
            return Patch(
                source_entries=source_entries,
                target_layer=target,
                target_section=dest_section,
                new_entry_sigil=target,
                new_entry_name=_derive_name(candidate),
                new_entry_value=new_value,
                reason="policy blocks elevation",
                policy_id=policy_id,
                promotion_score=promotion_score,
                affected_files=[".arqux/brain.cortex"],
                mode="block",
            )
    except Exception:
        mode = "propose"

    return Patch(
        source_entries=source_entries,
        target_layer=target,
        target_section=dest_section,
        new_entry_sigil=target,
        new_entry_name=_derive_name(candidate),
        new_entry_value=new_value,
        reason=reason,
        policy_id=policy_id,
        promotion_score=promotion_score,
        affected_files=[".arqux/brain.cortex"],
        mode=mode,
    )


__all__ = ["plan_patch"]
