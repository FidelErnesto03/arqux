#!/usr/bin/env python3
"""Apply the ArqUX brand document format to every public doc.

Inserts a uniform brand header (logo + doc-type ribbon) after front-matter
and a brand footer before EOF, between idempotent markers. The format is
generated, not hand-edited — regenerate with:

    python scripts/format_docs.py            # apply to all public docs
    python scripts/format_docs.py --check    # verify all docs carry the blocks

Blocks and rules are defined by docs/es/formato-documental.md (doc-type canon).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent

BRAND_DIR = "docs/assets/brand"
LOGO_LIGHT = f"{BRAND_DIR}/arqux-logo-primary-light.svg"
LOGO_DARK = f"{BRAND_DIR}/arqux-logo-primary-dark.svg"

HDR_OPEN = "<!-- DOC-BRAND -->"
HDR_CLOSE = "<!-- /DOC-BRAND -->"
FTR_OPEN = "<!-- DOC-FOOT -->"
FTR_CLOSE = "<!-- /DOC-FOOT -->"
FM_RX = re.compile(r"\A---\n(.*?)\n---\n", re.S)
MARKER_RX = re.compile(r"^\s*<!-- /?DOC-(?:BRAND|FOOT) -->\s*$")

DOC_TYPE_ES = {
    "tutorial": "Tutorial",
    "guide": "Guía",
    "reference": "Referencia",
    "explanation": "Explicación",
    "canon": "Canon",
    "report": "Reporte",
}
STATUS_ES = {
    "normative": "Normativo",
    "informative": "Informativo",
    "historical": "Histórico",
    "draft": "Borrador",
}
DOC_TYPE_EN = {
    "tutorial": "Tutorial",
    "guide": "Guide",
    "reference": "Reference",
    "explanation": "Explanation",
    "canon": "Canon",
    "report": "Report",
}
STATUS_EN = {
    "normative": "Normative",
    "informative": "Informative",
    "historical": "Historical",
    "draft": "Draft",
}
INDEX_LINK = {
    "es": ("docs/es/README.md", "índice de documentación", "verificado"),
    "en": ("docs/en/README.md", "documentation index", "verified"),
}

# Docs that do not receive the brand block (generated artifacts, machine
# indexes, governance kernels, retired stubs).
NO_BRAND = {
    "AGENTS.md", "AGENTS.lite.md", "AGENTS.full.md",   # governance kernels
    "CHANGELOG.md",                                    # keep-a-changelog
    "PILOT_MODE.md",                                   # retired stub
    "llms.txt",                                        # machine index
    "docs/es/especificacion/secciones-cerebro-canon.md",  # canon shard
}


def public_docs() -> list[Path]:
    return sorted(
        p for p in list(REPO.glob("*.md"))
        + list((REPO / "docs" / "es").rglob("*.md"))
        + list((REPO / "docs" / "en").rglob("*.md"))
        if p.relative_to(REPO).as_posix() not in NO_BRAND
        and p.name not in NO_BRAND
    )


def _rel_root(doc: Path) -> str:
    """Relative path prefix from the doc's directory back to repo root."""
    depth = len(doc.relative_to(REPO).parent.parts)
    return "../" * depth if depth else "./"


def _fm(doc_text: str) -> dict:
    m = FM_RX.match(doc_text)
    return (yaml.safe_load(m.group(1)) or {}) if m else {}


def _lang(doc: Path) -> str:
    parts = doc.relative_to(REPO).parts
    return "en" if len(parts) > 1 and parts[0] == "docs" and parts[1] == "en" else "es"


def _ribbon(doc: Path, fm: dict, version: str) -> str | None:
    dt = fm.get("doc_type")
    if not dt:
        return None
    types, statuses = (DOC_TYPE_EN, STATUS_EN) if _lang(doc) == "en" else (DOC_TYPE_ES, STATUS_ES)
    parts = [types.get(dt, dt)]
    if fm.get("status") in statuses:
        parts.append(statuses[fm["status"]])
    parts.append(f"ArqUX {fm.get('version', version)}")
    return " · ".join(parts)


def header_block(doc: Path, fm: dict, version: str) -> str:
    rel = _rel_root(doc)
    ribbon = _ribbon(doc, fm, version)
    lines = [
        HDR_OPEN,
        '<p align="center">',
        "  <picture>",
        f'    <source media="(prefers-color-scheme: dark)" srcset="{rel}{LOGO_DARK}">',
        f'    <img alt="ArqUX" src="{rel}{LOGO_LIGHT}" width="240">',
        "  </picture>",
        "</p>",
    ]
    if ribbon:
        lines.append(f'<p align="center"><sub>{ribbon}</sub></p>')
    lines.append(HDR_CLOSE)
    return "\n".join(lines) + "\n\n"


def footer_block(doc: Path, fm: dict, version: str) -> str:
    rel = _rel_root(doc)
    ver = str(fm.get("version", version))
    verified = fm.get("verified", "")
    index_path, index_label, ver_label = INDEX_LINK[_lang(doc)]
    stamp = f" · {ver_label} {verified}" if verified else ""
    return (
        f"\n\n{FTR_OPEN}\n<hr>\n"
        f'<p align="center"><sub>ArqUX {ver}{stamp} · '
        f'<a href="{rel}{index_path}">{index_label}</a></sub></p>\n'
        f"{FTR_CLOSE}\n"
    )


def _strip_blocks(text: str) -> str:
    """Remove generated DOC-BRAND/DOC-FOOT blocks — only marker lines that sit
    OUTSIDE fenced code blocks (a spec may show the markers as examples)."""
    lines = text.split("\n")
    out: list[str] = []
    in_fence = in_block = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and MARKER_RX.match(line):
            in_block = not in_block
            continue
        if not in_block:
            out.append(line)
    return "\n".join(out)


def apply_doc(doc: Path, version: str) -> bool:
    text = doc.read_text(encoding="utf-8")
    fm = _fm(text)
    body = _strip_blocks(text)
    header = header_block(doc, fm, version)
    footer = footer_block(doc, fm, version)
    m = FM_RX.match(body)
    if m:
        new = body[: m.end()] + "\n" + header + body[m.end():].lstrip("\n")
    else:
        new = header + body.lstrip("\n")
    new = new.rstrip("\n") + footer
    if new != text:
        doc.write_text(new, encoding="utf-8")
        return True
    return False


def check_doc(doc: Path) -> list[str]:
    text = doc.read_text(encoding="utf-8")
    missing = []
    if HDR_OPEN not in text:
        missing.append("DOC-BRAND header")
    if FTR_OPEN not in text:
        missing.append("DOC-FOOT footer")
    return missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify, don't write")
    args = ap.parse_args()
    version = re.search(
        r'^version\s*=\s*"([^"]+)"',
        (REPO / "pyproject.toml").read_text(encoding="utf-8"),
        re.M,
    ).group(1)

    failures = []
    changed = 0
    for doc in public_docs():
        if args.check:
            for miss in check_doc(doc):
                failures.append(f"{doc.relative_to(REPO)}: missing {miss}")
        elif apply_doc(doc, version):
            changed += 1
            print(f"branded {doc.relative_to(REPO)}")

    if args.check:
        if failures:
            print("\n".join(failures))
            return 1
        print("brand format OK — all public docs carry header+footer")
        return 0
    print(f"done — {changed} docs branded, version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
