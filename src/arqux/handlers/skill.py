"""`skill` module — skill management under Arqux governance.

Handlers:
    skill.import  — acquire a skill from external source, store original in originals/
    skill.convert — convert skill from native format to CORTEX ultra-dense
    skill.record  — record a deviation (ADA) in the skill file's $0: ADAPTATIONS section
    skill.evolve  — apply an approved adaptation, updating the skill
    skill.list    — list all available skills in .arqux/skills/

Adaptations are stored INSIDE the skill file as section $0: ADAPTATIONS (before $1).
Each ADA entry documents a deviation between what the skill says and what was actually done.
When evolve is approved, the adaptation moves from $0 into the relevant section
and $0 is updated accordingly.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..state import find_project_root, find_workspace_root
from ..sync import sync_brain

SKILL_DIR = "skills"
ORIGINALS_DIR = "skills/originals"


def _resolve_arqux_root(path: str | None = None) -> Path | None:
    """Find the .arqux/ root from path (workspace or project)."""
    ws = find_workspace_root(start=path)
    if ws:
        return ws  # find_workspace_root already returns .arqux/ path
    pr = find_project_root(start=path)
    if pr:
        return pr  # find_project_root already returns .arqux/ path
    return None


def _skill_path(arqux: Path, name: str) -> Path:
    """Return the path to a skill file in .arqux/skills/."""
    return arqux / SKILL_DIR / f"{name}.skill.md"


def _append_ada_to_skill(skill_path: Path, name: str, line: str) -> None:
    """Append an ADA entry to the skill file's $0: ADAPTATIONS section.

    If no $0 section exists, creates it before $1.
    """
    content = skill_path.read_text(encoding="utf-8")
    ada_entry = f"ADA:{name}{{{line}}}\n"

    # Look for existing $0: ADAPTATIONS section
    adapt_marker = "$0: ADAPTATIONS"
    if adapt_marker in content:
        # Append after the $0 header
        idx = content.index(adapt_marker)
        insert_at = content.index("\n", idx) + 1  # end of $0 line
        # Find end of $0 section (next $N:)
        rest = content[insert_at:]
        next_sec = re.search(r"\n\$1:", rest)
        if next_sec:
            insert_at += next_sec.start()
        content = content[:insert_at] + ada_entry + content[insert_at:]
    else:
        # Insert $0: ADAPTATIONS before $1: IDENTITY
        sec1 = content.find("\n$1:")
        if sec1 != -1:
            insert_at = content.rfind("\n", 0, sec1) + 1
            content = content[:insert_at] + f"$0: ADAPTATIONS\n\n{ada_entry}\n" + content[insert_at:]
        else:
            content += f"\n$0: ADAPTATIONS\n\n{ada_entry}\n"

    skill_path.write_text(content, encoding="utf-8")


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

    BLP-009: ``content`` accepts a CORTEX entry string with keys
    ``source, name, body``. When the content parses as CORTEX and
    contains a ``body`` key, the parsed values override the individual
    ``source``, ``name`` params, and ``body`` becomes the actual content
    to write. Otherwise content is treated as raw text (retrocompatible).
    """
    arqux = _resolve_arqux_root(path)
    if arqux is None:
        return CortexOUT.error("no arqux root found (workspace or project)", code="NOT_FOUND")

    originals_dir = arqux / ORIGINALS_DIR
    originals_dir.mkdir(parents=True, exist_ok=True)

    # BLP-009: try to parse content as CORTEX. If it yields a 'body'
    # key, treat it as the CORTEX content form. Otherwise, treat as
    # raw text (retrocompatibility).
    raw_body: str | None = None
    if content:
        from ..cortex.parse_content import parse_content_entry
        parsed = parse_content_entry(content)
        if parsed and "body" in parsed:
            # CORTEX form — extract fields.
            source = parsed.get("source", source)
            name = parsed.get("name", name)
            raw_body = parsed["body"]
        else:
            raw_body = content

    skill_filename = f"{name}.skill.md"
    dest = originals_dir / skill_filename

    if not raw_body:
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

    dest.write_text(raw_body, encoding="utf-8")
    return CortexOUT.work(
        f"skill.import ok name={name} source={source} size={len(raw_body)}",
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

    The converted skill includes:
      - $0: ADAPTATIONS — empty section ready for future ADA entries
      - $1: IDENTITY — skill metadata
      - $2: DESCRIPTION — overview
      - $3: CANON — original content preserved as backup

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

    dst = _skill_path(arqux, name)
    raw = src.read_text(encoding="utf-8")

    lines = raw.splitlines()
    lines[0].lstrip("#").strip() if lines else name
    first_lines = [l for l in lines[1:8] if l.startswith("#")]
    description = " ".join(l.lstrip("#").strip() for l in first_lines) or f"Imported skill: {name}"

    cortex_content = (
        "$0: ADAPTATIONS\n"
        "# ADA entries are appended here as deviations are recorded.\n"
        "# When evolve is approved, entries move to the relevant section.\n"
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
                    f"Load from .arqux/skills/{name}.skill.md.",
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

    Writes the ADA entry directly into the skill file's $0: ADAPTATIONS section.
    Accumulated ADAs drive skill evolution via skill.evolve.

    Parameters:
        name: Skill name (e.g. "oracle-apex").
        expected: What the skill said to do.
        actual: What was actually done.
        reason: Why the deviation occurred.
    """
    arqux = _resolve_arqux_root(path)
    if arqux is None:
        return CortexOUT.error("no arqux root found", code="NOT_FOUND")

    skill_path = _skill_path(arqux, name)
    if not skill_path.exists():
        return CortexOUT.error(
            f"skill {name!r} not found in .arqux/skills/",
            code="NOT_FOUND",
            hint="Use skill.import + skill.convert first.",
        )

    agent = (ctx or PermissionContext.from_env()).agent_id
    attrs = (
        f"skill:{name!r}, expected:{expected!r}, actual:{actual!r}, "
        f"reason:{reason!r}, agent:{agent!r}, status:\"active\""
    )

    _append_ada_to_skill(skill_path, name, attrs)

    return CortexOUT.work(
        f"skill.record ok name={name} agent={agent}",
        name=name,
        expected=expected,
        actual=actual,
        reason=reason,
        agent=agent,
        stored_in="$0: ADAPTATIONS",
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

    Finds the ADA entry in the skill file's $0: ADAPTATIONS section.
    When ``apply=False`` (default): shows the proposed change (dry-run).
    When ``apply=True``: marks the ADA as applied in $0 (preserves history).

    Parameters:
        name: Skill name.
        adaptation_id: The ADA entry selector (ADA:<name>).
        apply: If True, marks as applied. Default is dry-run.
    """
    arqux = _resolve_arqux_root(path)
    if arqux is None:
        return CortexOUT.error("no arqux root found", code="NOT_FOUND")

    skill_path = _skill_path(arqux, name)
    if not skill_path.exists():
        return CortexOUT.error(f"skill {name!r} not found in skills/", code="NOT_FOUND")

    content = skill_path.read_text(encoding="utf-8")

    # Find the $0: ADAPTATIONS section
    adapt_marker = "$0: ADAPTATIONS"
    if adapt_marker not in content:
        return CortexOUT.error(f"no $0: ADAPTATIONS section found in skill {name!r}", code="NOT_FOUND")

    idx = content.index(adapt_marker)
    sec_start = content.index("\n", idx) + 1
    rest = content[sec_start:]
    next_sec = re.search(r"\n\$1:", rest)
    sec_end = sec_start + (next_sec.start() if next_sec else len(rest))
    adapt_section = content[sec_start:sec_end]

    # Find the target ADA
    lines = adapt_section.splitlines()
    target_line = None
    for _i, line in enumerate(lines):
        if adaptation_id in line and '"active"' in line:
            target_line = line
            break

    if not target_line:
        return CortexOUT.error(
            f"adaptation {adaptation_id!r} not found (or already applied)",
            code="NOT_FOUND",
        )

    if not apply:
        return CortexOUT.work(
            f"skill.evolve dry-run name={name} adaptation={adaptation_id}",
            name=name,
            adaptation=adaptation_id,
            mode="dry_run",
            entry=target_line.strip(),
            instruction="Review the adaptation entry above. "
                        "Call with apply=true to mark it as applied.",
        )

    # Mark the ADA as applied in-place (change "active" → "applied")
    updated = content.replace(
        f'{target_line}',
        target_line.replace('status:"active"', 'status:"applied"'),
        1,
    )
    skill_path.write_text(updated, encoding="utf-8")

    return CortexOUT.work(
        f"skill.evolve applied name={name} adaptation={adaptation_id}",
        name=name,
        adaptation=adaptation_id,
        mode="applied",
        note="ADA marked as applied in $0: ADAPTATIONS. Entry preserved for history.",
    )


# ---------------------------------------------------------------------------
# skill.edit
# ---------------------------------------------------------------------------


def _replace_skill_section(body: str, section_id: str, new_content: str) -> str | None:
    """Replace a CORTEX section in a skill file.

    Section can be:
      - ``$0`` (bare, no title)
      - ``$1`` or ``$1: TITLE``
      - ``$2.1`` or ``$2.1: TITLE``

    The new_content should NOT include the section header —
    the original header is preserved. If new_content does include
    the header, it is stripped to avoid duplication.
    Returns the new body, or None if the section was not found.
    """
    normalized = section_id.lstrip("$")
    target_header = re.compile(rf"^\${re.escape(normalized)}(?::.*)?$")
    section_header = re.compile(r"^\$(\d+(?:\.\d+)?)(?::.*)?$")

    lines = body.splitlines(keepends=True)
    start = None
    for idx, line in enumerate(lines):
        if target_header.match(line.rstrip("\r\n")):
            start = idx
            break

    if start is None:
        return None

    end = len(lines)
    for idx in range(start + 1, len(lines)):
        match = section_header.match(lines[idx].rstrip("\r\n"))
        if match and match.group(1) != normalized:
            end = idx
            break

    hdr = lines[start].rstrip("\r\n")

    # Strip section header from new_content if present
    clean = new_content
    clean_lines = clean.lstrip().splitlines()
    if clean_lines and target_header.match(clean_lines[0].rstrip("\r\n")):
        first_lf = clean.index("\n") if "\n" in clean else len(clean)
        clean = clean[first_lf + 1:] if first_lf < len(clean) else ""
    clean = clean.strip()
    new_section = hdr + "\n" + clean + "\n"
    new_body = "".join(lines[:start]) + new_section + "".join(lines[end:])
    if new_body == body:
        return None
    return new_body


def edit_skill(
    name: str,
    content: str | None = None,
    section: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Edit (read or write) a skill file in .arqux/skills/.

    Without ``content``: returns the current content of the skill file.
    With ``content`` and no ``section``: atomically replaces the entire skill file.
    With ``content`` and ``section``: replaces only that section (e.g. ``$0``, ``$1``, ``$2.1``).

    This is the governed alternative to direct file editing of skills.
    Skills are NOT governance state — they are working documents.

    BLP-009: ``content`` accepts a CORTEX entry string with keys
    ``name, body, section``. When the content parses as CORTEX and
    contains a ``body`` key, the parsed values override the individual
    ``name``, ``section`` params, and ``body`` becomes the actual
    content to write. Otherwise content is treated as raw text
    (retrocompatible).
    """
    arqux = _resolve_arqux_root(path)
    if arqux is None:
        return CortexOUT.error("no arqux root found", code="NOT_FOUND")

    # BLP-009: try to parse content as CORTEX. If it yields a 'body'
    # key, treat it as the CORTEX content form. Otherwise, treat as
    # raw text (retrocompatibility).
    raw_body: str | None = None
    if content:
        from ..cortex.parse_content import parse_content_entry
        parsed = parse_content_entry(content)
        if parsed and "body" in parsed:
            name = parsed.get("name", name)
            # 'section' from CORTEX overrides the param if present.
            parsed_section = parsed.get("section")
            if parsed_section:
                section = parsed_section
            raw_body = parsed["body"]
        else:
            raw_body = content

    skill_path = _skill_path(arqux, name)

    if not raw_body:
        if not skill_path.exists():
            return CortexOUT.error(
                f"skill {name!r} not found in .arqux/skills/",
                code="NOT_FOUND",
                hint="Use skill.list to see available skills.",
            )
        raw = skill_path.read_text(encoding="utf-8")
        return CortexOUT.work(
            f"skill.edit read name={name} size={len(raw)}",
            name=name,
            size=len(raw),
            content=raw,
        )

    if section:
        if not skill_path.exists():
            return CortexOUT.error(
                f"skill {name!r} not found in .arqux/skills/",
                code="NOT_FOUND",
            )
        current = skill_path.read_text(encoding="utf-8")
        updated = _replace_skill_section(current, section, raw_body)
        if updated is None:
            return CortexOUT.error(
                f"section ${section} not found in skill {name!r}",
                code="NOT_FOUND",
                hint="Sections use CORTEX format: $0, $1, $2.1, etc.",
            )
        skill_path.write_text(updated, encoding="utf-8")
        sync_brain(arqux.parent, "skill.edit", detail=f"section ${section} of {name} written")
        return CortexOUT.work(
            f"skill.edit section name={name} section=${section} size={len(raw_body)}",
            name=name,
            section=f"${section}",
            size=len(raw_body),
            status="section_written",
        )

    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(raw_body, encoding="utf-8")
    sync_brain(arqux.parent, "skill.edit", detail=f"full write of {name} ({len(raw_body)} bytes)")
    return CortexOUT.work(
        f"skill.edit write name={name} size={len(raw_body)}",
        name=name,
        size=len(raw_body),
        status="written",
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
        content = f.read_text(encoding="utf-8")
        size = len(content)
        was_imported = (originals_dir / f.name).exists()
        ada_count = content.count("ADA:")
        available.append({
            "name": f.name.replace(".skill.md", ""),
            "size": size,
            "imported": was_imported,
            "adaptations": ada_count,
        })

    return CortexOUT.work(
        f"skills: {len(available)} available",
        count=len(available),
        skills=available,
    )


# ---------------------------------------------------------------------------
# skill.install (BLP-010)
# ---------------------------------------------------------------------------


def install_skill(
    source: str,
    name: str,
    *,
    content: str | None = None,
    dry_run: bool = False,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Install a skill: import + validate + register in brain.cortex $6/SKL.

    BLP-010 meta-handler. Wraps:

    1. ``skill.import`` — stores the raw skill content in ``originals/``.
    2. Validation — checks the skill has a ``$0`` header (CORTEX form).
    3. Registration — appends an ``SKL`` entry to brain.cortex $6/SKL.

    Args:
        source: Skill source (URL, marketplace, etc.).
        name: Skill name.
        content: Optional CORTEX content with keys ``source, name, body``.
            When provided, parsed values override individual params.
        dry_run: If True, report what would happen without modifying state.
        path: Path to workspace/project root.
        ctx: Permission context.
    """
    # Merge content CORTEX.
    raw_body: str | None = None
    if content:
        from ..cortex.parse_content import parse_content_entry
        parsed = parse_content_entry(content)
        if parsed and "body" in parsed:
            source = parsed.get("source", source)
            name = parsed.get("name", name)
            raw_body = parsed["body"]
        else:
            raw_body = content

    arqux = _resolve_arqux_root(path)
    if arqux is None:
        return CortexOUT.error("no arqux root found", code="NOT_FOUND")

    steps_report: list[dict[str, str]] = []

    # Step 1: import (store in originals/).
    if dry_run:
        steps_report.append({"step": "import", "status": "simulated"})
    else:
        if raw_body is None:
            return CortexOUT.error(
                "content (raw body) is required for install",
                code="INVALID_ARGS",
            )
        originals_dir = arqux / ORIGINALS_DIR
        originals_dir.mkdir(parents=True, exist_ok=True)
        dest = originals_dir / f"{name}.skill.md"
        if dest.exists():
            return CortexOUT.error(
                f"skill {name!r} already exists in originals/",
                code="ALREADY_EXISTS",
            )
        dest.write_text(raw_body, encoding="utf-8")
        steps_report.append({"step": "import", "status": "done", "path": str(dest)})

    # Step 2: validate — check for $0 header.
    if raw_body is not None:
        has_header = "$0" in raw_body[:200] or "$1" in raw_body[:200]
        if has_header:
            steps_report.append({"step": "validate", "status": "passed"})
        else:
            steps_report.append({
                "step": "validate",
                "status": "warning",
                "reason": "no $0/$1 header found — skill may not be in CORTEX form",
            })
    else:
        steps_report.append({"step": "validate", "status": "skipped"})

    # Step 3: register in brain.cortex $6/SKL.
    if dry_run:
        steps_report.append({"step": "register", "status": "simulated"})
    else:
        # Append SKL entry to brain.cortex $6 (LESSONS section in legacy,
        # or a SKILLS section if present).
        try:
            from ..state import find_project_root
            project_arqux = find_project_root(start=path)
            if project_arqux is not None:
                brain_path = project_arqux / "brain.cortex"
                if brain_path.exists():
                    brain_text = brain_path.read_text(encoding="utf-8")
                    # Append a simple SKL registration line.
                    skl_entry = f"SKL:{name}{{source:\"{source}\", status:\"installed\"}}\n"
                    # Find the $6 section or append at the end.
                    if "$6" in brain_text:
                        # Insert after the $6 header line.
                        idx = brain_text.index("$6")
                        end_of_line = brain_text.index("\n", idx) + 1
                        brain_text = brain_text[:end_of_line] + skl_entry + brain_text[end_of_line:]
                    else:
                        # Append a new $6 section.
                        brain_text += f"\n$6: SKILLS\n\n{skl_entry}\n"
                    brain_path.write_text(brain_text, encoding="utf-8")
                    steps_report.append({
                        "step": "register",
                        "status": "done",
                        "path": str(brain_path),
                    })
                else:
                    steps_report.append({
                        "step": "register",
                        "status": "skipped",
                        "reason": "no brain.cortex found",
                    })
            else:
                steps_report.append({
                    "step": "register",
                    "status": "skipped",
                    "reason": "no project root found",
                })
        except Exception as exc:  # noqa: BLE001
            steps_report.append({
                "step": "register",
                "status": "failed",
                "reason": str(exc),
            })

    # PULSE.
    if not dry_run:
        try:
            from ..pulse import append_pulse_to_brain, next_pulse_event_id
            from ..state import find_project_root as _fpr
            project_arqux = _fpr(start=path)
            if project_arqux is not None:
                agent = (ctx or PermissionContext.from_env()).agent_id
                event_id = next_pulse_event_id(project_arqux)
                append_pulse_to_brain(
                    project_arqux,
                    event_id=event_id,
                    task_id="-",
                    kind="skill_install",
                    agent=agent,
                    payload=f"[skill.install] name={name} source={source}",
                )
        except Exception:  # noqa: BLE001
            pass

    return CortexOUT.work(
        f"skill.install ok name={name} source={source} dry_run={dry_run} "
        f"steps={len(steps_report)}",
        name=name,
        source=source,
        dry_run=dry_run,
        steps=steps_report,
    )


handler_schemas = [
    {"name": "skill.import", "fn": import_skill, "description": "Acquire a skill from external source, store original in originals/. Accepts content as CORTEX with keys source, name, body (BLP-009).", "input_schema": {"type": "object", "properties": {"source": {"type": "string", "description": "Origin (marketplace, platform, url:...)"}, "name": {"type": "string", "description": "Skill name (e.g. oracle-apex)"}, "content": {"type": "string", "description": "Raw skill content, or CORTEX entry 'source:...,name:...,body:...' (BLP-009). Omit to get instructions first."}, "path": {"type": "string", "description": "Path to workspace/project root"}}, "required": ["source", "name"]}},
    {"name": "skill.convert", "fn": convert_skill, "description": "Convert a skill from original format to CORTEX ultra-dense.", "input_schema": {"type": "object", "properties": {"name": {"type": "string", "description": "Skill name"}, "path": {"type": "string"}}, "required": ["name"]}},
    {"name": "skill.record", "fn": record_adaptation, "description": "Record a deviation (ADA) when a skill does not match the real context.", "input_schema": {"type": "object", "properties": {"name": {"type": "string", "description": "Skill name"}, "expected": {"type": "string", "description": "What the skill says"}, "actual": {"type": "string", "description": "What was actually done"}, "reason": {"type": "string", "description": "Why the deviation occurred"}, "path": {"type": "string"}}, "required": ["name", "expected", "actual", "reason"]}},
    {"name": "skill.evolve", "fn": evolve_skill, "description": "Apply an approved adaptation to a skill. Default is dry-run.", "input_schema": {"type": "object", "properties": {"name": {"type": "string", "description": "Skill name"}, "adaptation_id": {"type": "string", "description": "Adaptation entry selector"}, "apply": {"type": "boolean", "default": False, "description": "If true, apply the evolution"}, "path": {"type": "string"}}, "required": ["name", "adaptation_id"]}},
    {"name": "skill.edit", "fn": edit_skill, "description": "Edit (read, write, or section-edit) a skill file in .arqux/skills/. Without content: returns the skill content. With content but no section: atomically replaces the entire skill file. With content and section: replaces only that CORTEX section (e.g. $0, $1, $2.1). Accepts content as CORTEX with keys name, body, section (BLP-009).", "input_schema": {"type": "object", "properties": {"name": {"type": "string", "description": "Skill name (e.g. handlers)"}, "content": {"type": "string", "description": "New content, or CORTEX entry 'name:...,body:...,section:...' (BLP-009). Omit to read current content."}, "section": {"type": "string", "description": "Section ID to replace (e.g. $0, $1, $2.1). Only valid with content."}, "path": {"type": "string", "description": "Path to workspace/project root"}}, "required": ["name"]}},
    {"name": "skill.list", "fn": list_skills, "description": "List all available skills in .arqux/skills/.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}}},
    {"name": "skill.install", "fn": install_skill, "description": "Install a skill: import + validate + register in brain.cortex $6/SKL (BLP-010 meta-handler). Supports dry_run mode.", "input_schema": {"type": "object", "properties": {"source": {"type": "string", "description": "Skill source."}, "name": {"type": "string", "description": "Skill name."}, "content": {"type": "string", "description": "CORTEX content with keys source, name, body."}, "dry_run": {"type": "boolean", "default": False, "description": "If true, report what would happen without modifying state."}, "path": {"type": "string"}}, "required": ["source", "name"]}},
]
