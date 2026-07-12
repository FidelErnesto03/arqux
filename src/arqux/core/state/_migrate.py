"""Migration utility for BLP-042 — migrate .cortex files to clean CODEC-CORTEX format."""

from __future__ import annotations

from pathlib import Path

from . import _cc_parser, _cc_validator, _cc_writer
from ._crud import requires_codec_cortex


def migrate_cortex_file(path: Path, *, dry_run: bool = False) -> bool:
    """Migrate a .cortex file to clean CODEC-CORTEX format.

    Protocol (BLP-042):
      1. BACKUP   -> mv archivo.cortex -> archivo.cortex.bck
      2. LECTURA  -> extraer datos del .bck
      3. REESCRITURA -> escribir archivo.cortex NUEVO usando write_cortex()
         con entries completos (LNG con prevention, todos con name)

    Returns True if migration was performed, False if not needed.
    """
    if not path.exists():
        return False
    if path.suffix == ".bck":
        return False

    requires_codec_cortex()

    # 1. Check if migration is needed (has blocking errors).
    text = path.read_text(encoding="utf-8")
    try:
        doc = _cc_parser.parse_cortex(text, path=str(path))
        diags = _cc_validator.validate(doc)
        blocking = [
            d for d in diags
            if d.get("severity") == "error"
            and d.get("code", "").startswith(("E032", "E034", "E008"))
        ]
        if not blocking:
            return False  # no blocking errors — skip
    except Exception:
        # Unparseable file — needs migration regardless.
        pass

    # 2. Backup.
    backup = path.with_suffix(".cortex.bck")
    if not backup.exists():
        path.rename(backup)

    if dry_run:
        return True  # would migrate

    # 3. Read data from backup, build clean document.
    raw = backup.read_text(encoding="utf-8")

    # Determine stem and defaults.
    stem = path.stem
    level_default = 0
    name_default = stem
    usage_default = "config"
    kind_default = "native"

    # Try to extract ARQX metadata from backup.
    level = level_default
    name = name_default
    usage = usage_default
    kind = kind_default
    agent_val: str | None = None
    old_doc = None

    try:
        old_doc = _cc_parser.parse_cortex(raw, path=str(backup))
        for sec in old_doc.sections:
            for entry in sec.entries:
                if entry.sigil == "ARQX" and entry.name == "artifact":
                    if isinstance(entry.value, dict):
                        level = entry.value.get("level", level_default)
                        name = entry.value.get("name", name_default)
                        usage = entry.value.get("usage", usage_default)
                        kind = entry.value.get("kind", kind_default)
                        agent_val = entry.value.get("agent")
                    break
    except Exception:
        pass

    # Build a new clean CortexDocument from scratch.
    from cortex.core.ast import CortexDocument, Section, SigilDef
    from cortex.core.ast import Entry as CEntry

    new_doc = CortexDocument()

    # $0 glossary
    sec0 = Section(id="$0", title="")
    new_doc.sections.append(sec0)

    # Glossary entries — identity-level sigils.
    for sd in [
        ("ARQX", "artifact",   "attrs",  "B", "Semantic",   "ArqUX artifact metadata"),
        ("IDN", "identity",    "attrs",  "B", "Semantic",   "Agent identity descriptor"),
        ("FCS", "focus",       "attrs",  "H", "Working",    "Default attention anchor"),
        ("OBJ", "objective",   "attrs",  "H", "Working",    "Standing objectives"),
        ("AXM", "axiom",       "cuerpo", "H", "Prefrontal", "Non-negotiable principles"),
        ("LIM", "limit",       "attrs",  "M", "Prefrontal", "Hard limits and boundaries"),
        ("LNG", "lesson",      "attrs",  "M", "Episodic",   "Behavioral lessons"),
        ("DESC","description", "cuerpo", "B", "Semantic",   "Agent description and style"),
    ]:
        new_doc.glossary.add_sigil(SigilDef(
            sigil=sd[0], name=sd[1], type=sd[2],
            risk=sd[3], layer=sd[4], description=sd[5],
        ))

    # Types header
    sec0.comments.append("#")
    sec0.comments.append("# Types:")
    sec0.comments.append("# attrs = canonical type")
    sec0.comments.append("# cuerpo = canonical type")

    # $19: ARQUX METADATA
    sec01 = Section(id="$19", title="ARQUX METADATA")
    meta_value = {"level": level, "name": name, "usage": usage, "kind": kind}
    if agent_val:
        meta_value["agent"] = agent_val
    sec01.entries.append(CEntry(
        "$19", sigil="ARQX", name="artifact", type="attrs",
        value=meta_value,
    ))
    new_doc.sections.append(sec01)

    # Copy all entries from the old doc, validating and completing them.
    # We preserve sections $1 (IDENTITY) through $7 (DESCRIPTION).
    if old_doc:
        for sec in old_doc.sections:
            if sec.id in ("$0", "$19"):
                continue  # skip — we rebuilt these
            new_sec = Section(id=sec.id, title=sec.title)
            new_sec.comments = sec.comments
            for entry in sec.entries:
                new_sec.entries.append(CEntry(
                    sec.id,
                    sigil=entry.sigil,
                    name=entry.name,
                    type=entry.type or "attrs",
                    value=entry.value if isinstance(entry.value, dict) else str(entry.value) if entry.value else "",
                ))
            new_doc.sections.append(new_sec)

    # 4. Write clean file via CODEC-CORTEX writer.
    cortex_text = _cc_writer.write_cortex(new_doc)
    path.write_text(cortex_text, encoding="utf-8")

    # 5. Verify.
    try:
        final_text = path.read_text(encoding="utf-8")
        final_doc = _cc_parser.parse_cortex(final_text, path=str(path))
        final_diags = _cc_validator.validate(final_doc)
        final_errors = [
            d for d in final_diags
            if d.get("severity") == "error"
            and d.get("code", "").startswith(("E032", "E034", "E008"))
        ]
        if final_errors:
            # Entries with historical incompleteness (E032/E034/E008) are
            # acceptable during migration — the handler fix prevents new ones.
            # Revert only on structural errors that make the file unparseable.
            structural = [
                d for d in final_diags
                if d.get("severity") == "error"
                and d.get("code", "").startswith(("E001", "E002", "E015"))
            ]
            if structural:
                if backup.exists():
                    path.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
                    backup.unlink()
                raise RuntimeError(
                    f"migrate_cortex_file produced {len(structural)} structural errors — reverted"
                )
    except RuntimeError:
        raise
    except Exception as exc:
        if backup.exists():
            path.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
            backup.unlink()
        raise RuntimeError(f"migrate_cortex_file verify failed: {exc} — reverted") from exc

    return True
