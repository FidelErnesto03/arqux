"""BLP-004 L-SEC-02 / R-07: no secrets in the repository or its release artifacts.

The secret check is a blocking entrance condition to the release gate, not an
informative report (§7.5): a finding stops the release and is filed as an
incident. BLP-004 §13 declares the scope as "artefactos, logs, corpora e
informe".

Two defects were fixed here on 2026-10-11:

1. **Scope.** The scan only walked `docs/release/**` (3 files) while §13
   declares artifacts, logs, corpora AND the report. Every `.cortex` file,
   `CHANGELOG.md`, `README.md` and all of `src/` were outside it. It now walks
   the whole versioned tree.

2. **Circular evidence.** `test_benchmark_corpus_is_synthetic` used to assert
   that `benchmark-0.9.0.json` said `synthetic: true` and
   `contains_secrets: false` — the artifact certifying its own virtue, which
   is no evidence at all. It now REGENERATES the corpus with the same function
   the benchmark uses, scans the generated text, and checks the report
   describes that corpus.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# High-confidence shapes: unambiguous credential material wherever it appears.
HIGH_CONFIDENCE = [
    re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
]

# Assignment of a credential-named field to a QUOTED LITERAL of real length.
#
# The previous patterns were `secret\s*[:=]\s*\S` and friends, which match any
# *reference* to a credential, not a credential: widened to the whole tree they
# flagged `api_key: str = ""`, `secret = os.environ.get("ARQUX_AGENT_SECRET", "")`
# and `export ARQUX_AGENT_SECRET=<hex-secret>`. Six files tripped on that, zero
# held a secret. A blocking control that fires on correct code is a control
# that gets switched off — which is how a scan of three files ended up being
# the whole of L-SEC-02.
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"""\b(api[_-]?key|secret|password|passwd|token|credential)s?\b["']?\s*[:=]\s*"""
    r"""(?P<quote>["'])(?P<value>[^"'\n]{6,})(?P=quote)""",
    re.IGNORECASE,
)

# Values that are obviously not secrets.
_PLACEHOLDERS = {
    "...",
    "***",
    "xxxxx",
    "changeme",
    "change-me",
    "placeholder",
    "example",
    "redacted",
    "hex-secret",
    "your-key-here",
    "none",
    "null",
    "undefined",
    "todo",
    "fixme",
}

# Substrings that mean the value is an indirection, not a literal.
_INDIRECTIONS = (
    "os.environ",
    "getenv",
    "config.",
    "options.",
    "settings.",
    "self.",
    "%s",
    "{",
    "}",
    "$(",
    "lambda",
    "Field(",
)


def _is_real_credential(value: str) -> bool:
    stripped = value.strip()
    if stripped.lower() in _PLACEHOLDERS:
        return False
    return not any(marker in stripped for marker in _INDIRECTIONS)


SECRET_PATTERNS = HIGH_CONFIDENCE

# Files that legitimately contain credential-shaped strings, each with the
# reason it is exempt. An exemption without a reason is a hole, so
# `test_every_exemption_states_a_reason` enforces that every entry has one.
#
# This is deliberately NOT a blanket allowlist: a file is exempt, never a
# pattern, and the reason is reviewed with the rest of the change.
EXEMPTIONS = {
    "tests/test_release_secrets.py": "defines the patterns used by this scanner",
    "tests/test_security.py": "defines credential-shaped fixtures for the security suite",
    "tests/test_security_hmac.py": (
        "HMAC fixtures need deterministic key material to assert on; the values "
        "are literals like 's3kr3t'/'hunter2' with no external validity"
    ),
    "tests/test_memory_model.py": (
        "the subject under test is sanitize_payload() excluding secrets, so a "
        "hardcoded api_key is the fixture, not a leak"
    ),
}

# Binary or generated-by-build trees: never release evidence, and scanning
# them only produces false positives from compiled artefacts.
SKIP_DIRS = {
    ".git", ".venv", ".venv-voice", "build", "dist", "node_modules",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache",
}

TEXT_SUFFIXES = {
    ".py", ".md", ".cortex", ".json", ".txt", ".toml", ".yml", ".yaml",
    ".cfg", ".ini", ".sh", ".cortex.md", "",
}


