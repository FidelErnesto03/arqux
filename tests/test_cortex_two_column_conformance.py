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
CODEC_ROOT = Path(os.environ.get("CODEC_ROOT", "/home/vatrox/workspace/CODEC-CORTEX"))
CORPUS = CODEC_ROOT / "conformance" / "corpus"

COLUMN_A_PATH = os.environ.get(
    "CODEC_062_PATH",
    "/home/vatrox/workspace/UTILS/codec-cortex-legacy/codec-cortex-legacy/src",
)
COLUMN_B_PATH = os.environ.get("CODEC_RC1_PATH", str(CODEC_ROOT))

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
            f"PYTHONPATH={codec_path}\n{proc.stderr[-600:]}"
        )
    return json.loads(payloads[-1])


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def test_corpus_is_present() -> None:
    """The governed corpus must exist, or the rest of this file proves nothing."""
    assert CORPUS.is_dir(), f"canonical corpus not found at {CORPUS}"
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
    """Document the pin-versus-reality gap instead of asserting it away.

    ``pyproject.toml`` declares ``codec-cortex==1.0.0rc1`` while the
    installed engine is 0.6.2. This test records which column the suite
    really exercises so the discrepancy cannot be forgotten.
    """
    pinned = "codec-cortex==1.0.0rc1" in (REPO_ROOT / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert pinned, "the declared pin changed; update §4 and re-check the frontier"

    fallback_present = Path(COLUMN_A_PATH).is_dir()
    assert fallback_present, f"fallback column not found at {COLUMN_A_PATH}"

    # The suite imports column A, so the candidate column is only covered
    # by the isolated subprocesses above — never by the ordinary import.
    result = subprocess.run(
        [sys.executable, "-c", "import cortex.core.parser as p; print(p.__file__)"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": COLUMN_A_PATH},
    )
    assert result.returncode == 0, result.stderr[-300:]
    assert "codec-cortex-legacy" in result.stdout, (
        f"the default import resolved elsewhere: {result.stdout.strip()}"
    )
