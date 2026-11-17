"""Docs-as-contract gate (BLP-032): every public doc's verifiable claims are
checked against the code — front-matter, versions, cited commands, cited error
codes, internal links, and internal jargon.

Every exception is declared explicitly with its justification — zero silent
skips. A failure names file + rule; rules run offline (regex + parse, <5s).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

from arqux.constants import ARQUX_VERSION

ROOT = Path(__file__).resolve().parents[2]

DOC_TYPES = {"tutorial", "guide", "reference", "explanation", "canon", "report"}
STATUSES = {"normative", "informative", "historical", "draft"}

PUBLIC_DOCS = sorted(
    p for p in list(ROOT.glob("*.md"))
    + list((ROOT / "docs" / "es").rglob("*.md"))
    + list((ROOT / "docs" / "en").rglob("*.md"))
    if ".git" not in p.parts
)

# --- Declared exceptions (each justified — a skip must be a decision) --------

# Files that legitimately carry no YAML front-matter (not docs-pipeline docs).
NO_FRONT_MATTER = {
    "AGENTS.md",            # harness kernel — a .cortex-adjacent contract, not Diátaxis
    "AGENTS.lite.md",
    "AGENTS.full.md",
    "CHANGELOG.md",         # keep-a-changelog format — its own front-matter convention
    "PILOT_MODE.md",        # legacy guide frozen pending status=historical
    "README.md",            # product door — badges serve as its header contract
    "HANDLERS.md",          # generated artifact — regenerating overwrites FM anyway
    "llms.txt",             # machine index (llmstxt.org format), not a Diátaxis doc
    "docs/es/especificacion/secciones-cerebro-canon.md",  # canon shard w/o FM
}

# Public entry docs where internal working jargon must never appear.
# Guides/canon may cite real artifact ids (SES022-E0093) — that is evidence,
# not jargon; the ban targets leaks of the team's working session ids into the
# product's front door.
ENTRY_DOCS = [
    "README.md", "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md",
    "ARCHITECTURE.md", "docs/es/README.md",
]
JARGON_EXCEPTIONS = {
    # The tutorial creates CYCLE-01/BLP-001 itself — they are the reader's own
    # artifacts, not internal session ids.
    "docs/es/tutorial/inicio-rapido.md": r"BLP-00[12]|CYCLE-0[01]|SES\d{3}",
    # Same pattern in the English tutorial: CYCLE-01/BLP-001 are the reader's
    # own example artifacts, created by the tutorial commands themselves.
    "docs/en/tutorial/inicio-rapido.md": r"BLP-00[12]|CYCLE-0[01]|SES\d{3}",
    # EN twin of the audit guide: SES022-E0093/CYCLE-16 are real captured
    # evidence ids — the same content the ES canon carries.
    "docs/en/guias/auditar-trabajo.md": r"SES\d{3}|CYCLE-\d{2}",
    # EN twin of the wake guide: the captured WRK output shows scope CYCLE-01 —
    # real output content, not session jargon.
    "docs/en/guias/arranque-agente.md": r"CYCLE-0[01]",
    # EN twins of the reference/explanation docs carry the same captured
    # command output and spec examples the ES canon carries (CYCLE-16 review
    # output, SES999 demo session, BLP-016 event target, CYCLE-99 seal example,
    # provenance ids in the test-suite doctrine).
    "docs/en/referencia/cli.md": r"CYCLE-\d{2}|BLP-\d{3}|SES\d{3}",
    "docs/en/referencia/formatos.md": r"CYCLE-\d{2}|BLP-\d{3}|SES\d{3}",
    "docs/en/explicacion/test-suite-framework.md": r"BLP-\d{3}|CYCLE-\d{2}|SES\d{3}|T-\d+\.\d+",
    # ARCHITECTURE's data-flow example calls a hypothetical CYCLE-01 — a
    # reader-facing example artifact, not a session id.
    "ARCHITECTURE.md": r"CYCLE-0[01]",
    "docs/en/root/ARCHITECTURE.md": r"CYCLE-0[01]",
}

# Codes cited in docs that are demo values inside format examples, not claims
# about real error codes.
CODE_CITATION_EXCEPTIONS = {"ERR_DEMO"}  # formatos.md — placeholder in spec example

# Files exempt from the "no 0.x series references" rule:
VERSION_SERIES_EXCEPTIONS = {
    "CHANGELOG.md",     # version history is its content
    "PILOT_MODE.md",    # frozen legacy pilot doc (0.4.3-era) pending historical status
    "README.md",        # honest note: PyPI still serves 0.9.0 — a fact, not a claim
    "SECURITY.md",      # "≤0.9.x ❌" declares it UNSUPPORTED — the point of the table
    "docs/es/tutorial/inicio-rapido.md",  # same honest PyPI note
    "docs/es/explicacion/test-suite-framework.md",  # historical baseline measurement
}

JARGON_RX = re.compile(r"(?<![\w.])(?:BLP-\d{3}|CYCLE-\d{2}|SES\d{3}|E-\d{4}|P0-[ABC]|T-\d+\.\d+)")
CODE_RX = re.compile(r"\b(?:ERR_[A-Z_]+|POLICY_[A-Z]+|PERMISSION_DENIED|EXPORT_BLOCKED)\b")
CMD_RX = re.compile(r"`arqux ([a-z][a-z0-9-]*(?:\s+[a-z][a-z0-9-]*)?)`")
LINK_RX = re.compile(r"\]\(([^)\s#]+)(#[^)]*)?\)")
STALE_SERIES_RX = re.compile(r"\b0\.4\.\d")
FM_RX = re.compile(r"\A---\n(.*?)\n---", re.S)


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _click_commands() -> set[str]:
    """All `arqux <cmd>` and `arqux <group> <sub>` paths in the real click tree."""
    import click

    from arqux.cli import main

    names: set[str] = set()

    def walk(group: click.Command, prefix: str = "") -> None:
        for name, cmd in getattr(group, "commands", {}).items():
            names.add(prefix + name)
            if isinstance(cmd, click.Group):
                walk(cmd, f"{prefix}{name} ")

    walk(main)
    return names


def _error_codes_in_code() -> set[str]:
    codes: set[str] = set()
    for py in (ROOT / "src" / "arqux").rglob("*.py"):
        codes.update(CODE_RX.findall(py.read_text(encoding="utf-8")))
    return codes


def test_front_matter_valid():
    """Rule (a): every public doc's front-matter parses with enum-valid values
    and matches the repo version."""
    failures = []
    for doc in PUBLIC_DOCS:
        rel = _rel(doc)
        text = doc.read_text(encoding="utf-8")
        m = FM_RX.match(text)
        if not m:
            if rel.split("/")[-1] in NO_FRONT_MATTER or rel in NO_FRONT_MATTER:
                continue
            failures.append(f"{rel}: missing front-matter (not in declared NO_FRONT_MATTER)")
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        for key in ("doc_type", "status", "version", "verified"):
            if key not in fm:
                failures.append(f"{rel}: front-matter missing '{key}'")
        if fm.get("doc_type") not in DOC_TYPES:
            failures.append(f"{rel}: doc_type={fm.get('doc_type')!r} not in {sorted(DOC_TYPES)}")
        if fm.get("status") not in STATUSES:
            failures.append(f"{rel}: status={fm.get('status')!r} not in {sorted(STATUSES)}")
        if str(fm.get("version")) != ARQUX_VERSION:
            failures.append(f"{rel}: version={fm.get('version')!r} != pyproject {ARQUX_VERSION}")
    assert not failures, "\n".join(failures)


def test_no_stale_version_series():
    """Rule (b): no 0.4.x-series references survive in public docs (0.9.x
    PyPI notes are honest facts covered by declared exceptions)."""
    failures = []
    for doc in PUBLIC_DOCS:
        rel = _rel(doc)
        if rel in VERSION_SERIES_EXCEPTIONS or rel.split("/")[-1] in VERSION_SERIES_EXCEPTIONS:
            continue
        for i, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if STALE_SERIES_RX.search(line):
                failures.append(f"{rel}:{i}: stale 0.4.x reference: {line.strip()[:70]}")
    assert not failures, "\n".join(failures)


def test_cited_commands_exist():
    """Rule (c): every backticked `arqux <cmd>` is a real command or
    group/subcommand path in the click tree."""
    commands = _click_commands()
    top_level = {c.split(" ")[0] for c in commands}
    failures = []
    for doc in PUBLIC_DOCS:
        for i, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for m in CMD_RX.finditer(line):
                cmd = m.group(1).strip()
                first = cmd.split()[0]
                if cmd in commands or first in top_level:
                    continue
                failures.append(f"{_rel(doc)}:{i}: `arqux {cmd}` not in cli.py")
    assert not failures, "\n".join(failures)


def test_cited_error_codes_exist():
    """Rule (d): every ERR_*/POLICY_*/PERMISSION_DENIED/EXPORT_BLOCKED code
    cited in docs exists in src/arqux."""
    real = _error_codes_in_code() | CODE_CITATION_EXCEPTIONS
    failures = []
    for doc in PUBLIC_DOCS:
        for i, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for code in CODE_RX.findall(line):
                if code not in real:
                    failures.append(f"{_rel(doc)}:{i}: cited code {code} not found in src/")
    assert not failures, "\n".join(failures)


def test_error_catalog_codes_exist():
    """Rule (d2): every first-column code in the failure catalog exists as an
    identifier or string in src/ — catches bare codes like SESSION_UNBOUND
    that the ERR_*-prefixed regex of rule (d) cannot see (OUT-AUDIT H-x /
    errores.md documented the phantom UNBOUND_SESSION)."""
    src_text = "".join(
        p.read_text(encoding="utf-8")
        for p in (ROOT / "src" / "arqux").rglob("*")
        if p.suffix in {".py", ".md"}
    )
    doc = ROOT / "docs" / "es" / "referencia" / "errores.md"
    ident = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
    failures = []
    for i, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
        first_col = re.match(r"^\|\s*(`[^`]+`(?:\s*/\s*`[^`]+`)*)\s*\|", line)
        if not first_col:
            continue
        for code in re.findall(r"`([^`]+)`", first_col.group(1)):
            # Identifier-like tokens only — skips format templates such as
            # `OUT-ERROR code=...` and exit codes like `exit 2`.
            if ident.match(code) and code not in src_text:
                failures.append(f"errores.md:{i}: catalog code {code} not found in src/")
    assert not failures, "\n".join(failures)


def test_relative_links_resolve():
    """Rule (e): relative markdown links resolve to a real file (external
    http/mailto and pure anchors are out of scope by design)."""
    failures = []
    for doc in PUBLIC_DOCS:
        for i, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for m in LINK_RX.finditer(line):
                target = m.group(1)
                if target.startswith(("http://", "https://", "mailto:", "/")):
                    continue
                if (doc.parent / target).exists():
                    continue
                # Declared debt: an EN doc may link a sibling whose twin is
                # still pending — the skip lives exactly as long as the
                # TRANSLATION_PENDING entry it names (BLP-035).
                rel = _rel(doc)
                if rel.startswith("docs/en/"):
                    en_rel = (doc.parent / target).resolve()
                    try:
                        pending_key = en_rel.relative_to(ROOT / "docs" / "en").as_posix()
                    except ValueError:
                        pending_key = ""
                    if pending_key in TRANSLATION_PENDING or any(
                        p.startswith(pending_key.rstrip("/") + "/")
                        for p in TRANSLATION_PENDING
                    ):
                        continue
                failures.append(f"{rel}:{i}: dead link {target}")
    assert not failures, "\n".join(failures)


# Jargon-rule scope (BLP-034 H-03 resolution): the strict set is ENTRY_DOCS —
# the public front door — plus all of docs/en/. The ES canon, guides and
# references legitimately carry BLP/CYCLE/SES ids as *content* (the spec
# documents the artifact format those ids name; CHANGELOG is version history;
# HANDLERS.md is generated from registry provenance). Scanning them for the
# same patterns would flag the corpus's own subject matter — that is the
# documented scope decision, not a silent hole.
JARGON_SCANNED = ENTRY_DOCS + [
    _rel(p) for p in sorted((ROOT / "docs" / "en").rglob("*.md"))
]

# Prefixes where the jargon rule does not apply at all: the EN canon mirror
# (docs/en/especificacion/) documents the governance artifact format whose
# ids (CYCLE-NN, SESNNN, BLP-NNN, T-NNN) ARE its subject matter — the ES
# canon it translates is equally outside the scanned scope.
JARGON_EXEMPT_PREFIXES = ("docs/en/especificacion/",)


def test_brand_format_present():
    """Rule (g): every branded doc carries both DOC-BRAND and DOC-FOOT
    markers — the uniform presentation layer defined by
    docs/es/formato-documental.md (Brand Kit v1.0). NO_BRAND exceptions are
    declared in scripts/format_docs.py."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import format_docs

    failures = []
    for doc in format_docs.public_docs():
        for miss in format_docs.check_doc(doc):
            failures.append(f"{doc.relative_to(ROOT)}: missing {miss}")
    assert not failures, "\n".join(failures)


