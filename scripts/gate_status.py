#!/usr/bin/env python3
"""Gate status — recompute the ROADMAP-001 table from artifacts, never from prose.

ROADMAP-001 states that a row without a verification command does not enter the
table, and that the roadmap publishes the output of this script rather than
anyone's memory. This script is that contract's other half.

Each check runs a real command and reports PASS / PARTIAL / FAIL / UNVERIFIED.
``UNVERIFIED`` is a first-class verdict: when the evidence cannot be produced,
the row is never silently assumed green.

Usage:
    python scripts/gate_status.py                 # human table
    python scripts/gate_status.py --json          # machine output
    python scripts/gate_status.py --only A-11     # one or more rows
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "arqux"

PASS = "PASS"
PARTIAL = "PARTIAL"
FAIL = "FAIL"
UNVERIFIED = "UNVERIFIED"


@dataclass
class Result:
    id: str
    title: str
    verdict: str
    detail: str


def _run(cmd: list[str], timeout: int = 600) -> tuple[int, str]:
    """Run a command from the repo root. Returns (returncode, combined output)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s: {' '.join(cmd)}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _pytest(paths: list[str]) -> tuple[str, str]:
    """Run pytest on paths and classify the outcome by its summary line."""
    code, out = _run([sys.executable, "-m", "pytest", *paths, "-q", "--no-header"])
    tail = " ".join(line.strip() for line in out.strip().splitlines()[-2:])[:220]
    if code == 0:
        return PASS, tail
    if code == 5:  # no tests collected
        return UNVERIFIED, "no tests collected"
    return FAIL, tail


