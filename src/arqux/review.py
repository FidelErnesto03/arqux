"""REQ-09: ``arqux review --cycle <id>`` — HCORTEX review reports.

Renders a closed or open cycle to HCORTEX (human-legible Markdown) for
review or a Pull Request body: a human header with cycle state, task table
and evidence metrics, followed by the round-trippable HCORTEX rendering of
``cycle.cortex`` produced by CODEC-CORTEX.

``from_hcortex(path)`` recompiles a reviewed report back to ``.cortex`` and
reports ``loss_count`` — the spec's negative test requires it to be 0.
"""
from __future__ import annotations

import re
from pathlib import Path

from .constants import ARQUX_DIR


def _scalar_lexeme(scalar) -> str:
    lex = getattr(scalar, "lexeme", None)
    if lex is not None:
        return lex
    return str(getattr(scalar, "value", scalar))


def _serialize_idea(idea) -> str:
    tag, fields = idea.payload
    name = idea.name or "_"
    if tag == "attrs":
        body = ",".join(f"{k}:{_scalar_lexeme(v)}" for k, v in fields)
        return f"{idea.qualified_symbol}:{name}{{{body}}}"
    # body/cuerpo shapes serialize as multi-line entries
    body = fields if isinstance(fields, str) else str(fields)
    return f"{idea.qualified_symbol}:{name}{{\n{body}\n}}"


def document_to_cortex(doc) -> str:
    """Serialize a codec_cortex Document back to cortex:1.0 text."""
    parts: list[str] = ["$0"]
    fmt = getattr(doc.glossary, "format", None)
    version = getattr(fmt, "version", "1.0") if fmt else "1.0"
    encoding = getattr(fmt, "encoding", "UTF-8") if fmt else "UTF-8"
    parts.append(f"$0:format{{cortex:{version}, encoding:{encoding}}}")
    for sym in doc.glossary.symbols:
        label = getattr(sym, "label", sym.sigil.lower() + "_contract")
        attrs = ",".join(f"{k}:{_scalar_lexeme(v)}" for k, v in sym.attrs)
        parts.append(f"{sym.sigil}:{label}{{{attrs}}}")
    for sec in doc.sections:
        title = getattr(sec, "title", "") or ""
        parts += ["", f"${sec.id}: {title}".rstrip()]
        parts += [_serialize_idea(i) for i in sec.ideas]
    return "\n".join(parts) + "\n"


def _idea_keys(doc) -> set[tuple]:
    return {
        (s.id, i.qualified_symbol, i.name)
        for s in doc.sections
        for i in s.ideas
    }


def from_hcortex(path: Path) -> dict:
    """Compile an HCORTEX markdown file back to .cortex text.

    Returns ``{"text": cortex_text, "loss_count": n, "entries": n,
    "errors": [...]}`` — loss is measured as source ideas missing after a
    re-parse of the serialized output (must be 0 for a lossless review).
    """
    try:
        import codec_cortex
    except ImportError as exc:
        raise RuntimeError(
            "arqux review requires the CORTEX codec. "
            "Install with: pip install codec-cortex>=1.0,<1.1"
        ) from exc

    md = Path(path).read_text(encoding="utf-8")
    doc, diags = codec_cortex.compile_hcortex(md)
    errors = [str(d) for d in diags if getattr(d, "severity", "") == "error"]
    if errors or doc is None:
        return {"text": "", "loss_count": None, "entries": 0, "errors": errors}

    text = document_to_cortex(doc)
    try:
        reparsed = codec_cortex.parse_cortex(text)
        loss = len(_idea_keys(doc) - _idea_keys(reparsed))
        entries = sum(len(s.ideas) for s in doc.sections)
    except Exception as exc:  # noqa: BLE001
        return {"text": text, "loss_count": None, "entries": 0,
                "errors": [f"reparse failed: {exc}"]}
    return {"text": text, "loss_count": loss, "entries": entries, "errors": []}


def review_report(project_root: Path, cycle_id: str) -> str:
    """Markdown review report: human header + round-trippable HCORTEX body."""
    try:
        import codec_cortex
    except ImportError as exc:
        raise RuntimeError(
            "arqux review requires the CORTEX codec. "
            "Install with: pip install codec-cortex>=1.0,<1.1"
        ) from exc

    cdir = Path(project_root) / ARQUX_DIR / "cycles" / cycle_id
    cycle_file = cdir / "cycle.cortex"
    if not cycle_file.exists():
        raise FileNotFoundError(f"cycle {cycle_id} not found under {cdir}")

    manifest = cdir / "MANIFEST.md"
    status = "unknown"
    if manifest.exists():
        m = re.search(r'status:\s*"?(\w+)', manifest.read_text(encoding="utf-8"))
        status = m.group(1) if m else status

    seal = cdir / "seal.cortex"
    seal_hash = "none"
    if seal.exists():
        m = re.search(r'seal_sha256:"([0-9a-f]{16})', seal.read_text(encoding="utf-8"))
        if m:
            seal_hash = m.group(1) + "…"

    tasks_dir = cdir / "tasks"
    tasks: list[tuple[str, str, str]] = []
    if tasks_dir.is_dir():
        for f in sorted(tasks_dir.glob("*.cortex")):
            for line in f.read_text(encoding="utf-8").splitlines():
                m = re.match(r"TSK:(\w+)\{(.*)\}", line.strip())
                if not m:
                    continue
                tid, attrs = m.groups()
                st = re.search(r'status:"?(\w+)', attrs)
                ob = re.search(r'obj:"([^"]{0,60})', attrs)
                tasks.append((tid, st.group(1) if st else "?", ob.group(1) if ob else ""))
                break

    doc = codec_cortex.parse_cortex(cycle_file.read_text(encoding="utf-8"))
    entries = sum(len(s.ideas) for s in doc.sections)
    hcortex = codec_cortex.render_hcortex(doc)

    out = [
        f"# Cycle Review — {cycle_id}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Status | {status} |",
        f"| Seal | `{seal_hash}` |",
        f"| Entries | {entries} |",
        f"| Tasks | {len(tasks)} |",
        "",
    ]
    if tasks:
        out += ["| Task | Status | Objective |", "|---|---|---|"]
        out += [f"| {t} | {s} | {o} |" for t, s, o in tasks]
        out.append("")
    out += ["## Evidence (HCORTEX — round-trippable)", "", hcortex]
    return "\n".join(out)


__all__ = ["document_to_cortex", "from_hcortex", "review_report"]
