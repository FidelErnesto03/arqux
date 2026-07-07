"""
`cortex` module — generic .cortex file operations using CODEC-CORTEX.

These are UTILITY handlers (outside the 24-handler governance budget) that
expose CODEC-CORTEX as MCP tools for reading, writing, verifying, and
rendering arbitrary .cortex files that ARE NOT governance state.

For governance state (brain.cortex, manifest.cortex, tasks, etc.), use the
governance handlers (workspace.*, project.*, cycle.*, task.*, evidence.*).

Handlers:
    cortex.read     — read and parse a .cortex file
    cortex.write    — write (atomically) a .cortex file from CORTEX source text
    cortex.verify   — validate a .cortex file's structure
    cortex.render   — render a .cortex file to HCORTEX READ markdown
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..state import cortex_read, cortex_write, cortex_verify, cortex_render


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
    lesson: str,
    kind: str = "behavioral",
    cause: str = "",
    agent_id: str = "",
    path: str = "",
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Record a behavioral lesson into the agent's identity file.

    Appends an LNG entry to ``$5: BEHAVIORAL LESSONS`` in the agent's
    identity at ``<workspace or project>/.arqux/identities/<agent_id>.cortex``.

    This is how identities evolve — each significant behavioral lesson
    becomes a permanent part of the agent's identity.
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
        text = identity_file.read_text(encoding="utf-8")

        # Generate a lesson name from the lesson text.
        name = re.sub(r"[^a-z0-9]", "_", lesson.lower().split()[0])[:30] or "lesson"

        # Build the LNG entry.
        escaped_lesson = lesson.replace('"', '\\"')
        escaped_cause = cause.replace('"', '\\"')
        entry = f'LNG:{name}{{type:"{kind}", cause:"{escaped_cause}", lesson:"{escaped_lesson}"}}'

        # Append after $5: BEHAVIORAL LESSONS section (or before $6 if no lessons yet).
        if "$5: BEHAVIORAL LESSONS" in text:
            # Find the end of section 5 and insert before section 6.
            sec5_end = text.find("\n$6:")
            if sec5_end == -1:
                sec5_end = len(text)
            text = text[:sec5_end] + f"\n{entry}\n" + text[sec5_end:]
        else:
            # No behavioral lessons section — append before $6 or at end.
            sec6_pos = text.find("\n$6:")
            if sec6_pos != -1:
                insert_at = text.rfind("\n", 0, sec6_pos) + 1
                text = text[:insert_at] + f"\n$5: BEHAVIORAL LESSONS\n\n{entry}\n" + text[insert_at:]
            else:
                text += f"\n\n$5: BEHAVIORAL LESSONS\n\n{entry}\n"

        identity_file.write_text(text, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="IDENTITY_UPDATE_ERROR")

    return CortexOUT.work(
        f"identity.record ok agent={agent} lesson={name} kind={kind}",
        agent=agent,
        kind=kind,
        lesson=name,
        file=str(identity_file),
    )


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
