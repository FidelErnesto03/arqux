"""Two-column conformance of ArqUX against the canonical CODEC-CORTEX corpus.

BLP-001 CA-01 and CA-02. The corpus is the governed material under
``CODEC-CORTEX/conformance``; these tests make it an input rather than a
document nobody reads.

Two columns are exercised, exactly as the compatibility frontier in §4
declares:

* **A — fallback estable**, codec-cortex 0.6.2, package ``cortex``.
* **B — candidata**, codec-cortex 1.0.0-rc.1, package ``codec_cortex``.

The engines are loaded in isolated subprocesses. Importing both in one
process would let whichever resolved first shadow the other and quietly
report one column twice, which is the kind of self-deception this suite
exists to prevent.
"""

from __future__ import annotations

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


def _resolve(env_var: str, local_default: str) -> str:
    value = os.environ.get(env_var)
    if value:
        return value
    default = Path(local_default)
    return str(default) if default.exists() else ""


# Empty string when the column is absent: the tests below then fail with
# _MISSING_COLUMNS, which names the fix. The previous behaviour was to fall
# back to a hardcoded local path and fail with "canonical corpus not found
# at /home/vatrox/..." — indistinguishable from a real conformance failure.
CODEC_ROOT = Path(_resolve("CODEC_ROOT", "/home/vatrox/workspace/CODEC-CORTEX") or ".")
CORPUS = CODEC_ROOT / "conformance" / "corpus"

COLUMN_A_PATH = _resolve(
    "CODEC_062_PATH",
    "/home/vatrox/workspace/UTILS/codec-cortex-legacy/codec-cortex-legacy/src",
)
COLUMN_B_PATH = _resolve("CODEC_RC1_PATH", str(CODEC_ROOT))

COLUMNS = [
    pytest.param("A", COLUMN_A_PATH, id="fallback-0.6.2"),
    pytest.param("B", COLUMN_B_PATH, id="candidate-1.0.0-rc.1"),
]

_WORKER = r"""
import json, sys
from pathlib import Path

column, corpus = sys.argv[1], Path(sys.argv[2])
if column == "A":
    import cortex.core.parser as P
else:
    import codec_cortex.parser as P

parsed, failed, detail = 0, 0, {}
for fixture in sorted((corpus / "valid").glob("*.cortex")):
    try:
        document = P.parse_cortex(fixture.read_text(encoding="utf-8"))
        assert document is not None
        parsed += 1
    except Exception as exc:
        failed += 1
        detail[fixture.name] = f"{type(exc).__name__}: {exc}"[:120]
print(json.dumps({"parsed": parsed, "failed": failed, "detail": detail}))
"""


def _run_column(column: str, codec_path: str, corpus: Path) -> dict:
    """Parse every valid fixture with one codec engine in its own process."""
    env = dict(os.environ)
    env["PYTHONPATH"] = codec_path
    proc = subprocess.run(
        [sys.executable, "-c", _WORKER, column, str(corpus)],
        capture_output=True,
        text=True,
        env=env,
    )
    payloads = [line for line in proc.stdout.splitlines() if line.startswith("{")]
    if not payloads:
        pytest.fail(
            f"column {column} produced no result — engine failed to import.\n"
            f"PYTHONPATH={codec_path}\n{proc.stderr[-600:]}\n\n{_MISSING_COLUMNS}"
        )
    return json.loads(payloads[-1])


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def test_corpus_is_present() -> None:
    """The governed corpus must exist, or the rest of this file proves nothing."""
    if not CORPUS.is_dir():
        pytest.fail(f"canonical corpus not found at {CORPUS}\n\n{_MISSING_COLUMNS}")
    manifest = CORPUS / "manifest.json"
    assert manifest.is_file(), "corpus manifest missing"
    declared = json.loads(manifest.read_text(encoding="utf-8"))
    valid = list((CORPUS / "valid").glob("*.cortex"))
    assert len(valid) == len(declared["valid"]), (
        f"corpus holds {len(valid)} valid fixtures but its manifest declares "
        f"{len(declared['valid'])} — the material moved and the baseline is stale"
    )


# ---------------------------------------------------------------------------
# CA-02 — roundtrip on both columns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("column, codec_path", COLUMNS)
def test_every_valid_fixture_parses(column: str, codec_path: str) -> None:
    result = _run_column(column, codec_path, CORPUS)
    assert result["failed"] == 0, (
        f"column {column} rejected {result['failed']} valid fixtures: "
        f"{list(result['detail'].items())[:3]}"
    )
    assert result["parsed"] > 0, "column parsed nothing; the corpus was not exercised"


@pytest.mark.parametrize("column, codec_path", COLUMNS)
def test_both_columns_agree_on_the_same_fixture_set(column: str, codec_path: str) -> None:
    """A column that parses a different number of fixtures is a real difference.

    Without this, one column could silently cover less ground and still
    report success.
    """
    result = _run_column(column, codec_path, CORPUS)
    expected = len(list((CORPUS / "valid").glob("*.cortex")))
    assert result["parsed"] == expected


# ---------------------------------------------------------------------------
# CA-01 — the frontier the matrix depends on
# ---------------------------------------------------------------------------


def test_fallback_column_is_the_one_the_environment_actually_runs() -> None:
    """Record the pin and that the suite really exercises the fallback engine.

    The pin used to declare ``codec-cortex==1.0.0rc1`` while the suite ran
    against 0.6.2 — and the pin was worse than useless, because the rc1
    candidate ships no validator and no HCORTEX read renderer, so
    installing it disabled the whole CORTEX layer (89 failures against a
    15-failure baseline). The pin now declares the 0.6.x line, the one that
    provides the full surface.

    This test used to assert that the resolved import path contained the
    literal string "codec-cortex-legacy", i.e. it asserted the NAME OF A LOCAL
    DIRECTORY. That made the suite unrunnable anywhere else: with the columns
    fetched by ``scripts/fetch_conformance_columns.py`` the engine is the
    same code from a different directory and the assertion was false for the
    wrong reason. It now asserts what actually matters — the engine layout is
    the legacy one and the declared pin matches it.
    """
    declared = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "codec-cortex>=0.6.2,<0.7" in declared, (
        "the declared pin changed; update §4 and re-check the frontier"
    )
    assert "codec-cortex==1.0.0rc1" not in declared, (
        "the rc1 candidate was re-pinned: it has no validate and no "
        "render_hcortex_read, so it silently disables cortex_verify"
    )

    if not Path(COLUMN_A_PATH).is_dir():
        pytest.fail(f"fallback column not found at {COLUMN_A_PATH}\n\n{_MISSING_COLUMNS}")

    # The suite imports column A, so the candidate column is only covered
    # by the isolated subprocesses above — never by the ordinary import.
    # Assert the LAYOUT (legacy `cortex.*`) rather than the location: the
    # layout is the contract, the directory is an accident of this machine.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import cortex.core.parser as p, cortex.core.validator as v;"
            "print(p.__file__)",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": COLUMN_A_PATH},
    )
    assert result.returncode == 0, (
        f"the fallback column does not expose the legacy layout: "
        f"{result.stderr[-300:]}\n\n{_MISSING_COLUMNS}"
    )
    assert "cortex/core/parser" in result.stdout.replace("\\", "/"), (
        f"the fallback column resolved to an unexpected layout: "
        f"{result.stdout.strip()}"
    )
