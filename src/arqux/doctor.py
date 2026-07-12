"""arqux doctor — workspace/project health diagnostics (BLP-007)."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from .constants import ARQUX_DIR, BRAIN_CORTEX, META_BRAIN_CORTEX, PRODUCT_NAME
from .cortex_out import CortexOUT
from .state import find_project_root, find_workspace_root

ContextType = Literal["workspace", "project", "unknown"]


def detect_context(path: str | None = None) -> ContextType:
    """Detect whether we're in a workspace root, project, or unknown."""
    cursor = Path(path or os.getcwd()).resolve()
    # Walk up looking for .arqux/
    while True:
        arqux_dir = cursor / ARQUX_DIR
        if arqux_dir.is_dir():
            meta_brain = arqux_dir / META_BRAIN_CORTEX
            brain = arqux_dir / BRAIN_CORTEX
            has_meta = meta_brain.exists()
            has_brain = brain.exists()
            if has_meta and not has_brain:
                return "workspace"
            if has_brain:
                return "project"
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    return "unknown"


@dataclass
class CheckResult:
    name: str
    status: Literal["pass", "fail", "warn"]
    message: str
    detail: str = ""
    fixable: bool = False
    context: Literal["workspace", "project", "both"] = "both"


def _handler_count() -> int:
    """Return the number of registered handlers."""
    try:
        from .handlers import REGISTRY
        return len(REGISTRY)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Workspace checks
# ---------------------------------------------------------------------------


def check_meta_brain_integrity(arqux_dir: Path) -> CheckResult:
    """Verify meta-brain.cortex exists and is parseable."""
    meta_brain = arqux_dir / META_BRAIN_CORTEX
    if not meta_brain.exists():
        return CheckResult(
            name="meta-brain.cortex",
            status="fail",
            message="meta-brain.cortex not found",
            fixable=False,
            context="workspace",
        )
    try:
        content = meta_brain.read_text(encoding="utf-8")
        if "$0" not in content:
            return CheckResult(
                name="meta-brain.cortex",
                status="fail",
                message="meta-brain.cortex missing $0 section",
                fixable=False,
                context="workspace",
            )
        return CheckResult(
            name="meta-brain.cortex",
            status="pass",
            message=f"meta-brain.cortex ok ({len(content)} bytes)",
            context="workspace",
        )
    except Exception as exc:
        return CheckResult(
            name="meta-brain.cortex",
            status="fail",
            message=f"meta-brain.cortex read error: {exc}",
            fixable=False,
            context="workspace",
        )


def check_metadata_section(arqux_dir: Path) -> CheckResult:
    """Verify .cortex files use $19 (not $0.1) for ARQUX METADATA.

    Checks brain.cortex and meta-brain.cortex for the correct
    metadata section identifier. $0.1 was deprecated (causes E033
    in codec-cortex 0.5.0+). All files must use $19.
    """
    cortex_files = [
        ("meta-brain.cortex", arqux_dir / META_BRAIN_CORTEX, "workspace"),
        ("brain.cortex", arqux_dir / BRAIN_CORTEX, "project"),
    ]
    issues: list[str] = []
    for name, path, ctx in cortex_files:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
            if "$0.1:" in text or "$0.1 " in text:
                issues.append(f"{name} uses $0.1 (should be $19)")
        except Exception:
            issues.append(f"{name} unreadable")

    if issues:
        return CheckResult(
            name="metadata-section",
            status="fail",
            message="; ".join(issues),
            fixable=False,
            context="both",
        )
    return CheckResult(
        name="metadata-section",
        status="pass",
        message="All .cortex files use $19 for ARQUX METADATA",
        context="both",
    )


