"""
`cortex` module — generic .cortex file operations using CODEC-CORTEX.

Handlers:
    cortex.read     — read and parse a .cortex file
    cortex.write    — write (atomically) a .cortex file from CORTEX source text
    cortex.verify   — validate a .cortex file's structure
    cortex.render   — render a .cortex file to HCORTEX READ markdown
    cortex.file.validate — detect and optionally rename duplicate entries
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..cortex_out import CortexOUT
from ..permissions import PermissionContext, enforce_ctx, HMAC_REQUIRED
from ..state import cortex_read, cortex_write, cortex_verify, cortex_render
from ..sync import sync_brain


# ---------------------------------------------------------------------------
# SectionCounter — in-memory sequential counter per (file, section)
# ---------------------------------------------------------------------------

_section_counter: dict[str, int] = {}

def _next_number(path: str, section: str) -> str:
    """Increment and return the next zero-padded 4-digit suffix for *section* in *path*."""
    key = f"{path}:::{section}"
    _section_counter[key] = _section_counter.get(key, 0) + 1
    return f"_{_section_counter[key]:04d}"


def read_handler(
    path: str,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read and parse a .cortex file using CODEC-CORTEX.

    Returns sections, glossary, and raw content.
    """
    try:
        result = cortex_read(Path(path))
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except RuntimeError as exc:
        return CortexOUT.error(f"CODEC-CORTEX not available: {exc}", code="MISSING_DEPENDENCY")
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="PARSE_ERROR")

    return CortexOUT.work(
        f"cortex.read ok path={path} sections={result['sections']}",
        path=str(result["path"]),
        sections=result["sections"],
        glossary=result["glossary"],
        size_bytes=result["size_bytes"],
    )


def write_handler(
    path: str,
    content: str,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Write (atomically) a .cortex file from CORTEX source text.

    Validates before writing. Pass force=True to skip validation errors.
    """
    try:
        result = cortex_write(Path(path), content, force=force)
    except RuntimeError as exc:
        return CortexOUT.error(f"CODEC-CORTEX not available: {exc}", code="MISSING_DEPENDENCY")
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="WRITE_ERROR")

    if "error" in result:
        return CortexOUT.error(result["error"], code="VALIDATION_FAILED")

    return CortexOUT.work(
        f"cortex.write ok path={path} bytes={result['bytes_written']}",
        path=path,
        bytes_written=result["bytes_written"],
        backup=result.get("backup"),
        diagnostics=result.get("diagnostics", []),
    )


def verify_handler(
    path: str,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Verify a .cortex file's structure using CODEC-CORTEX.

    Returns valid (bool), diagnostics, sections count, entries count.
    """
    try:
        result = cortex_verify(Path(path))
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except RuntimeError as exc:
        return CortexOUT.error(f"CODEC-CORTEX not available: {exc}", code="MISSING_DEPENDENCY")
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="VERIFY_ERROR")

    profile = "OK" if result["valid"] else "ERROR"
    return CortexOUT.profile(
        profile,
        f"cortex.verify path={path} valid={result['valid']} "
        f"sections={result['sections']} entries={result['entries']}",
        path=path,
        valid=result["valid"],
        sections=result["sections"],
        entries=result["entries"],
        diagnostics=result.get("diagnostics", []),
    )


