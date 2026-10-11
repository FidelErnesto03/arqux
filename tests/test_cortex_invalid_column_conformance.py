"""Invalid-column conformance of ArqUX against the canonical CODEC-CORTEX corpus.

BLP-001 T-3.2 / CA-02. The two-column suite above proves read, write and
roundtrip on the *valid* fixtures. This file measures the *invalid* column:
the diagnostic behaviour each engine exhibits on fixtures the manifest marks
as invalid, compared against the ``requiredCodes`` the manifest declares.

Three sources are measured, each in the isolation it needs:

* **REF** — the reference validator ``CODEC-CORTEX/tools/cortex01_validator.py``,
  loaded straight from its file (it imports only the standard library).
* **A** — the fallback engine, codec-cortex 0.6.2, package ``cortex``.
* **B** — the candidate engine, codec-cortex 1.0.0-rc.1, package ``codec_cortex``.

The manifest's ``requiredCodes`` are the *specification* of what each invalid
fixture should emit; the engines are the *implementations* under measurement.
This suite records the measured frontier — it does not assert that any engine
fully implements the CORTEX 0.1 diagnostic contract. The engines are external
dependencies; ArqUX measures and documents them, it does not modify them.

The reference validator is measured as a third implementation. It is also
checked against the *valid* corpus: a validator that cannot accept the valid
fixtures is not a usable oracle, and that fact is recorded as a finding.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_MISSING_COLUMNS = (
    "Las columnas de conformance no estan disponibles. Se obtienen con:\n"
    "    python scripts/fetch_conformance_columns.py --dest <dir>\n"
    "que clona codec-cortex en dos refs pineados, verifica el sha256 del "
    "manifest del corpus y exporta CODEC_ROOT, CODEC_062_PATH y "
    "CODEC_RC1_PATH. Antes de 2026-10-11 estos defaults apuntaban a rutas "
    "absolutas bajo /home/vatrox/workspace, por lo que la suite solo podia "
    "correr en una maquina."
)


def _resolve(env_var: str, local_default: str) -> Path:
    value = os.environ.get(env_var)
    if value:
        return Path(value)
    default = Path(local_default)
    return default if default.exists() else Path(f"/nonexistent/{env_var}")


CODEC_ROOT = _resolve("CODEC_ROOT", "/home/vatrox/workspace/CODEC-CORTEX")
CORPUS = CODEC_ROOT / "conformance" / "corpus"
MANIFEST = CORPUS / "manifest.json"
TOOLS_PATH = CODEC_ROOT / "tools"

COLUMN_A_PATH = _resolve(
    "CODEC_062_PATH",
    "/home/vatrox/workspace/UTILS/codec-cortex-legacy/codec-cortex-legacy/src",
)
COLUMN_B_PATH = _resolve("CODEC_RC1_PATH", str(CODEC_ROOT))

REPORT_PATH = Path(
    os.environ.get(
        "CORTEX_INVALID_REPORT",
        str(REPO_ROOT / "docs" / "conformance" / "invalid-column-report.json"),
    )
)

# column id -> (human label, path that must be importable for its engine)
COLUMNS = {
    "REF": ("reference validator", TOOLS_PATH),
    "A": ("fallback 0.6.2", COLUMN_A_PATH),
    "B": ("candidate 1.0.0-rc.1", COLUMN_B_PATH),
}

# Runs in its own process so column A (``cortex``) and column B
# (``codec_cortex``) can never shadow one another — the same isolation the
# valid-column suite uses, so one engine cannot report for two columns.
_ENGINE_WORKER = r"""
import json, sys
from pathlib import Path

column, corpus, manifest_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

if column == "A":
    from cortex.core.parser import parse_cortex
else:
    from codec_cortex.dispatcher import parse_cortex

results = []
for case in manifest["invalid"]:
    source = (corpus / case["source"]).read_text(encoding="utf-8")
    try:
        parse_cortex(source)
        outcome, codes = "ACCEPTED", []
    except Exception as exc:
        outcome, codes = "REJECTED", [getattr(exc, "code", type(exc).__name__)]
    results.append({
        "id": case["id"],
        "required": case["requiredCodes"],
        "outcome": outcome,
        "codes": codes,
        "matched": sorted(set(case["requiredCodes"]) & set(codes)),
    })
print("\n".join(json.dumps(r, ensure_ascii=False) for r in results))
"""


def _load_reference_validator():
    """Load ``cortex01_validator.py`` by path, without touching sys.path."""
    spec = importlib.util.spec_from_file_location(
        "cortex01_validator", TOOLS_PATH / "cortex01_validator.py"
    )
    module = importlib.util.module_from_spec(spec)
    # Register before exec_module: the module defines @dataclass types,
    # whose __post_init__ resolution needs the module present in
    # sys.modules, or dataclasses.py raises AttributeError on None.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _measure_reference_validator() -> list[dict]:
    """Measure the reference validator on every invalid fixture, in-process."""
    validator = _load_reference_validator()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    results = []
    for case in manifest["invalid"]:
        source = (CORPUS / case["source"]).read_text(encoding="utf-8")
        _, diagnostics = validator.parse_document(source)
        codes = [d["code"] for d in diagnostics]
        results.append({
            "id": case["id"],
            "required": case["requiredCodes"],
            "outcome": "ACCEPTED" if not codes else "REJECTED",
            "codes": codes,
            "matched": sorted(set(case["requiredCodes"]) & set(codes)),
        })
    return results


def _run_engine_column(column: str, codec_path: Path) -> list[dict]:
    """Run one engine column against the invalid corpus in a subprocess."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(codec_path)
    proc = subprocess.run(
        [sys.executable, "-c", _ENGINE_WORKER, column, str(CORPUS), str(MANIFEST)],
        capture_output=True,
        text=True,
        env=env,
    )
    lines = [line for line in proc.stdout.splitlines() if line.startswith("{")]
    if not lines:
        pytest.fail(
            f"column {column} produced no result — engine failed to import.\n"
            f"PYTHONPATH={codec_path}\n{proc.stderr[-600:]}\n\n{_MISSING_COLUMNS}"
        )
    return [json.loads(line) for line in lines]