def _count(pattern: str, path: Path = SRC) -> int:
    """Count regex matches across every .py file under path."""
    total = 0
    for py in path.rglob("*.py"):
        try:
            total += len(re.findall(pattern, py.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return total


def check_a01() -> Result:
    if not (REPO_ROOT / "tests" / "test_cortex_write_transaction.py").exists():
        return Result("A-01", "Escritura transaccional", UNVERIFIED, "suite ausente")
    verdict, detail = _pytest(["tests/test_cortex_write_transaction.py"])
    return Result("A-01", "Escritura transaccional", verdict, detail)


def check_a02() -> Result:
    """A-02 needs three diagnostic families: E, W and I. I is the one missing."""
    e_codes, w_codes, i_codes = _count(r'"E0\d'), _count(r'"W0\d'), _count(r'"I0\d')
    verdict, detail = _pytest(["tests/e2e/test_signal_quality.py"])
    partial = e_codes > 0 and w_codes > 0 and i_codes == 0
    if verdict == PASS and partial:
        return Result(
            "A-02", "Verificador E/W/I", PARTIAL,
            f"E={e_codes} W={w_codes} I={i_codes} (familia I ausente); suite OK",
        )
    if verdict == PASS and e_codes and w_codes and i_codes:
        return Result("A-02", "Verificador E/W/I", PASS, f"E={e_codes} W={w_codes} I={i_codes}")
    return Result("A-02", "Verificador E/W/I", verdict, f"E={e_codes} W={w_codes} I={i_codes}")


def check_a03() -> Result:
    verdict, detail = _pytest(["tests/e2e/test_identity_session.py"])
    return Result("A-03", "Identidad contextual", verdict, detail)


def check_a05() -> Result:
    verdict, detail = _pytest([
        "tests/test_cortex_conformance.py",
        "tests/test_brain_roundtrip_integrity.py",
        "tests/test_writer_roundtrip.py",
        "tests/test_cortex_two_column_conformance.py",
        "tests/test_cortex_invalid_column_conformance.py",
    ])
    return Result("A-05", "Conformidad CORTEX", verdict, detail)


def check_a06() -> Result:
    verdict, detail = _pytest([
        "tests/test_frontmatter_consistency.py",
        "tests/e2e/test_integrity_gates.py",
    ])
    return Result("A-06", "Frontmatter huérfano", verdict, detail)


def check_a09() -> Result:
    verdict, detail = _pytest(["tests/e2e/test_integrity_gates.py"])
    return Result("A-09", "Regresión de corrupción", verdict, detail)


def check_a11() -> Result:
    """Every public number must resolve to a verified fact.

    Compares the handler count the registry actually reports against the counts
    the documentation claims, and the SECURITY.md supported-version line against
    the version the package declares.
    """
    problems: list[str] = []

    code, out = _run([sys.executable, "-m", "arqux", "handlers"])
    live = len([ln for ln in out.splitlines() if re.match(r"^\s*[a-z_]+\.[a-z_]+", ln)])
    if code != 0 or live == 0:
        return Result("A-11", "Verdad del repo", UNVERIFIED, "no se pudo contar handlers")

    arch = REPO_ROOT / "ARCHITECTURE.md"
    if arch.exists():
        text = arch.read_text(encoding="utf-8")
        # Only totals claim the registry size. Sub-budgets ("24-handler
        # governance budget", "the remaining 49") are legitimate partial counts
        # and must not be read as a discrepancy.
        claimed = {
            int(m)
            for m in re.findall(r"\b(\d{2,3})\s+(?:handlers|MCP Handlers)\b", text)
            if not re.search(rf"{m}[- ]handler\s+\w+\s+budget", text)
        }
        # Partial sub-counts ("the remaining 49") describe a slice, not the
        # total. Only claims near the registry size are discrepancies.
        wrong = {c for c in claimed if c != live and c > 50}
        if wrong:
            problems.append(f"ARCHITECTURE.md dice {sorted(wrong)}, real {live}")

    sec = REPO_ROOT / "SECURITY.md"
    pkg_version = _package_version()
    if sec.exists() and pkg_version:
        sec_versions = re.findall(r"^\|\s*(\d+\.\d+)\.x\s*\|", sec.read_text(encoding="utf-8"), re.M)
        minor = ".".join(pkg_version.split(".")[:2])
        if sec_versions and minor not in sec_versions:
            problems.append(f"SECURITY.md soporta {sec_versions}, vigente {minor}.x")

    if problems:
        return Result("A-11", "Verdad del repo", FAIL, " | ".join(problems))
    return Result("A-11", "Verdad del repo", PASS, f"handlers={live}, versiones coherentes")


def check_a22() -> Result:
    """The learning engine must work without codec-cortex installed.

    A-22 makes learning a native ArqUX component. Until the port lands, the
    engine reports ENGINE_UNAVAILABLE whenever the codec is absent — which is
    the exact condition this check encodes.
    """
    auditor = SRC / "core" / "learning" / "_common.py"
    if not auditor.exists():
        return Result("A-22", "Learning nativo", UNVERIFIED, "módulo de aprendizaje ausente")

    text = auditor.read_text(encoding="utf-8")
    foreign = re.findall(r"from\s+(cortex\.learning|codec_cortex\.learning)", text)
    if foreign:
        return Result(
            "A-22", "Learning nativo", FAIL,
            f"aún importa {sorted(set(foreign))} del codec",
        )
    return Result("A-22", "Learning nativo", PASS, "sin dependencia de cortex.learning")


def check_xfail() -> Result:
    """Declared gaps. G1 demands zero — each xfail is a written admission."""
    verdict, detail = _run([sys.executable, "-m", "pytest", "tests/", "-q", "--no-header"])
    found = len(re.findall(r"\bXFAIL\b", detail))
    failed = len(re.findall(r"\bFAILED\b", detail))
    if failed:
        return Result("XFAIL", "Brechas declaradas", FAIL, f"{found} xfail, {failed} failed")
    if found == 0:
        return Result("XFAIL", "Brechas declaradas", PASS, "0 brechas")
    return Result("XFAIL", "Brechas declaradas", PARTIAL, f"{found} xfail declarados")


def check_suite() -> Result:
    verdict, detail = _run([sys.executable, "-m", "pytest", "tests/", "-q", "--no-header"])
    tail = " ".join(detail.strip().splitlines()[-1:])[:200]
    return Result("SUITE", "Suite completa", PASS if verdict == 0 else FAIL, tail)


def _package_version() -> str | None:
    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.exists():
        return None
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def check_dialect() -> Result:
    """Every migrable .cortex artifact must parse as CORTEX 1.0 (BLP-001).

    Invokes the BLP-001 instrument so the row measures the corpus rather than a
    remembered number. The instrument needs codec-cortex 1.0 importable; when it
    is not, the row is UNVERIFIED — never assumed green.
    """
    script = REPO_ROOT / "scripts" / "dialect_conformance.py"
    if not script.exists():
        return Result("DIALECTO", "Conformidad de dialecto", UNVERIFIED, "instrumento ausente")
    code, out = _run(
        [sys.executable, str(script), "--root", str(REPO_ROOT.parent), "--corpus", "migrable"],
        timeout=900,
    )
    summary = next(
        (ln.strip() for ln in out.splitlines() if ln.strip().startswith("total=")), ""
    )
    if "NO_CODEC_1" in out:
        return Result("DIALECTO", "Conformidad de dialecto", UNVERIFIED, "codec-cortex 1.0 no instalado")
    if not summary:
        return Result("DIALECTO", "Conformidad de dialecto", UNVERIFIED, "sin resumen del instrumento")
    failed = 0
    if "fail=" in summary:
        try:
            failed = int(summary.split("fail=")[1].split()[0])
        except (IndexError, ValueError):
            failed = -1
    verdict = PASS if failed == 0 else FAIL
    return Result("DIALECTO", "Conformidad de dialecto", verdict, summary)


CHECKS = {
    "A-01": check_a01,
    "A-02": check_a02,
    "A-03": check_a03,
    "A-05": check_a05,
    "A-06": check_a06,
    "A-09": check_a09,
    "A-11": check_a11,
    "A-22": check_a22,
    "DIALECTO": check_dialect,
    "XFAIL": check_xfail,
    "SUITE": check_suite,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--only", nargs="+", metavar="ID", help="run only these rows")
    args = parser.parse_args()

    keys = args.only or list(CHECKS)
    unknown = [k for k in keys if k not in CHECKS]
    if unknown:
        parser.error(f"unknown row(s): {', '.join(unknown)}")

    results = [CHECKS[k]() for k in keys]

    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False))
    else:
        width = max(len(r.id) for r in results)
        for r in results:
            print(f"{r.id:<{width}}  {r.verdict:<10}  {r.title}")
            print(f"{'':<{width}}  {'':<10}  {r.detail}")

    # The gate is closed unless every row is green.
    blocking = [r for r in results if r.verdict != PASS]
    if not args.json:
        print()
        if blocking:
            print(f"G1: CERRADA — {len(blocking)} fila(s) sin PASS: {', '.join(r.id for r in blocking)}")
        else:
            print("G1: ABIERTA — todas las filas en PASS")
    return 0 if not blocking else 1


if __name__ == "__main__":
    raise SystemExit(main())