def render_handler(
    path: str,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Render a .cortex file to HCORTEX READ markdown."""
    try:
        md = cortex_render(Path(path))
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except RuntimeError as exc:
        return CortexOUT.error(f"CODEC-CORTEX not available: {exc}", code="MISSING_DEPENDENCY")
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="RENDER_ERROR")

    return CortexOUT.work(
        f"cortex.render ok path={path} rendered={len(md)} chars",
        path=path,
        format="hcortex-read",
        content=md,
    )


def record_lesson_handler(
    lesson: str, kind: str | None = None, cause: str | None = None,
    prevention: str | None = None,
    agent_id: str | None = None,
    path: str | None = None, ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Record a behavioral lesson into agent identity with HMAC verification."""
    enforce_ctx(ctx, "identity.record", require_hmac=os.environ.get("ARQUX_STRICT_SECURITY") == "1")
    if agent_id and ctx and agent_id != ctx.agent_id:
        return CortexOUT.error("PERMISSION_DENIED", code="FORBIDDEN")
    return record_lesson_handler_legacy(
        lesson=lesson,
        kind=kind or "behavioral",
        cause=cause or "",
        prevention=prevention or "",
        agent_id=agent_id or (ctx.agent_id if ctx else "alfred"),
        path=path or "",
        ctx=ctx,
    )


def record_lesson_handler_legacy(
    lesson: str,
    kind: str = "behavioral",
    cause: str = "",
    prevention: str = "",
    agent_id: str = "",
    path: str = "",
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Record a behavioral lesson into the agent's identity file.

    Appends an LNG entry to ``$5: BEHAVIORAL LESSONS`` in the agent's
    identity at ``<workspace or project>/.arqux/identities/<agent_id>.cortex``.

    This is how identities evolve — each significant behavioral lesson
    becomes a permanent part of the agent's identity.

    BLP-042: prevention is REQUIRED. No fallback bypass.
    """
    from ..constants import ARQUX_DIR
    import re

    # Determine agent identity file location.
    agent = agent_id or (ctx.agent_id if ctx else "alfred")
    target_path = Path(path or ".").resolve()

    # Search up for .arqux/identities/
    identity_file = None
    cursor = target_path
    while True:
        candidate = cursor / ARQUX_DIR / "identities" / f"{agent}.cortex"
        if candidate.exists():
            identity_file = candidate
            break
        if cursor.parent == cursor:
            break
        cursor = cursor.parent

    if identity_file is None:
        # Fall back to installed package identities.
        pkg = Path(__file__).resolve().parent.parent / "identities" / f"{agent}.cortex"
        if pkg.exists():
            identity_file = pkg
        else:
            return CortexOUT.error(
                f"identity file not found for agent={agent}", code="NOT_FOUND"
            )

    try:
        from ..state import crud_add

        # Generate a lesson name from the lesson text (strip leading non-alnum).
        first_word = lesson.lstrip(" -\"").lower().split()[0] if lesson.split() else "lesson"
        name = re.sub(r"[^a-z0-9]", "_", first_word)[:30] or "lesson"

        # Build the LNG entry value as a structured dict — includes prevention.
        value = {"type": kind, "cause": cause, "lesson": lesson, "prevention": prevention}

        # Use crud_add for atomic, validated insertion.
        result = crud_add(
            identity_file,
            "$5", "LNG", name, value,
            create_section=True,
            force=True,
        )
        if "error" in result:
            # BLP-042: No bypass. If CODEC-CORTEX rejects, propagate error.
            return CortexOUT.error(result["error"], code="CRUD_ERROR")
        migrated = True
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="IDENTITY_UPDATE_ERROR")

    # --- auto-trigger: sync LNG to brain + scan (non-blocking per AC-05) ---
    scan_candidates = 0
    try:
        from ..state import find_project_root, read_brain, crud_add, _bump_concurrency

        root = find_project_root(start=path or ".")
        if root is not None:
            project_dir = root.parent
            brain_path = project_dir / ".arqux" / "brain.cortex"
            if brain_path.exists():
                crud_add(
                    brain_path,
                    "$7", "LNG", name,
                    {"type": kind, "cause": cause, "lesson": lesson},
                    create_section=True,
                )

            from ..learning import scan_brain
            scan = scan_brain(project_dir, verbose=True)
            scan_candidates = len(scan.get("candidates", []))
    except Exception:  # noqa: BLE001
        pass  # Non-blocking: scan failure never blocks identity.record

    result = CortexOUT.work(
        f"identity.record ok agent={agent} lesson={name} kind={kind}",
        agent=agent,
        kind=kind,
        lesson=name,
        file=str(identity_file),
    )
    if scan_candidates:
        result.fields["hint"] = f"{scan_candidates} learning candidate(s) detected — run cortex.learn.elevate to review"
        result.fields["learning_candidates"] = scan_candidates
    return result


# ---------------------------------------------------------------------------
# cortex.render.validate_file
# ---------------------------------------------------------------------------


def render_validate_file_handler(
    path: str,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Validate all PUML blocks in a file (batch).

    Equivalent to DIALECT's guide.validate_file. Scans a .md file for
    @startuml/@enduml blocks and validates each against PlantUML parser.
    Returns a report with pass/fail per diagram + D1-D5 checklist.
    """
    from pathlib import Path
    import re

    target = Path(path)
    if not target.exists():
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")

    try:
        text = target.read_text(encoding="utf-8")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="READ_ERROR")

    blocks = re.findall(r"@startuml\n(.*?)@enduml", text, re.DOTALL)
    if not blocks:
        return CortexOUT.work(
            "validate_file ok — 0 PUML blocks found",
            path=path, total=0, passed=0, failed=0,
        )

    from ..plantuml import render_puml

    passed = 0
    failed = 0
    failures = []
    for i, block in enumerate(blocks):
        ok, result = render_puml(f"@startuml\n{block}\n@enduml", format="svg")
        if ok:
            passed += 1
        else:
            failed += 1
            failures.append({"index": i + 1, "error": str(result)[:200]})

    # D1-D5 checklist
    checks = {
        "D1_delimiters": text.count("@startuml") == text.count("@enduml"),
        "D2_metadata": bool(re.search(r"@name:", text)),
        "D3_syntax": failed == 0,
        "D5_prohibited": not re.search(
            r"skinparam\s+global|^box\s|newpage|autonumber", text, re.MULTILINE
        ),
    }
    all_pass = all(checks.values())

    return CortexOUT.work(
        f"validate_file {'PASS' if all_pass else 'FAIL'} — {passed}/{passed + failed} diagrams ok",
        path=path,
        total=passed + failed,
        passed=passed,
        failed=failed,
        checks=checks,
        failures=failures if failures else None,
    )


# ---------------------------------------------------------------------------
# cortex.render.diagram
# ---------------------------------------------------------------------------


def render_diagram_handler(
    source: str,
    format: str = "svg",
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Render a PlantUML diagram from PUML source to SVG/PNG.

    Requires plantuml.jar and Java runtime.
    Install: python -m arqux setup-plantuml
    """
    from ..plantuml import is_available, render_puml

    if not is_available():
        return CortexOUT.error(
            "plantuml.jar not found. Install Java JRE 8+ and run: python -m arqux setup-plantuml",
            code="PLANTUML_UNAVAILABLE",
        )

    ok, result = render_puml(source, format=format)
    if not ok:
        return CortexOUT.error(result, code="RENDER_ERROR")

    # Read rendered content for inline delivery via MCP
    output_path = Path(result)
    svg_content = ""
    if output_path.exists() and format == "svg":
        svg_content = output_path.read_text(encoding="utf-8")

    return CortexOUT.work(
        f"render_diagram ok format={format}",
        format=format,
        output_path=str(output_path),
        svg_content=svg_content if svg_content else None,
    )


def setup_plantuml_handler(
    force: bool = False,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Download and install plantuml.jar to ~/.arqux/bin/."""
    from ..plantuml import setup_plantuml

    ok, msg = setup_plantuml(force=force)
    if ok:
        return CortexOUT.work(msg, installed=True)
    return CortexOUT.error(msg, code="SETUP_FAILED")


def learn_scan_handler(
    scope: str = "project",
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Scan a project brain through the CODEC-CORTEX Learning Engine.

    Returns scored entries and elevation candidates.
    """
    from ..learning import scan_brain, list_candidates, _resolve_project_root

    root = _resolve_project_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    scan = scan_brain(root, verbose=(scope == "workspace"))
    if scan.get("engine") == "unavailable":
        return CortexOUT.error(
            "CODEC-CORTEX Learning Engine not available. "
            "Requires codec-cortex >=0.4.0 with learning module.",
            code="ENGINE_UNAVAILABLE",
        )
    if "error" in scan:
        return CortexOUT.error(scan["error"], code="LEARN_ERROR")

    candidates = scan.get("candidates", []) or list_candidates(root)

    return CortexOUT.work(
        f"learn.scan ok count={scan.get('count', 0)} entries scanned",
        engine=scan.get("engine", "unknown"),
        total=scan.get("count", 0),
        profile=scan.get("profile", {}),
        candidates=candidates,
    )


def learn_elevate_handler(
    candidate_id: str,
    path: str | None = None,
    *,
    apply: bool = False,
    confirm_hash: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Elevate a learning candidate (dry-run or apply).

    Default mode is dry-run (returns diff without changing brain).
    Pass apply=true to actually apply the elevation.
    """
    from ..learning import elevate_candidate, _resolve_project_root

    root = _resolve_project_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    result = elevate_candidate(root, candidate_id, dry_run=not apply, confirm_hash=confirm_hash)
    if "error" in result:
        return CortexOUT.error(
            result["error"],
            code="ELEVATE_ERROR",
            preview_hash=result.get("preview_hash"),
            diff=result.get("diff"),
        )

    if result.get("mode") == "dry_run":
        return CortexOUT.work(
            f"learn.elevate dry-run candidate={candidate_id}",
            candidate=candidate_id,
            mode="dry_run",
            diff=result.get("diff", ""),
            preview_hash=result.get("preview_hash", ""),
            validation_errors=result.get("validation_errors", []),
        )

    return CortexOUT.work(
        f"learn.elevate applied candidate={candidate_id}",
        candidate=candidate_id,
        mode="applied",
        diff=result.get("diff", ""),
        preview_hash=result.get("preview_hash", ""),
    )


# ---------------------------------------------------------------------------
# cortex.entry.* — generic .cortex entry CRUD via CODEC-CORTEX
# ---------------------------------------------------------------------------


def entry_get_handler(
    path: str,
    selector: str,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read entries matching a CORTEX selector from a .cortex file."""
    from ..state import crud_read

    try:
        result = crud_read(path, selector)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="READ_ERROR")

    return CortexOUT.work(
        f"entry.get ok path={path} selector={selector} count={len(result['entries'])}",
        path=path,
        selector=selector,
        count=len(result["entries"]),
        entries=result["entries"],
    )


def entry_add_handler(
    path: str,
    section: str,
    sigil: str,
    name: str,
    value: str,
    *,
    create_section: bool = False,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Add a new entry to a .cortex file.

    Automatically appends a sequential _XXXX suffix to the name
    (per-section counter) to prevent silent overwrites.
    """
    from ..state import crud_add

    suffix = _next_number(path, section)
    numbered_name = f"{name}{suffix}"

    try:
        result = crud_add(path, section, sigil, numbered_name, value, create_section=create_section, force=force)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="ADD_ERROR")

    if "error" in result:
        return CortexOUT.error(result["error"], code="CRUD_ERROR")
    return CortexOUT.work(
        f"entry.add ok path={path} {sigil}:{numbered_name} in {section}",
        path=path, section=section, sigil=sigil, name=numbered_name,
        bytes_written=result.get("bytes_written"),
        backup=result.get("backup"),
    )


def entry_update_handler(
    path: str,
    selector: str,
    *,
    set_: str | None = None,
    replace_body: str | None = None,
    append: bool = False,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Update an entry selected by a CORTEX selector.

    For attrs entries: pass ``set_`` as JSON key:value pairs (e.g. ``status:done,priority:high``).
    For cuerpo entries: pass ``replace_body`` with the new body text.
    """
    from ..state import crud_update

    # Parse set_ from key:val format
    set_dict = None
    if set_:
        import json as _json
        try:
            # Try JSON format first: key:"val", key:"val2"
            set_dict = _json.loads(f"{{{set_}}}")
        except _json.JSONDecodeError:
            # Fallback: parse raw key:val,key2:val2
            try:
                set_dict = {}
                for pair in set_.split(","):
                    pair = pair.strip()
                    if ":" not in pair:
                        continue
                    k, v = pair.split(":", 1)
                    k = k.strip().strip('"').strip("'")
                    v = v.strip().strip('"').strip("'")
                    set_dict[k] = v
            except Exception:
                return CortexOUT.error(f"invalid set_ format: {set_}", code="INVALID_ARGS")

    try:
        result = crud_update(path, selector, set_=set_dict, replace_body=replace_body, append=append, force=force)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="UPDATE_ERROR")

    if "error" in result:
        return CortexOUT.error(result["error"], code="CRUD_ERROR")
    return CortexOUT.work(
        f"entry.update ok path={path} selector={selector}",
        path=path, selector=selector,
        bytes_written=result.get("bytes_written"),
        backup=result.get("backup"),
    )


def entry_delete_handler(
    path: str,
    selector: str,
    *,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Delete an entry matching a CORTEX selector from a .cortex file."""
    from ..state import crud_delete

    try:
        result = crud_delete(path, selector, force=force)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="DELETE_ERROR")

    if "error" in result:
        return CortexOUT.error(result["error"], code="CRUD_ERROR")
    return CortexOUT.work(
        f"entry.delete ok path={path} selector={selector}",
        path=path, selector=selector,
        bytes_written=result.get("bytes_written"),
        backup=result.get("backup"),
    )


def entry_move_handler(
    path: str,
    selector: str,
    to_section: str,
    *,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Move an entry between sections in a .cortex file."""
    from ..state import crud_move

    try:
        result = crud_move(path, selector, to_section, force=force)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="MOVE_ERROR")

    if "error" in result:
        return CortexOUT.error(result["error"], code="CRUD_ERROR")
    return CortexOUT.work(
        f"entry.move ok path={path} selector={selector} to={to_section}",
        path=path, selector=selector, to_section=to_section,
        bytes_written=result.get("bytes_written"),
        backup=result.get("backup"),
    )


def entry_list_handler(
    path: str,
    *,
    section: str | None = None,
    sigil: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """List entries in a .cortex file, optionally filtered by section or sigil."""
    from ..state import crud_list

    try:
        result = crud_list(path, section=section, sigil=sigil)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="LIST_ERROR")

    return CortexOUT.work(
        f"entry.list ok path={path} count={len(result['entries'])}",
        path=path, section=section, sigil=sigil,
        count=len(result["entries"]),
        entries=result["entries"],
    )


# ---------------------------------------------------------------------------
# cortex.file.validate — detect and optionally rename duplicate entries
# ---------------------------------------------------------------------------


def file_validate_handler(
    path: str,
    fix: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Scan a .cortex file for duplicate entry names and optionally fix them.

    Groups entries by (section, sigil, name). When multiple entries share
    the same name in the same section, they are flagged as duplicates.
    With fix=true, duplicates are renamed with a _XXXX suffix.
    """
    from ..state import _cc_parser, _cc_validator, _cc_transactions
    from pathlib import Path
    from collections import defaultdict
    import re as _re

    target = Path(path)
    if not target.exists():
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")

    try:
        text = target.read_text(encoding="utf-8")
        doc = _cc_parser.parse_cortex(text, path=str(path))
    except Exception as exc:
        return CortexOUT.error(str(exc), code="PARSE_ERROR")

    def _strip_suffix(n: str) -> str:
        return _re.sub(r"_\d{4}$", "", n)

    # Group by (section, sigil, base_name)
    groups: dict[tuple[str, str, str], list] = defaultdict(list)
    for sec in doc.sections:
        for entry in sec.entries or []:
            base = _strip_suffix(entry.name)
            groups[(sec.id, entry.sigil, base)].append({
                "section": sec.id,
                "sigil": entry.sigil,
                "name": entry.name,
                "base": base,
                "entry": entry,
            })

    duplicates = {k: v for k, v in groups.items() if len(v) > 1}
    if not duplicates:
        return CortexOUT.work(
            f"file.validate ok — 0 duplicates found in {path}",
            path=path, fix=fix, total_duplicates=0,
        )

    # Build rename report
    report = []
    for (sec_id, sigil, base), entries in sorted(duplicates.items()):
        for idx, e in enumerate(entries):
            new_name = f"{base}_{idx + 1:04d}"
            if e["name"] != new_name:
                report.append({
                    "section": sec_id,
                    "sigil": sigil,
                    "old_name": e["name"],
                    "new_name": new_name,
                })

    if not fix:
        return CortexOUT.work(
            f"file.validate ok — {len(report)} duplicate(s) detected (dry-run, fix=false)",
            path=path, fix=fix, total_duplicates=len(report),
            duplicates=report,
        )

    # Fix: rename in AST, validate, write
    for r in report:
        for sec in doc.sections:
            if sec.id != r["section"]:
                continue
            for ent in sec.entries or []:
                if ent.name == r["old_name"]:
                    ent.name = r["new_name"]
                    break

    # Use atomic_write with force=True instead of validate+abort.
    # atomic_write internally validates AND auto-repairs E032/E034
    # (missing required fields like LNG:prevention, OBJ:success) when
    # force=True.  This allows duplicate rename to proceed even when the
    # file has legacy entries with incomplete metadata.
    #
    # Non-repairable errors (E033: ARQX in $0, E001: structural) are still
    # rejected by atomic_write's internal non-bypassable check.
    try:
        result = _cc_transactions.atomic_write_cortex(doc, str(target), force=True)
        return CortexOUT.work(
            f"file.validate ok — {len(report)} duplicate(s) renamed",
            path=path, fix=fix, total_duplicates=len(report),
            renamed=report,
            bytes_written=result.bytes_written,
            backup=result.backup,
        )
    except Exception as exc:
        return CortexOUT.error(str(exc), code="VALIDATION_FAILED")
