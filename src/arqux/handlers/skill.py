"""`skill` module — skill management under Arqux governance.

Handlers:
    skill.import  — acquire a skill from external source, store original in originals/
    skill.convert — convert skill from native format to CORTEX ultra-dense
    skill.record  — record a deviation (ADA) when the skill doesn't match context
    skill.evolve  — apply an approved adaptation, updating the skill
    skill.list    — list all available skills in .arqux/skills/
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from ..constants import ARQUX_DIR
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..state import find_workspace_root, find_project_root


ADA_FILENAME = "{name}.adapt.cortex"
SKILL_DIR = "skills"
ORIGINALS_DIR = "skills/originals"
ADAPTATIONS_DIR = "skills/adaptations"


def _resolve_arqux_root(path: str | None = None) -> Path | None:
    """Find the .arqux/ root from path (workspace or project)."""
    ws = find_workspace_root(start=path)
    if ws:
        return ws  # find_workspace_root already returns .arqux/ path
    pr = find_project_root(start=path)
    if pr:
        return pr  # find_project_root already returns .arqux/ path
    return None


# ---------------------------------------------------------------------------
# skill.import
# ---------------------------------------------------------------------------


def import_skill(
    source: str,
    name: str,
    content: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Acquire a skill from an external source.

    Stores the original (canon) in ``.arqux/skills/originals/``.
    The skill is NOT yet usable — ``skill.convert`` must be called next.

    Parameters:
        source: Origin identifier (e.g. "marketplace", "platform", "url:...").
        name: Skill name (e.g. "oracle-apex", "ci-cd-pipeline").
        content: Raw content of the skill. If omitted, the handler returns
                 instructions for the agent to provide it.
        path: Path to workspace or project root.
    """
    arqux = _resolve_arqux_root(path)
    if arqux is None:
        return CortexOUT.error("no arqux root found (workspace or project)", code="NOT_FOUND")

    originals_dir = arqux / ORIGINALS_DIR
    originals_dir.mkdir(parents=True, exist_ok=True)

    skill_filename = f"{name}.skill.md"
    dest = originals_dir / skill_filename

    if not content:
        return CortexOUT.work(
            f"skill.import ready name={name} source={source}",
            name=name,
            source=source,
            status="awaiting_content",
            instruction=f"Provide the raw content of {name}.skill.md from {source}. "
                        f"Once provided, call skill.import again with content=<raw_text>.",
        )

    if dest.exists():
        return CortexOUT.error(
            f"skill {name!r} already exists in originals/",
            code="ALREADY_EXISTS",
        )

    dest.write_text(content, encoding="utf-8")
    return CortexOUT.work(
        f"skill.import ok name={name} source={source} size={len(content)}",
        name=name,
        source=source,
        storage=str(dest),
        status="imported",
        next_step=f"Call skill.convert(name={name!r}) to convert to CORTEX ultra-dense format.",
    )


# ---------------------------------------------------------------------------
# skill.convert
# ---------------------------------------------------------------------------


