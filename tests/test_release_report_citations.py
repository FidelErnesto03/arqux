"""Every artifact the release report cites must exist.

`docs/release/0.9.0-report.md` exists to make each claim traceable to an
artifact (§7.1 / R-14: "Cada condición del gate cita su artefacto; sin
artefacto, la condición no está cumplida"). That property only holds if the
citations are checked.

On 2026-10-11 a citation was added to the report naming
`src/arqux/core/state/_cycle.py`, a path that never existed — written to fill
a table cell without checking it. This suite is the check that was missing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "release" / "0.9.0-report.md"

# src/..., tests/..., docs/..., scripts/... — including brace groups and globs.
_CITATION = re.compile(
    r"(?<![\w/])((?:src|tests|docs|scripts)/[A-Za-z0-9_.*{},/-]+)"
)


def _expand(pattern: str) -> list[str]:
    """Expand ``a/{x,y}.py`` into its concrete paths."""
    match = re.search(r"\{([^{}]+)\}", pattern)
    if not match:
        return [pattern]
    expanded: list[str] = []
    for alternative in match.group(1).split(","):
        alternative = alternative.strip()
        head, tail = pattern[: match.start()], pattern[match.end() :]
        expanded.extend(_expand(head + alternative + tail))
    return expanded


def _citations() -> list[str]:
    text = REPORT.read_text(encoding="utf-8")
    paths: set[str] = set()
    for raw in _CITATION.findall(text):
        paths.update(_expand(raw))
    return sorted(paths)


def test_report_exists() -> None:
    assert REPORT.is_file(), f"release report missing at {REPORT}"


def test_benchmark_does_not_rewrite_release_evidence_on_a_plain_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Measuring must never publish; only an explicit request may.

    The benchmark used to write `docs/release/benchmark-*.json` on every run,
    so `pytest tests/benchmarks` silently replaced versioned release evidence
    with timings from whatever machine ran it.
    """
    monkeypatch.delenv("BENCHMARK_PUBLISH", raising=False)

    class Config:
        def getoption(self, _name: str, default: object = None) -> object:
            return default

    from tests.benchmarks.test_memory_benchmark import _should_publish

    assert _should_publish(Config()) is False, (
        "a plain test run must not publish benchmark evidence"
    )

    monkeypatch.setenv("BENCHMARK_PUBLISH", "1")
    assert _should_publish(Config()) is True

    # And the env switch must survive the autouse _clean_env fixture, which
    # strips every ARQUX_* variable. An ARQUX_-prefixed name was erased before
    # the test could read it, which made the switch look inert.
    assert not "BENCHMARK_PUBLISH".startswith("ARQUX_")


def test_report_cites_at_least_twenty_artifacts() -> None:
    """A guard on the guard: an empty scan proves nothing."""
    citations = _citations()
    assert len(citations) >= 20, (
        f"only {len(citations)} artifact paths found in the report — the "
        f"citation extractor is probably broken"
    )


def test_every_cited_artifact_exists() -> None:
    missing = []
    for citation in _citations():
        if "*" in citation:
            if not list(ROOT.glob(citation)):
                missing.append(citation)
        elif not (ROOT / citation).exists():
            missing.append(citation)
    assert not missing, (
        "the release report cites artifacts that do not exist. R-14 says a "
        f"condition without an artifact is not a satisfied condition: {missing}"
    )


def _done_blueprints(cycle_dir: Path) -> list[str]:
    """Blueprints of the cycle that actually shipped.

    A ``cancelled`` (or ``draft``) blueprint is not part of what the release
    shipped, so the report is under no obligation to cite it. Requiring every
    ``BLP-*.md`` file meant a legitimate ``cancelled`` entry turned the check
    red — the report was right and the check was wrong.
    """
    done: list[str] = []
    for path in sorted(cycle_dir.glob("BLP-*.md")):
        head = path.read_text(encoding="utf-8").split("\n---", 1)[0]
        match = re.search(r'^status:\s*"?([a-z_]+)"?', head, re.MULTILINE)
        if match and match.group(1) == "done":
            done.append(path.stem)
    return done


def test_report_cites_every_blueprint_of_the_closed_cycle() -> None:
    """CYCLE-13 closed 6/6; the report table must not silently show fewer.

    BLP-005 and BLP-006 finished after the report was first issued, and the
    table listed only four. Listing the cycle's real state is the point of
    the table; leaving it at four understated what shipped.
    """
    text = REPORT.read_text(encoding="utf-8")
    cycle_dir = ROOT / ".arqux" / "cycles" / "CYCLE-13" / "blueprints"
    if not cycle_dir.is_dir():
        # Governance tree absent in a CI checkout — nothing to compare against.
        return
    blueprints = _done_blueprints(cycle_dir)
    assert blueprints, "no done blueprints found under CYCLE-13"
    uncited = [b for b in blueprints if b not in text]
    assert not uncited, (
        f"the release report does not mention {uncited}, but CYCLE-13 closed "
        f"with {len(blueprints)} done blueprints. State the cycle's real content."
    )