def check_bak_files(arqux_dir: Path) -> CheckResult:
    """Check for .bak files in git."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True, text=True, timeout=10,
            cwd=arqux_dir.parent,
        )
        bak_files = [f for f in result.stdout.splitlines() if ".bak" in f]
        if bak_files:
            return CheckResult(
                name=".bak files in git",
                status="fail",
                message=f"{len(bak_files)} .bak file(s) tracked",
                detail=", ".join(bak_files[:5]),
                fixable=True,
                context="workspace",
            )
        return CheckResult(
            name=".bak files in git",
            status="pass",
            message="No .bak files tracked",
            context="workspace",
        )
    except Exception as exc:
        return CheckResult(
            name=".bak files in git",
            status="warn",
            message=f"Could not check .bak files: {exc}",
            context="workspace",
        )


# ---------------------------------------------------------------------------
# Project checks
# ---------------------------------------------------------------------------


def check_brain_integrity(arqux_dir: Path) -> CheckResult:
    """Verify brain.cortex exists and is parseable."""
    brain = arqux_dir / BRAIN_CORTEX
    if not brain.exists():
        return CheckResult(
            name="brain.cortex",
            status="fail",
            message="brain.cortex not found",
            fixable=False,
            context="project",
        )
    try:
        content = brain.read_text(encoding="utf-8")
        if "$0" not in content:
            return CheckResult(
                name="brain.cortex",
                status="fail",
                message="brain.cortex missing $0 section",
                fixable=False,
                context="project",
            )
        return CheckResult(
            name="brain.cortex",
            status="pass",
            message=f"brain.cortex ok ({len(content)} bytes)",
            context="project",
        )
    except Exception as exc:
        return CheckResult(
            name="brain.cortex",
            status="fail",
            message=f"brain.cortex read error: {exc}",
            fixable=False,
            context="project",
        )


def check_readme_badge(arqux_dir: Path) -> CheckResult:
    """Check if README handler badge matches actual count."""
    readme = arqux_dir.parent / "README.md"
    if not readme.exists():
        return CheckResult(
            name="README badge",
            status="warn",
            message="README.md not found",
            context="project",
        )
    try:
        content = readme.read_text(encoding="utf-8")
        actual = _handler_count()
        m = re.search(r"MCP%20Handlers-(\d+)", content)
        if m:
            badge_count = int(m.group(1))
            if badge_count == actual:
                return CheckResult(
                    name="README badge",
                    status="pass",
                    message=f"Handler badge correct ({badge_count})",
                    context="project",
                )
            return CheckResult(
                name="README badge",
                status="fail",
                message=f"Badge shows {badge_count}, actual is {actual}",
                fixable=True,
                context="project",
            )
        return CheckResult(
            name="README badge",
            status="warn",
            message="No MCP Handlers badge found in README",
            context="project",
        )
    except Exception as exc:
        return CheckResult(
            name="README badge",
            status="warn",
            message=f"README check error: {exc}",
            context="project",
        )


# ---------------------------------------------------------------------------
# Context-agnostic checks
# ---------------------------------------------------------------------------


def check_arqux_dir_structure(arqux_dir: Path) -> CheckResult:
    """Verify .arqux/ has expected subdirectories."""
    expected_dirs = ["skills", "cycles", "identities", "templates"]
    present = [d for d in expected_dirs if (arqux_dir / d).is_dir()]
    missing = [d for d in expected_dirs if d not in present]
    if missing:
        return CheckResult(
            name=".arqux/ structure",
            status="warn",
            message=f"Missing: {', '.join(missing)}",
            detail=f"Present: {', '.join(present)}",
            context="both",
        )
    return CheckResult(
        name=".arqux/ structure",
        status="pass",
        message=f"All {len(expected_dirs)} expected dirs present",
        context="both",
    )


# ---------------------------------------------------------------------------
# Fix functions
# ---------------------------------------------------------------------------


def fix_bak_files(arqux_dir: Path) -> str:
    """Remove .bak files from git tracking."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True, text=True, timeout=10,
            cwd=arqux_dir.parent,
        )
        bak_files = [f for f in result.stdout.splitlines() if ".bak" in f]
        if not bak_files:
            return "No .bak files to fix"
        for f in bak_files:
            subprocess.run(["git", "rm", f], capture_output=True, cwd=arqux_dir.parent)
        gitignore = arqux_dir.parent / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            if "*.bak" not in content:
                with gitignore.open("a", encoding="utf-8") as fh:
                    fh.write("\n# Backup files\n*.bak\n*.bak-*\n")
        return f"Removed {len(bak_files)} .bak file(s) from git"
    except Exception as exc:
        return f"Fix failed: {exc}"


def fix_readme_badge(arqux_dir: Path) -> str:
    """Update the README handler badge to match actual count."""
    readme = arqux_dir.parent / "README.md"
    if not readme.exists():
        return "README.md not found"
    try:
        content = readme.read_text(encoding="utf-8")
        actual = _handler_count()
        content = re.sub(
            r"MCP%20Handlers-\d+",
            f"MCP%20Handlers-{actual}",
            content,
        )
        readme.write_text(content, encoding="utf-8")
        return f"README badge updated to {actual}"
    except Exception as exc:
        return f"Fix failed: {exc}"


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

FixMap = dict[str, Callable[[Path], str]]


def run_all(path: str | None = None, fix: bool = False) -> CortexOUT:
    """Run all relevant checks and optionally apply fixes.

    Returns:
        CortexOUT with check results and fix report.
    """
    ctx = detect_context(path)
    arqux_dir: Path | None = None

    if ctx == "workspace":
        ws = find_workspace_root(start=path)
        if ws:
            arqux_dir = ws
    elif ctx == "project":
        pr = find_project_root(start=path)
        if pr:
            arqux_dir = pr

    if ctx == "unknown" or arqux_dir is None:
        return CortexOUT.error(
            f"No {PRODUCT_NAME} governance found",
            code="NOT_FOUND",
            context=ctx,
        )

    # Build check list based on context
    checks: list[CheckResult] = []
    fixes: FixMap = {}

    # Context-agnostic checks
    checks.append(check_arqux_dir_structure(arqux_dir))
    checks.append(check_metadata_section(arqux_dir))

    if ctx == "workspace":
        checks.append(check_meta_brain_integrity(arqux_dir))
        checks.append(check_bak_files(arqux_dir))
        fixes["fix_bak_files"] = fix_bak_files
    elif ctx == "project":
        checks.append(check_brain_integrity(arqux_dir))
        checks.append(check_bak_files(arqux_dir))
        checks.append(check_readme_badge(arqux_dir))
        fixes["fix_bak_files"] = fix_bak_files
        fixes["fix_readme_badge"] = fix_readme_badge

    # Apply fixes if requested
    fix_results: list[str] = []
    if fix:
        for name, fn in fixes.items():
            fix_results.append(fn(arqux_dir))

    passed = sum(1 for c in checks if c.status == "pass")
    failed = sum(1 for c in checks if c.status == "fail")
    warned = sum(1 for c in checks if c.status == "warn")

    # Build output fields
    fields = {
        "context": ctx,
        "checks": len(checks),
        "passed": passed,
        "failed": failed,
        "warned": warned,
    }
    if fix_results:
        fields["fixes"] = fix_results

    detail_lines = [
        f"  [{'✅' if c.status == 'pass' else '❌' if c.status == 'fail' else '⚠️'}] {c.name}: {c.message}"
        for c in checks
    ]
    detail = "\n".join(detail_lines)

    return CortexOUT.work(
        f"{PRODUCT_NAME} doctor: {len(checks)} checks ({passed} passed, {failed} failed, {warned} warned)",
        **fields,
        detail=detail,
    )