def convert_skill(
    name: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Convert a skill from its original format to CORTEX ultra-dense.

    Reads from ``.arqux/skills/originals/<name>.skill.md``,
    converts to CORTES ultra-dense format,
    writes to ``.arqux/skills/<name>.skill.md``.

    The original remains untouched in originals/.
    """
    arqux = _resolve_arqux_root(path)
    if arqux is None:
        return CortexOUT.error("no arqux root found", code="NOT_FOUND")

    src = arqux / ORIGINALS_DIR / f"{name}.skill.md"
    if not src.exists():
        return CortexOUT.error(
            f"original skill {name!r} not found in originals/",
            code="NOT_FOUND",
            hint="Use skill.import first to acquire the skill.",
        )

    dst = arqux / SKILL_DIR / f"{name}.skill.md"
    raw = src.read_text(encoding="utf-8")

    # Build an ultra-dense CORTEX wrapper.
    # The original content is wrapped inside a DESC:cannon block so
    # it remains accessible but the skill is now in CORTEX format.
    lines = raw.splitlines()
    title = lines[0].lstrip("#").strip() if lines else name
    description = " ".join(
        l.lstrip("#").strip() for l in lines[1:6] if l.startswith("#")
    ) or f"Imported skill: {name}"

    cortex_content = (
        "$0\n"
        "# -- $0: SKILL GLOSSARY --\n"
        f"# SKL | {name} | skill | attrs | B | {description[:60]}\n"
        "\n"
        "$1: IDENTITY\n"
        f"SKL:{name}{{source:\"imported\", format:\"cortex\", lines:{len(lines)}, file:\"{name}.skill.md\"}}\n"
        "\n"
        "$2: DESCRIPTION\n"
        f"DESC:overview{{{description}}}\n"
        "\n"
        "$3: CANON\n"
        "DESC:original_canon{\n"
        f"{raw}\n"
        "}\n"
    )

    dst.write_text(cortex_content, encoding="utf-8")
    return CortexOUT.work(
        f"skill.convert ok name={name} cortex={len(cortex_content)}c original={len(raw)}c",
        name=name,
        format="cortex-ultra-dense",
        size=len(cortex_content),
        original_size=len(raw),
        location=str(dst),
        instruction=f"Skill {name!r} is now available in CORTEX format. "
                    f"Load from .arqux/skills/{name}.skill.md. "
                    f"Use skill.list() to see all available skills.",
    )


# ---------------------------------------------------------------------------
# skill.record
# ---------------------------------------------------------------------------


def record_adaptation(
    name: str,
    expected: str,
    actual: str,
    reason: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Record a deviation (ADA) from a skill.

    When an agent follows a skill but the real context requires a different
    approach, it records an adaptation. Accumulated adaptations drive skill
    evolution.

    Parameters:
        name: Skill name (e.g. "oracle-apex").
        expected: What the skill said to do.
        actual: What was actually done.
        reason: Why the deviation occurred.
    """
    arqux = _resolve_arqux_root(path)
    if arqux is None:
        return CortexOUT.error("no arqux root found", code="NOT_FOUND")

    adaptations_dir = arqux / ADAPTATIONS_DIR
    adaptations_dir.mkdir(parents=True, exist_ok=True)

    adapt_file = adaptations_dir / ADA_FILENAME.format(name=name)

    agent = (ctx or PermissionContext.from_env()).agent_id
    ada_line = (
        f"ADA:{name}{{skill:{name!r}, expected:{expected!r}, "
        f"actual:{actual!r}, reason:{reason!r}, agent:{agent!r}, "
        f"status:\"active\"}}\n"
    )

    with open(adapt_file, "a", encoding="utf-8") as f:
        f.write(ada_line)

    return CortexOUT.work(
        f"skill.record ok name={name} agent={agent}",
        name=name,
        expected=expected,
        actual=actual,
        reason=reason,
        agent=agent,
        file=str(adapt_file),
    )


# ---------------------------------------------------------------------------
# skill.evolve
# ---------------------------------------------------------------------------


def evolve_skill(
    name: str,
    adaptation_id: str,
    path: str | None = None,
    *,
    apply: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Apply an approved adaptation to a skill.

    When ``apply=False`` (default): shows the proposed change (dry-run).
    When ``apply=True``: applies the adaptation to the skill file.

    Parameters:
        name: Skill name.
        adaptation_id: The adaptation entry selector (ADA:<name>).
        apply: If True, applies the change. Default is dry-run.
    """
    arqux = _resolve_arqux_root(path)
    if arqux is None:
        return CortexOUT.error("no arqux root found", code="NOT_FOUND")

    adapt_file = arqux / ADAPTATIONS_DIR / ADA_FILENAME.format(name=name)
    if not adapt_file.exists():
        return CortexOUT.error(f"no adaptations found for skill {name!r}", code="NOT_FOUND")

    # Read all adaptations, find the target one
    adapts = adapt_file.read_text(encoding="utf-8").strip().splitlines()
    target_entry = None
    remaining = []
    for line in adapts:
        if adaptation_id in line and "status:\"active\"" in line:
            target_entry = line
        else:
            remaining.append(line)

    if not target_entry:
        return CortexOUT.error(
            f"adaptation {adaptation_id!r} not found in {adapt_file.name}",
            code="NOT_FOUND",
        )

    if not apply:
        return CortexOUT.work(
            f"skill.evolve dry-run name={name} adaptation={adaptation_id}",
            name=name,
            adaptation=adaptation_id,
            mode="dry_run",
            entry=target_entry,
            instruction="Review the adaptation entry above. "
                        "Call with apply=true to update the skill.",
        )

    # Apply: update the skill with a note about the adaptation
    skill_file = arqux / SKILL_DIR / f"{name}.skill.md"
    if not skill_file.exists():
        return CortexOUT.error(f"skill {name!r} not found in skills/", code="NOT_FOUND")

    skill_content = skill_file.read_text(encoding="utf-8")
    evolution_note = (
        "\n$4: EVOLUTION\n"
        f"# Adaptation applied: {adaptation_id}\n"
        f"ADA:{name}{{status:\"applied\", entry:{target_entry!r}}}\n"
    )
    skill_content += evolution_note
    skill_file.write_text(skill_content, encoding="utf-8")

    # Mark adaptation as applied
    adapt_file.write_text("\n".join(remaining), encoding="utf-8")

    return CortexOUT.work(
        f"skill.evolve applied name={name} adaptation={adaptation_id}",
        name=name,
        adaptation=adaptation_id,
        mode="applied",
        evolution_section="$4: EVOLUTION added to skill",
    )


# ---------------------------------------------------------------------------
# skill.list
# ---------------------------------------------------------------------------


def list_skills(
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """List all available skills in .arqux/skills/."""
    arqux = _resolve_arqux_root(path)
    if arqux is None:
        return CortexOUT.error("no arqux root found", code="NOT_FOUND")

    skills_dir = arqux / SKILL_DIR
    if not skills_dir.exists():
        return CortexOUT.work("skills: 0 available", skills=[])

    originals_dir = arqux / ORIGINALS_DIR

    available = []
    for f in sorted(skills_dir.glob("*.skill.md")):
        was_imported = (originals_dir / f.name).exists()
        size = len(f.read_text(encoding="utf-8"))
        available.append({
            "name": f.stem,
            "size": size,
            "imported": was_imported,
        })

    return CortexOUT.work(
        f"skills: {len(available)} available",
        count=len(available),
        skills=available,
    )
