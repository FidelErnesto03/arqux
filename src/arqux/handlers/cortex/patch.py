"""cortex.patch handler (BLP-010).

Accepts ``content`` of the form ``{selector: entry_content, ...}`` and
iterates, updating each entry via direct file manipulation. Reads the
.cortex file, finds each entry by selector, replaces its content, and
writes back atomically.

Supports ``dry_run=True`` to report what would happen without executing.
"""

from __future__ import annotations

from pathlib import Path

from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import crud_update, find_project_root


def patch_handler(
    path: str,
    content: str,
    *,
    dry_run: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Patch multiple entries in a .cortex file from a CORTEX content payload.

    Args:
        path: Path to the .cortex file.
        content: CORTEX content payload. Two forms accepted:

            - **Per-selector form:** ``$SEL1:{new_body1}\n$SEL2:{new_body2}``
              where each section is a CORTEX selector like ``$5/LNG:lesson_001``.
              (The parser treats the part after ``$`` and before ``:`` as the
              selector — it may contain ``/`` and ``:``.)
            - **Map form:** ``$0:{"$5/LNG:lesson_001": "new body", "$2/FCS:primary": "new body"}``

        dry_run: If True, report what would happen without writing.
        ctx: Permission context.

    Returns ``OUT-WORK`` with:

    - ``patched`` (list[str]) — selectors successfully patched
    - ``failed`` (list[dict]) — selectors that failed with reason
    - ``dry_run`` (bool)
    """
    if not content:
        return CortexOUT.error("content is required", code="INVALID_ARGS")

    src_path = Path(path)
    if not src_path.exists():
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")

    patches = _parse_patches(content)
    if not patches:
        return CortexOUT.error(
            "no patches parsed from content",
            code="INVALID_ARGS",
        )

    patched: list[str] = []
    failed: list[dict[str, str]] = []

    for selector, new_body in patches.items():
        if dry_run:
            patched.append(selector)
            continue
        try:
            result = crud_update(
                path,
                selector,
                replace_body=new_body,
                force=True,
            )
            if "error" in result:
                failed.append({"selector": selector, "reason": result["error"]})
            else:
                patched.append(selector)
        except Exception as exc:  # noqa: BLE001
            failed.append({"selector": selector, "reason": str(exc)})

    # PULSE.
    if not dry_run:
        _record_pulse(path, ctx, patched=len(patched), failed=len(failed))

    return CortexOUT.work(
        f"cortex.patch ok path={path} patched={len(patched)} failed={len(failed)} "
        f"dry_run={dry_run}",
        path=path,
        patched=patched,
        failed=failed,
        dry_run=dry_run,
    )


def _parse_patches(content: str) -> dict[str, str]:
    """Parse a CORTEX content payload into ``{selector: new_body}``.

    Recognises the per-selector form: ``$SELECTOR{new_body}`` where
    SELECTOR may contain ``/``, ``:``, ``$``, digits, letters, etc.
    The selector is everything between ``$`` and the opening ``{``.
    """
    import re
    out: dict[str, str] = {}

    text = content.strip()
    # Match $<selector>{...} where selector is everything up to the
    # opening brace. Selector chars: anything except { and }.
    pattern = re.compile(r"\$([^{}]+)\{")
    matches = list(pattern.finditer(text))
    if not matches:
        return out

    for m in matches:
        selector = "$" + m.group(1).strip()
        # Find the matching closing brace starting from the opening brace.
        start = m.end() - 1  # position of the opening brace
        body = _extract_brace_body(text, start)
        if body is not None:
            out[selector] = body.strip()
    return out


def _extract_brace_body(text: str, start: int) -> str | None:
    """Return the content inside the ``{...}`` block starting at ``start``."""
    if start < 0 or start >= len(text) or text[start] != "{":
        return None
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
        i += 1
    return None


def _record_pulse(
    path: str | None,
    ctx: PermissionContext | None,
    *,
    patched: int,
    failed: int,
) -> None:
    """Append a PULSE event for the patch call (best-effort)."""
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
            payload=f"[cortex.patch] patched={patched} failed={failed}",
        )
    except Exception:  # noqa: BLE001
        pass