def _summary(results: list[dict]) -> dict:
    total = len(results)
    matched = sum(1 for r in results if set(r["required"]) <= set(r["codes"]))
    accepted = sum(1 for r in results if r["outcome"] == "ACCEPTED")
    return {
        "total": total,
        "required_codes_fully_matched": matched,
        "invalid_fixtures_accepted": accepted,
    }


def _reference_validator_self_conformance() -> dict:
    """A validator that rejects valid fixtures is not a usable oracle."""
    validator = _load_reference_validator()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    accepted, rejected = 0, []
    for case in manifest["valid"]:
        source = (CORPUS / case["source"]).read_text(encoding="utf-8")
        _, diagnostics = validator.parse_document(source)
        if diagnostics:
            rejected.append(
                {"id": case["id"], "codes": [d["code"] for d in diagnostics]}
            )
        else:
            accepted += 1
    return {
        "valid_total": len(manifest["valid"]),
        "valid_accepted": accepted,
        "valid_rejected": rejected,
    }


@pytest.fixture(scope="module")
def manifest_cases() -> list[dict]:
    if not MANIFEST.is_file():
        pytest.fail(
            f"corpus manifest not found at {MANIFEST}\n\n{_MISSING_COLUMNS}"
        )
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return manifest["invalid"]


@pytest.fixture(scope="module")
def results(manifest_cases) -> dict[str, list[dict]]:
    """Measure all three columns once and write the conformance report."""
    measured = {
        "REF": _measure_reference_validator(),
        "A": _run_engine_column("A", COLUMN_A_PATH),
        "B": _run_engine_column("B", COLUMN_B_PATH),
    }
    for column, cases in measured.items():
        assert len(cases) == len(manifest_cases), (
            f"column {column} measured {len(cases)} of {len(manifest_cases)} cases"
        )

    report = {
        "generated_by": "tests/test_cortex_invalid_column_conformance.py",
        "corpus": str(CORPUS),
        "required_codes_are": "specification (what each invalid fixture should emit)",
        "columns": {
            column: {
                "label": label,
                "summary": _summary(cases),
                "per_case": cases,
            }
            for column, (label, _) in COLUMNS.items()
            for cases in [measured[column]]
        },
        "reference_validator_self_conformance": _reference_validator_self_conformance(),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return measured


# ---------------------------------------------------------------------------
# Structural invariants — what the suite is responsible for verifying
# ---------------------------------------------------------------------------


def test_manifest_declares_required_codes_for_every_invalid_case(manifest_cases) -> None:
    """The specification is incomplete without a required code per case."""
    assert len(manifest_cases) > 0
    for case in manifest_cases:
        assert case.get("requiredCodes"), f"{case['id']} declares no requiredCodes"


@pytest.mark.parametrize("column", list(COLUMNS))
def test_every_column_measures_every_invalid_case(column, manifest_cases, results) -> None:
    """A column that silently skips fixtures is covering less ground."""
    assert len(results[column]) == len(manifest_cases)
    assert {r["id"] for r in results[column]} == {c["id"] for c in manifest_cases}


def test_reference_validator_rejects_every_invalid_fixture(results) -> None:
    """The reference validator must emit a diagnostic for each invalid fixture."""
    for case in results["REF"]:
        assert case["outcome"] == "REJECTED", (
            f"reference validator accepted invalid fixture {case['id']}"
        )
        assert case["codes"], f"reference validator emitted no code for {case['id']}"


def test_measurement_is_deterministic(manifest_cases) -> None:
    """Conformance is only evidence if re-running it reproduces the result."""
    reference_first = _measure_reference_validator()
    reference_second = _measure_reference_validator()
    assert reference_first == reference_second, "reference validator is not deterministic"

    for column, (_, codec_path) in COLUMNS.items():
        if column == "REF":
            continue
        first = _run_engine_column(column, codec_path)
        second = _run_engine_column(column, codec_path)
        assert first == second, f"column {column} is not deterministic"


def test_conformance_report_is_written(results) -> None:
    """The measured frontier is a durable artifact, not a transient print."""
    assert REPORT_PATH.is_file(), f"conformance report not written to {REPORT_PATH}"
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    for column in COLUMNS:
        assert column in report["columns"], f"report missing column {column}"
        assert report["columns"][column]["summary"]["total"] > 0


def test_reference_validator_self_conformance_is_recorded(results) -> None:
    """Record whether the reference validator accepts the valid corpus.

    This is a finding, not a pass/fail gate: the validator's section-header
    grammar (``$N: title`` with a space) is incompatible with the canonical
    corpus (``$N:Title`` without a space), so it rejects valid fixtures and
    cannot serve as a reliable oracle. The fact is recorded in the report so
    the diagnostic column is interpreted with it in view.
    """
    self_conf = _reference_validator_self_conformance()
    assert self_conf["valid_total"] > 0
    # The finding is structural and is recorded verbatim in the report.
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    assert report["reference_validator_self_conformance"] == self_conf