def _versioned_files() -> list[Path]:
    """Every file git tracks, minus build artefacts and virtualenvs."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        # No git (sdist install): fall back to a filesystem walk.
        return [
            p for p in ROOT.rglob("*")
            if p.is_file() and not (SKIP_DIRS & set(p.relative_to(ROOT).parts))
        ]
    files = []
    for raw in out.split("\0"):
        if not raw:
            continue
        rel = Path(raw)
        if SKIP_DIRS & set(rel.parts):
            continue
        files.append(ROOT / rel)
    return files


def _scan_text(text: str) -> list[str]:
    """Return the patterns that hit, plus any hardcoded credential literals."""
    hits = [p.pattern for p in HIGH_CONFIDENCE if p.search(text)]
    for match in _CREDENTIAL_ASSIGNMENT.finditer(text):
        if _is_real_credential(match.group("value")):
            hits.append(
                f"credential literal assigned to {match.group(1)!r}: "
                f"{match.group('value')[:24]!r}"
            )
    return hits


def _read_if_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw[:8192]:  # binary
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


# ---------------------------------------------------------------------------
# L-SEC-02 — the blocking scan
# ---------------------------------------------------------------------------


def test_no_secrets_anywhere_in_the_versioned_tree() -> None:
    """Every versioned text file, not just docs/release.

    Before 2026-10-11 this walked `docs/release/**` only — 3 files — while
    BLP-004 §13 declares "artefactos, logs, corpora e informe".
    """
    offenders: dict[str, list[str]] = {}
    scanned = 0
    for path in _versioned_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in EXEMPTIONS:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = _read_if_text(path)
        if text is None:
            continue
        scanned += 1
        hits = _scan_text(text)
        if hits:
            offenders[rel] = hits

    assert scanned > 100, (
        f"the scan only reached {scanned} files — the tree walk is broken, "
        f"and a scan that inspects nothing reports nothing"
    )
    assert not offenders, (
        f"L-SEC-02 violation — release stopped. {len(offenders)} file(s) "
        f"carry credential-shaped strings: {offenders}"
    )


def test_every_exemption_states_a_reason() -> None:
    """An exemption without a stated reason is a hole in the blocking gate."""
    for path, reason in EXEMPTIONS.items():
        assert reason and len(reason.strip()) > 20, (
            f"exemption for {path} needs a real justification"
        )
        assert (ROOT / path).is_file(), (
            f"exemption for {path} is stale: the file no longer exists, so the "
            f"allowlist is hiding nothing and hiding future risk"
        )


def test_the_scanner_actually_catches_a_planted_secret() -> None:
    """Guard the guard: a scanner that finds nothing must be proven capable.

    A blocking secret control is only worth its cost if a positive control
    proves it fires. This plants one of each shape in memory and asserts the
    scanner reports it, and plants the shapes that caused the six false
    positives to assert it stays quiet on them.
    """
    must_fire = {
        "github token": "token = 'ghp_" + "a" * 30,
        "private key": "-----BEGIN RSA PRIVATE KEY-----",
        "aws key": "AKIA" + "B" * 16,
        "openai key": "sk-" + "z" * 24,
        "hardcoded password": 'password = "correct-horse-battery"',
        "hardcoded api key": 'api_key = "abcd1234efgh5678"',
    }
    for label, sample in must_fire.items():
        assert _scan_text(sample), f"the scanner missed a {label}: {sample[:40]!r}"

    must_not_fire = {
        "type annotation": "api_key: str = \"\"",
        "env lookup": 'secret = os.environ.get("ARQUX_AGENT_SECRET", "")',
        "doc placeholder": "export ARQUX_AGENT_SECRET=<hex-secret>",
        "placeholder value": 'secret = "..."',
        "indirect config": 'api_key=str(options.get("api_key") or _env("K"))',
    }
    for label, sample in must_not_fire.items():
        assert not _scan_text(sample), (
            f"the scanner flagged correct code ({label}): {sample[:50]!r}. "
            f"A blocking control that cries wolf gets disabled."
        )


def test_release_artifacts_carry_no_secrets() -> None:
    """The original, narrower check, kept so the declared artifacts are
    explicitly covered even if the tree walk is ever narrowed again."""
    release_dir = ROOT / "docs" / "release"
    assert release_dir.is_dir(), "no release artifacts found to scan"
    files = [p for p in release_dir.rglob("*") if p.suffix in {".json", ".md", ".txt"}]
    assert files, "no release artifacts found to scan"
    offenders: dict[str, list[str]] = {}
    for path in files:
        hits = _scan_text(path.read_text(encoding="utf-8", errors="replace"))
        if hits:
            offenders[path.name] = hits
    assert not offenders, f"L-SEC-02 violation — release stopped: {offenders}"


# ---------------------------------------------------------------------------
# L-SEC-02 — the benchmark corpus, verified instead of self-declared
# ---------------------------------------------------------------------------


def test_benchmark_corpus_is_synthetic_and_secret_free() -> None:
    """Regenerate the corpus and scan IT — do not trust the report's flags.

    The previous version asserted that `benchmark-0.9.0.json` declared
    `synthetic: true` and `contains_secrets: false`, which proves only that
    someone wrote those words in a JSON file.
    """
    from tests.benchmarks.test_memory_benchmark import _synthetic_cortex

    records = 200
    corpus = _synthetic_cortex(records)

    hits = _scan_text(corpus)
    assert not hits, (
        f"the generated benchmark corpus carries credential-shaped strings: {hits}"
    )
    # Synthetic means every record line follows the generated template: no
    # free text that could have been pasted in from a real document.
    body = [ln for ln in corpus.splitlines() if ln.startswith("KNW:rec")]
    assert len(body) == records, (
        f"the corpus claims {records} records but generated {len(body)}"
    )
    for line in body:
        assert "synthetic memory" in line, (
            f"a corpus record is not template-generated: {line[:80]}"
        )


def test_benchmark_report_describes_the_corpus_it_measured() -> None:
    """The report must agree with the corpus the benchmark actually builds."""
    from tests.benchmarks.test_memory_benchmark import _synthetic_cortex

    report_path = ROOT / "docs" / "release" / "benchmark-0.9.0.json"
    assert report_path.is_file(), "benchmark report missing"
    data = json.loads(report_path.read_text(encoding="utf-8"))
    corpus_meta = data["corpus"]

    generated = _synthetic_cortex(int(corpus_meta["records"]))
    assert len([ln for ln in generated.splitlines() if ln.startswith("KNW:rec")]) == (
        corpus_meta["records"]
    ), "the report's record count does not match what the generator produces"

    assert corpus_meta["synthetic"] is True
    assert corpus_meta["contains_secrets"] is False
    # A content hash of the generator's output would make the report falsifiable
    # outright; until one is published, at least require the declared file name
    # to match what the benchmark writes.
    assert corpus_meta["file"] == "synthetic.cortex"
