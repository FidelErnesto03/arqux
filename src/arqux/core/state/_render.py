"""Rendering and writing helpers for CORTEX files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ... import formats
from . import _HAS_CODEC_CORTEX, _cc_parser, _cc_renderer


def write_cortex_pair(
    directory: Path,
    stem: str,
    frontmatter: dict[str, Any],
    body: str,
) -> tuple[Path, Path]:
    """Write a `.cortex` file.

    Governance files (brain, manifest, meta-brain, projects, cycle, T-NNN)
    are written in canonical CODEC-CORTEX sigil format when the library is
    available. Other files use the legacy YAML frontmatter format.

    HCORTEX .md twins are NOT automatically generated. Request them on demand
    via `cortex.render` MCP handler when the Architect needs human review.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    cortex_path = directory / f"{stem}.cortex"

    # BLP-042: ALL .cortex files use CODEC-CORTEX writer.
    if _HAS_CODEC_CORTEX:
        cortex_content = _render_governance_cortex(stem, frontmatter, body)
    else:
        cortex_content = _render_cortex(frontmatter, body)

    cortex_path.write_text(cortex_content, encoding="utf-8")
    return cortex_path, cortex_path  # Backward compat: returns (cortex, cortex)


def _render_governance_cortex(
    stem: str,
    frontmatter: dict[str, Any],
    body: str | dict,
) -> str:
    """Render a governance file in canonical CODEC-CORTEX format.

    Delegates to ``formats.render_governance_cortex()`` which uses
    CODEC-CORTEX's ``write_cortex()`` when available, falling back to
    the string-based builders otherwise.
    """
    return formats.render_governance_cortex(stem, frontmatter, body)


def _write_md_twin(
    cortex_path: Path,
    hcortex_path: Path,
    frontmatter: dict[str, Any],
    body: str,
) -> bool:
    """Write the .md twin. Returns True if CODEC-CORTEX was used."""
    if _HAS_CODEC_CORTEX:
        # Try to parse as proper CORTEX and render.
        try:
            text = cortex_path.read_text(encoding="utf-8")
            doc = _cc_parser.parse_cortex(text, path=str(cortex_path))
            md_content = _cc_renderer.render_hcortex_read(doc)
            hcortex_path.write_text(md_content, encoding="utf-8")
            return True
        except Exception:  # noqa: BLE001
            # Fall through to manual rendering if parse fails (e.g. YAML format).
            pass

    hcortex_content = _render_hcortex(frontmatter, body)
    hcortex_path.write_text(hcortex_content, encoding="utf-8")
    return False


def _render_cortex(frontmatter: dict[str, Any], body: str) -> str:
    """Render a CORTEX file: YAML frontmatter + body with # SECTION markers."""
    lines: list[str] = ["---"]
    for key, value in frontmatter.items():
        lines.append(f"{key}: {_yaml_value(value)}")
    lines.append("---")
    lines.append("")
    lines.append(body.rstrip())
    lines.append("")
    return "\n".join(lines)


def _render_hcortex(frontmatter: dict[str, Any], body: str) -> str:
    """Render an HCORTEX file: human-readable markdown derived from CORTEX.

    HCORTEX is a form of writing markdown oriented to facilitate reading,
    understanding, and organization, minimizing token consumption. The
    transformation rules are defined in AGENTS.md §9 (HCORTEX format).
    """
    title = frontmatter.get("id") or frontmatter.get("name") or "Untitled"
    lines: list[str] = [f"# {title}", ""]
    if "name" in frontmatter and frontmatter["name"] != title:
        lines.append(f"**Name:** {frontmatter['name']}")
        lines.append("")

    lines.append("## Metadata")
    lines.append("")
    for key, value in frontmatter.items():
        if key in {"id", "name"}:
            continue
        lines.append(f"- **{key}:** {_yaml_value(value)}")
    lines.append("")
    lines.append("## Body")
    lines.append("")
    lines.append(body.rstrip())
    lines.append("")
    return "\n".join(lines)


def _yaml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        return "[" + ", ".join(str(v) for v in value) + "]"
    if isinstance(value, dict):
        return json.dumps(value)
    return str(value)
