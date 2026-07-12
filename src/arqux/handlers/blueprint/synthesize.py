"""blueprint.synthesize handler (BLP-007).

Writes a Blueprint's content sections in a single call from a CORTEX
content payload. Uses ``parse_blp_template()`` (BLP-013) to validate
section IDs against ``BLP_TEMPLATE.md``.

Creates the BLP ``.md`` file if it doesn't exist (status=draft). Does
NOT change BLP status — only writes content. Writes atomically (temp
file + rename).
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

from ...blueprint.template import parse_blp_template
from ...constants import BLUEPRINTS_DIR, CYCLES_DIR
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import find_project_root


# ---------------------------------------------------------------------------
# synthesize
# ---------------------------------------------------------------------------


def synthesize_blueprint(
    bp_id: str,
    content: str,
    *,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Write a Blueprint's content sections in one call.

    Args:
        bp_id: Blueprint ID (e.g. ``"BLP-007"``). If the BLP file does
            not exist, it is created with status=draft.
        content: CORTEX content payload. Two forms accepted:

            - **Per-section form:** ``$1:{body1}\n$2:{body2}\n...``
            - **Single-body form:** ``$0:{1: "body1", 2: "body2", ...}``

            In the per-section form, the section ID is the part after
            ``$`` and before ``:``. The body is everything between
            ``{`` and the matching ``}``.

        path: Starting path for resolving the project root.
        ctx: Permission context.

    Returns ``OUT-WORK`` with:

    - ``blueprint_id`` (str)
    - ``path`` (str) — path to the written BLP file
    - ``sections_written`` (list[str])
    - ``sections_skipped`` (list[str]) — IDs in content but not in template
    - ``bytes_written`` (int)
    - ``created`` (bool) — true if the BLP was created (vs. updated)
    """
    if not bp_id or not isinstance(bp_id, str):
        return CortexOUT.error("bp_id is required", code="INVALID_ARGS")
    if not re.match(r"^BLP-\d{3}$", bp_id):
        return CortexOUT.error(
            f"invalid bp_id={bp_id!r} (must match BLP-NNN)",
            code="INVALID_ARGS",
        )
    if not content or not isinstance(content, str):
        return CortexOUT.error("content is required", code="INVALID_ARGS")

    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # Validate section IDs against template.
    tmpl_result = parse_blp_template(path=path)
    if tmpl_result.profile != "OUT-WORK":
        return CortexOUT.error(
            f"cannot validate sections: {tmpl_result.message}",
            code="TEMPLATE_MISSING",
        )
    valid_ids = set(tmpl_result.fields.get("markers", {}))

    # Parse content into section_id -> body.
    sections = _parse_content_sections(content)
    if not sections:
        return CortexOUT.error(
            "no sections parsed from content",
            code="INVALID_ARGS",
        )

    sections_skipped = [sid for sid in sections.keys() if f"BLP:{sid}" not in valid_ids]
    sections_to_write = {sid: body for sid, body in sections.items()
                         if f"BLP:{sid}" in valid_ids}
    if not sections_to_write:
        return CortexOUT.error(
            f"no valid sections to write. Skipped: {sections_skipped}",
            code="INVALID_ARGS",
            skipped=sections_skipped,
            valid_ids=sorted(valid_ids),
        )

    # Find or create the BLP file.
    bp_path, fm, body, created = _find_or_create_blueprint(root, bp_id, ctx)

    # Apply each section via marker replacement.
    new_body = body
    sections_written: list[str] = []
    for sid, section_content in sections_to_write.items():
        marker_id = f"BLP:{sid}"
        before = new_body
        new_body = _replace_marker(new_body, marker_id, section_content)
        if new_body != before:
            sections_written.append(sid)

    # Atomic write: temp file + rename.
    bytes_written = _atomic_write(bp_path, fm, new_body)

    _record_pulse(root, ctx, bp_id=bp_id, action="synthesize",
                  sections_written=sections_written)

    return CortexOUT.work(
        f"blueprint.synthesize ok id={bp_id} sections={len(sections_written)} "
        f"created={created} bytes={bytes_written}",
        blueprint_id=bp_id,
        path=str(bp_path),
        sections_written=sections_written,
        sections_skipped=sections_skipped,
        bytes_written=bytes_written,
        created=created,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_content_sections(content: str) -> dict[str, str]:
    """Parse a CORTEX content payload into ``{section_id: body}``.

    Recognises both the per-section form (``$1:{body1}\n$2:{body2}``)
    and the single-body form (``$0:{1: "body1", 2: "body2"}``).
    """
    out: dict[str, str] = {}
    text = content.strip()

    # Per-section form: scan for $N:{...} or $N.N:{...}
    pattern = re.compile(r"\$(\d+(?:\.\d+)?):\s*\{")
    matches = list(pattern.finditer(text))
    if matches:
        for i, m in enumerate(matches):
            sid = m.group(1)
            start = m.end() - 1  # position of the opening brace
            body = _extract_brace_body(text, start)
            if body is not None:
                out[sid] = body.strip()
        return out

    # Single-body form: $0:{...} containing key:val pairs.
    # Fall back to parsing the whole content as a key:val map.
    inner = _extract_brace_body(text, text.find("{"))
    if inner is None:
        return {}
    for part in _split_top_level(inner, ","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        k, _, v = part.partition(":")
        k = k.strip().strip('"').strip("'")
        v = v.strip()
        if len(v) >= 2 and v[0] in ('"', "'") and v[-1] == v[0]:
            v = v[1:-1]
        if k:
            out[k] = v
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


def _split_top_level(text: str, sep: str) -> list[str]:
    """Split ``text`` on ``sep`` at top level (not inside braces/quotes)."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: str | None = None
    for c in text:
        if quote:
            buf.append(c)
            if c == quote:
                quote = None
        elif c in ('"', "'"):
            quote = c
            buf.append(c)
        elif c == "{":
            depth += 1
            buf.append(c)
        elif c == "}":
            depth = max(0, depth - 1)
            buf.append(c)
        elif c == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(c)
    if buf:
        parts.append("".join(buf))
    return parts


def _find_or_create_blueprint(
    root: Path,
    bp_id: str,
    ctx: PermissionContext | None,
) -> tuple[Path, dict[str, Any], str, bool]:
    """Find the BLP file across cycles, or create a new draft.

    Returns ``(bp_path, frontmatter, body, created)``.
    """
    cycles_base = root / CYCLES_DIR
    if cycles_base.exists():
        for cdir in cycles_base.iterdir():
            bp_path = cdir / BLUEPRINTS_DIR / f"{bp_id}.md"
            if bp_path.exists():
                text = bp_path.read_text(encoding="utf-8")
                fm, body = _parse_md(text)
                return bp_path, fm, body, False

    # Not found — create in the latest cycle.
    if cycles_base.exists():
        open_cycles = sorted([d.name for d in cycles_base.iterdir() if d.is_dir()])
        cycle_id = open_cycles[-1] if open_cycles else "CYCLE-01"
    else:
        cycle_id = "CYCLE-01"
        cycles_base.mkdir(parents=True, exist_ok=True)

    bp_dir = cycles_base / cycle_id / BLUEPRINTS_DIR
    bp_dir.mkdir(parents=True, exist_ok=True)
    bp_path = bp_dir / f"{bp_id}.md"

    # Use the template as the starting body.
    from ...blueprint.template import _resolve_template, TEMPLATE_NAME
    template_path = _resolve_template(path=str(root.parent))
    if template_path and template_path.exists():
        body = template_path.read_text(encoding="utf-8")
        body = body.replace("blueprint_id: \"\"", f'blueprint_id: "{bp_id}"')
        body = body.replace("# BLP-NNN: Título", f"# {bp_id}: Synthesized")
    else:
        body = f"---\nblueprint_id: \"{bp_id}\"\nstatus: \"draft\"\n---\n\n# {bp_id}: Synthesized\n"

    fm, body = _parse_md(body)
    fm["blueprint_id"] = bp_id
    fm["status"] = "draft"
    fm["governor"] = (ctx or PermissionContext.from_env()).agent_id

    return bp_path, fm, body, True


def _parse_md(text: str) -> tuple[dict[str, Any], str]:
    """Parse a BLP .md file into (frontmatter, body)."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_raw = parts[1].strip()
    body = parts[2].strip()
    fm: dict[str, Any] = {}
    for line in fm_raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip().rstrip("@")
        v = v.strip().strip('"').strip("'")
        if v == "true":
            v = True
        elif v == "false":
            v = False
        fm[k] = v
    return fm, body


def _replace_marker(text: str, marker_id: str, content: str) -> str:
    """Replace the content between ``<!-- marker_id -->`` markers.

    Preserves the section header (``## §N: Title``) if present.
    """
    open_tag = f"<!-- {marker_id} -->"
    close_tag = f"<!-- /{marker_id} -->"
    pattern = rf"{re.escape(open_tag)}.*?{re.escape(close_tag)}"

    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return text

    block = match.group(0)
    inner = block[len(open_tag):-len(close_tag)].strip()

    # Preserve section header (first line starting with ## §).
    header = ""
    for line in inner.split("\n"):
        if line.strip().startswith("## §"):
            header = line.rstrip()
            break

    if header:
        replacement = f"{open_tag}\n{header}\n\n{content}\n{close_tag}"
    else:
        replacement = f"{open_tag}\n{content}\n{close_tag}"

    return text.replace(block, replacement, 1)


def _atomic_write(bp_path: Path, fm: dict[str, Any], body: str) -> int:
    """Write the BLP .md file atomically (temp file + rename)."""
    # Render frontmatter.
    fm_lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, bool):
            v = str(v).lower()
        elif isinstance(v, str):
            v = f'"{v}"'
        fm_lines.append(f"{k}: {v}")
    fm_lines.append("---")
    fm_lines.append("")
    content = "\n".join(fm_lines) + body

    bp_path.parent.mkdir(parents=True, exist_ok=True)
    # Write to temp file in the same directory, then rename.
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{bp_path.stem}_",
        suffix=".tmp",
        dir=str(bp_path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, bp_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return len(content)


def _record_pulse(
    root: Path,
    ctx: PermissionContext | None,
    *,
    bp_id: str,
    action: str,
    sections_written: list[str],
) -> None:
    """Append a PULSE event for the synthesize call (best-effort)."""
    try:
        agent = (ctx or PermissionContext.from_env()).agent_id
        event_id = next_pulse_event_id(root)
        append_pulse_to_brain(
            root,
            event_id=event_id,
            task_id=bp_id,
            kind="blueprint_lifecycle",
            agent=agent,
            payload=f"[{action}] sections={','.join(sections_written)}",
        )
    except Exception:  # noqa: BLE001
        pass
