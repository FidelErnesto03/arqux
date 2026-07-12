"""Cortex diagram rendering and PlantUML setup handlers."""

from __future__ import annotations

import re
from pathlib import Path

from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...plantuml import is_available, render_puml, setup_plantuml


def render_validate_file_handler(
    path: str,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Validate all PUML blocks in a file (batch).

    Equivalent to DIALECT's guide.validate_file. Scans a .md file for
    @startuml/@enduml blocks and validates each against PlantUML parser.
    Returns a report with pass/fail per diagram + D1-D5 checklist.
    """
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
    if not is_available():
        return CortexOUT.error(
            "plantuml.jar not found. Install Java JRE 8+ and run: python -m arqux setup-plantuml",
            code="PLANTUML_UNAVAILABLE",
        )

    ok, result = render_puml(source, format=format)
    if not ok:
        return CortexOUT.error(result, code="RENDER_ERROR")

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
    ok, msg = setup_plantuml(force=force)
    if ok:
        return CortexOUT.work(msg, installed=True)
    return CortexOUT.error(msg, code="SETUP_FAILED")
