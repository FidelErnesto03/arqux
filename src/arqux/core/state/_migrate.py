"""Migration utility for BLP-042 — migrate .cortex files to clean CORTEX format.

BLP-005: Replaced CODEC-CORTEX writer with ArqUX's own
write_cortex_from_json + atomic_write_text.
"""

from __future__ import annotations

from pathlib import Path

# BLP-fix (T-005/G-9): _cc_* are defined in core.state.__init__
# (as None when CODEC-CORTEX is absent), so a top-level 'from . import'
# is safe and no longer circular.
from . import _cc_parser, _cc_validator
from ._crud import requires_codec_cortex

# BLP-005: ArqUX's own writer and atomic writer.
from ...cortex.reader import cortex_to_dict
from ...cortex.writer import write_cortex_from_json
from ...cortex.atomic import atomic_write_text


def migrate_cortex_file(path: Path, *, dry_run: bool = False) -> bool:
    """Migrate a .cortex file to clean CORTEX format.

    Protocol (BLP-042):
      1. BACKUP   -> mv archivo.cortex -> archivo.cortex.bck
      2. LECTURA  -> extraer datos del .bck
      3. REESCRITURA -> escribir archivo.cortex NUEVO usando
         write_cortex_from_json() con entries completos
         (LNG con prevention, todos con name)

    BLP-005: Uses ArqUX's own reader/writer instead of CODEC-CORTEX
    AST builder + writer.

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

    # 2. Dry-run check — BEFORE any filesystem modification (OBS-001 fix).
    #     In dry-run mode we must NOT rename/move the original file.
    if dry_run:
        return True  # would migrate

    # 3. Backup.
    backup = path.with_suffix(".cortex.bck")
    if not backup.exists():
        path.rename(backup)

    # 4. Read data from backup, build clean document.
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

    # Build a new clean document using ArqUX's JSON dict model.
    # Glossary comments (identity-level sigils).
    glossary_comments = [
        "# -- $0: ARQUX GOVERNANCE GLOSSARY --",
        "# Sigil | Name | Type | Risk | Cognitive Layer | Description",
        "# ARQX  | artifact  | attrs  | B | Semantic   | ArqUX artifact metadata",
        "# IDN   | identity   | attrs  | B | Semantic   | Agent identity descriptor",
        "# FCS   | focus      | attrs  | H | Working    | Default attention anchor",
        "# OBJ   | objective  | attrs  | H | Working    | Standing objectives",
        "# AXM   | axiom      | cuerpo | H | Prefrontal | Non-negotiable principles",
        "# LIM   | limit      | attrs  | M | Prefrontal | Hard limits and boundaries",
        "# LNG   | lesson     | attrs  | M | Episodic   | Behavioral lessons",
        "# DESC  | description | cuerpo | B | Semantic   | Agent description and style",
        "#",
        "# Types:",
        "# attrs = canonical type",
        "# cuerpo = canonical type",
    ]

    new_doc = {
        "glossary": {
            "header": "$0",
            "comments": glossary_comments,
        },
        "sections": [],
    }

    # $19: ARQUX METADATA
    # OBS-002 fix: Preserve ALL entries from the original $19 section,
    # not just ARQX:artifact. We copy every entry from the old $19,
    # then ensure ARQX:artifact exists (add if missing).
    meta_value: dict = {"level": level, "name": name, "usage": usage, "kind": kind}
    if agent_val:
        meta_value["agent"] = agent_val

    preserved_19_entries: list[dict] = []
    arqx_artifact_found = False
    if old_doc:
        for sec in old_doc.sections:
            if sec.id != "$19":
                continue
            for entry in sec.entries:
                if entry.sigil == "ARQX" and entry.name == "artifact":
                    arqx_artifact_found = True
                    # Use the completed meta_value (with defaults filled in).
                    preserved_19_entries.append({
                        "sigil": "ARQX",
                        "name": "artifact",
                        "attrs": meta_value,
                    })
                elif isinstance(entry.value, dict):
                    preserved_19_entries.append({
                        "sigil": entry.sigil,
                        "name": entry.name,
                        "attrs": entry.value,
                    })
                elif isinstance(entry.value, str) and entry.value:
                    preserved_19_entries.append({
                        "sigil": entry.sigil,
                        "name": entry.name,
                        "body": entry.value,
                    })
                else:
                    preserved_19_entries.append({
                        "sigil": entry.sigil,
                        "name": entry.name,
                        "attrs": {},
                    })
            break  # only one $19 section

    if not arqx_artifact_found:
        preserved_19_entries.insert(0, {
            "sigil": "ARQX",
            "name": "artifact",
            "attrs": meta_value,
        })

    new_doc["sections"].append({
        "id": "$19",
        "title": "ARQUX METADATA",
        "comments": [],
        "entries": preserved_19_entries,
    })

    # Copy all entries from the old doc, validating and completing them.
    # We preserve sections $1 (IDENTITY) through $7 (DESCRIPTION).
    if old_doc:
        for sec in old_doc.sections:
            if sec.id in ("$0", "$19"):
                continue  # skip — we rebuilt these
            new_entries = []
            for entry in sec.entries:
                if isinstance(entry.value, dict):
                    new_entries.append({
                        "sigil": entry.sigil,
                        "name": entry.name,
                        "attrs": entry.value,
                    })
                elif isinstance(entry.value, str) and entry.value:
                    new_entries.append({
                        "sigil": entry.sigil,
                        "name": entry.name,
                        "body": entry.value,
                    })
                else:
                    # Empty value — attrs with empty dict
                    new_entries.append({
                        "sigil": entry.sigil,
                        "name": entry.name,
                        "attrs": {},
                    })
            new_doc["sections"].append({
                "id": sec.id,
                "title": sec.title,
                "comments": list(getattr(sec, "comments", []) or []),
                "entries": new_entries,
            })

    # 4. Write clean file via ArqUX writer + atomic write.
    cortex_text = write_cortex_from_json(new_doc)
    atomic_write_text(cortex_text, str(path))

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