# --- Bilingual mirror parity (BLP-035) --------------------------------------
#
# docs/en/ is a 1:1 mirror of docs/es/: same relative path, same filename,
# same doc_type/status/version — English body, Spanish canon. Two transition
# sets are declared while the mirror is being populated; both must be EMPTY
# at BLP-035 close. An entry here is a debt declaration, never a silent skip.

# ES docs whose EN twin is not yet written — shrink this list as twins land.
# BLP-035 F3 closed 2026-11-16: all 17 spec docs mirrored; empty set.
TRANSLATION_PENDING: set[str] = set()

# EN files with no ES twin and none planned — BLP-035 T-10 closed 2026-11-16:
# the 7 legacy pre-mirror paths were retired; root twins under docs/en/root/
# are already excluded from the mirror scan above (they mirror root *.md,
# not docs/es/). Empty set — declared, never silent.
EN_ONLY: set[str] = set()


def test_en_es_mirror_parity():
    """Rule (h): docs/en mirrors docs/es — every ES doc has an EN twin at the
    same relative path with identical doc_type/status/version, and no EN doc
    lacks its ES canon. TRANSLATION_PENDING/EN_ONLY are declared debt and must
    be empty when BLP-035 closes."""
    es_root = ROOT / "docs" / "es"
    en_root = ROOT / "docs" / "en"
    es = {
        p.relative_to(es_root).as_posix()
        for p in es_root.rglob("*.md")
        if p.name != "secciones-cerebro-canon.md"  # shard — mirror exception declared
    }
    en = {
        p.relative_to(en_root).as_posix()
        for p in en_root.rglob("*.md")
        if "root" not in p.relative_to(en_root).parts
    }
    failures = []
    for rel in sorted(es - en - TRANSLATION_PENDING):
        failures.append(f"docs/es/{rel}: missing EN twin docs/en/{rel} (undeclared)")
    for rel in sorted(en - es - EN_ONLY):
        failures.append(f"docs/en/{rel}: EN doc without ES canon (undeclared)")
    for rel in sorted(es & en):
        fm_es = yaml.safe_load(
            FM_RX.match((es_root / rel).read_text(encoding="utf-8")).group(1)
        )
        fm_en = yaml.safe_load(
            FM_RX.match((en_root / rel).read_text(encoding="utf-8")).group(1)
        )
        for key in ("doc_type", "status", "version"):
            if fm_es.get(key) != fm_en.get(key):
                failures.append(
                    f"{rel}: EN {key}={fm_en.get(key)!r} != ES {key}={fm_es.get(key)!r}"
                )
    assert not failures, "\n".join(failures)


def test_no_internal_jargon_in_entry_docs():
    """Rule (f): scanned docs carry no internal working ids
    (BLP-NNN, CYCLE-NN, SESNNN, E-NNNN, P0-x, T-N.N). Scope: ENTRY_DOCS +
    docs/en/** — see JARGON_SCANNED rationale (BLP-034)."""
    failures = []
    for rel in JARGON_SCANNED:
        if rel.startswith(JARGON_EXEMPT_PREFIXES):
            continue
        text = (ROOT / rel).read_text(encoding="utf-8")
        allowed = JARGON_EXCEPTIONS.get(rel)
        for i, line in enumerate(text.splitlines(), 1):
            for m in JARGON_RX.finditer(line):
                if allowed and re.search(allowed, m.group(0)):
                    continue
                failures.append(f"{rel}:{i}: internal jargon {m.group(0)}")
    assert not failures, "\n".join(failures)
