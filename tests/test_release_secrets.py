"""BLP-004 L-SEC-02 / R-07: no secrets in release artifacts.

The secret check is a blocking entrance condition to the release gate, not an
informative report (§7.5): a finding stops the release and is filed as an
incident. This test scans the release artifacts (corpus report, release docs)
and fails loudly on any credential-shaped string.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = ROOT / "docs" / "release"

SECRET_PATTERNS = [
    re.compile(r"api[_-]?key\s*[:=]\s*\S", re.IGNORECASE),
    re.compile(r"secret\s*[:=]\s*\S", re.IGNORECASE),
    re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE),
    re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


def _release_files() -> list[Path]:
    if not RELEASE_DIR.is_dir():
        return []
    return [p for p in RELEASE_DIR.rglob("*") if p.suffix in {".json", ".md", ".txt"}]


def test_release_artifacts_carry_no_secrets() -> None:
    files = _release_files()
    assert files, "no release artifacts found to scan"
    offenders: dict[str, str] = {}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                offenders[path.name] = pattern.pattern
    assert not offenders, f"L-SEC-02 violation — release stopped: {offenders}"


def test_benchmark_corpus_is_synthetic() -> None:
    """L-SEC-02: the benchmark corpus is synthetic and secret-free."""
    import json

    report = RELEASE_DIR / "benchmark-0.9.0.json"
    assert report.is_file(), "benchmark report missing"
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["corpus"]["synthetic"] is True
    assert data["corpus"]["contains_secrets"] is False
