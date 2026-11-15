# SPDX-License-Identifier: MPL-2.0
"""ArqUX-owned CORTEX document model (BLP-005).

Canonical internal representation for ``.cortex`` artifacts, mirroring the
codec-cortex AST surface that ArqUX consumers already rely on
(``sections``/``entries``/``sigil``/``name``/``value``/``glossary``).

CODEC-CORTEX supplies *format* parsing/rendering only; this model, the
level policy, the selectors and the HCORTEX-READ renderer are ArqUX
semantics.  ``from_codec_v1`` adapts a ``codec_cortex`` 1.0.x ``Document``
into this model so downstream code never touches codec types directly.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SigilDef:
    sigil: str
    name: str
    type: str
    risk: str = "M"
    layer: str = "Semantic"
    description: str = ""
    fields: list[str] | None = None
    needs_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "sigil": self.sigil, "name": self.name, "type": self.type,
            "risk": self.risk, "layer": self.layer,
            "description": self.description, "fields": self.fields,
            "needs_review": self.needs_review,
        }


@dataclass
class TypeDef:
    name: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description}


@dataclass
class MicroDef:
    token: str
    value: str

    def to_dict(self) -> dict[str, Any]:
        return {"token": self.token, "value": self.value}


@dataclass
class AttrsPosContract:
    sigil: str
    fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"sigil": self.sigil, "fields": list(self.fields)}


@dataclass
class Glossary:
    sigils: dict[str, SigilDef] = field(default_factory=dict)
    types: dict[str, TypeDef] = field(default_factory=dict)
    micro: dict[str, MicroDef] = field(default_factory=dict)
    contracts: dict[str, AttrsPosContract] = field(default_factory=dict)
    status_custom: list[str] | None = None
    types_custom: list[str] | None = None

    def add_sigil(self, sigil: SigilDef) -> None:
        self.sigils[sigil.sigil] = sigil

    def add_type(self, t: TypeDef) -> None:
        self.types[t.name] = t

    def add_micro(self, m: MicroDef) -> None:
        self.micro[m.token] = m

    def add_contract(self, c: AttrsPosContract) -> None:
        self.contracts[c.sigil] = c

    def sigil_type(self, sigil: str) -> str | None:
        s = self.sigils.get(sigil)
        return s.type if s else None

    def contract_for(self, sigil: str) -> AttrsPosContract | None:
        return self.contracts.get(sigil)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sigils": {k: v.to_dict() for k, v in self.sigils.items()},
            "types": {k: v.to_dict() for k, v in self.types.items()},
            "micro": {k: v.to_dict() for k, v in self.micro.items()},
            "contracts": {k: v.to_dict() for k, v in self.contracts.items()},
        }


def compute_entry_hash(entry: Entry) -> str:
    if entry.type == "bloque":
        payload = {"sigil": entry.sigil, "name": entry.name,
                   "type": entry.type, "raw": entry.raw}
    else:
        payload = {"sigil": entry.sigil, "name": entry.name,
                   "type": entry.type, "value": entry.value}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def compute_document_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Entry:
    section: str
    sigil: str
    name: str
    type: str
    value: Any
    raw: str = ""
    line_start: int = 0
    line_end: int = 0
    hash: str = ""
    entry_id: str = ""

    def __post_init__(self) -> None:
        if not self.hash:
            self.hash = compute_entry_hash(self)
        if not self.entry_id:
            self.entry_id = self.hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id, "section": self.section,
            "sigil": self.sigil, "name": self.name, "type": self.type,
            "value": self.value, "raw": self.raw,
            "line_start": self.line_start, "line_end": self.line_end,
            "hash": self.hash,
        }


@dataclass
class Section:
    id: str
    title: str = ""
    entries: list[Entry] = field(default_factory=list)
    line_start: int = 0
    comments: list[str] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "title": self.title,
            "entries": [e.to_dict() for e in self.entries],
            "line_start": self.line_start, "comments": list(self.comments),
        }


@dataclass
class CortexDocument:
    meta: dict[str, Any] = field(default_factory=dict)
    glossary: Glossary = field(default_factory=Glossary)
    sections: list[Section] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    @property
    def section_ids(self) -> list[str]:
        return [s.id for s in self.sections]

    def get_section(self, section_id: str) -> Section | None:
        norm = normalize_section_id(section_id)
        for s in self.sections:
            if s.id == norm:
                return s
        return None

    def get_or_create_section(self, section_id: str, title: str = "") -> Section:
        sec = self.get_section(section_id)
        if sec is not None:
            return sec
        sec = Section(id=normalize_section_id(section_id), title=title)
        self.sections.append(sec)
        return sec

    def iter_entries(self):
        for sec in self.sections:
            for e in sec.entries:
                yield sec, e

    def find_entries(self, sigil=None, name=None, section=None) -> list[Entry]:
        out: list[Entry] = []
        for sec, e in self.iter_entries():
            if section is not None and sec.id != normalize_section_id(section):
                continue
            if sigil is not None and e.sigil != sigil:
                continue
            if name is not None and e.name != name:
                continue
            out.append(e)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": dict(self.meta), "glossary": self.glossary.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "diagnostics": list(self.diagnostics),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent,
                          ensure_ascii=False, sort_keys=False)


def normalize_section_id(section_id: str) -> str:
    if section_id is None:
        return "$0"
    s = section_id.strip()
    if not s:
        return "$0"

    def is_section_number(value: str) -> bool:
        parts = value.split(".")
        return bool(parts) and all(part.isdigit() for part in parts)

    if not s.startswith("$"):
        if is_section_number(s.split(":", 1)[0].strip()):
            return "$" + s.split(":", 1)[0].strip()
        return "$" + s
    head = s[1:].split(":", 1)[0].split("·", 1)[0].strip()
    if is_section_number(head):
        return "$" + head
    return s


def _norm_shape(shape: str) -> str:
    """v1 spells the accented type ``relacion``; the canonical ArqUX/codec
    spelling is ``relación``."""
    return {"relacion": "relación"}.get(shape, shape)


def _unwrap_scalar(v: Any) -> Any:
    """codec_cortex 1.0.x ``Scalar`` → plain Python value (recursive)."""
    kind = getattr(v, "kind", None)
    if kind is None:
        return v
    value = getattr(v, "value", v)
    if kind == "list" or isinstance(value, list):
        return [_unwrap_scalar(x) for x in (value or [])]
    return value


def _decode_payload(payload: Any) -> Any:
    """v1 idea payload ``(shape_tag, content)`` → legacy-shaped value.

    ``('attrs', [(key, Scalar), ...])`` → ``dict``; every other shape
    carries its content as the second tuple element (``cuerpo``/``bloque``/
    ``relación`` text).  Scalars are unwrapped recursively.
    """
    if isinstance(payload, tuple) and len(payload) == 2 \
            and isinstance(payload[0], str):
        tag, content = payload
        if tag == "attrs" and isinstance(content, (list, tuple)):
            return {str(k): _unwrap_scalar(s) for k, s in content}
        return _unwrap_scalar(content)
    return _unwrap_scalar(payload)


def from_codec_v1(doc: Any, *, path: str = "<string>") -> CortexDocument:
    """Adapt a ``codec_cortex`` 1.0.x ``Document`` to :class:`CortexDocument`.

    Lossy-by-design at the format edge: v1 does not retain raw entry text
    or parser diagnostics, so ``Entry.raw`` is reconstructed best-effort
    from the payload and ``diagnostics`` starts empty (v1 signals fatal
    problems via ``ParseError`` at parse time).
    """
    out = CortexDocument()
    out.meta = {"path": path, "cortex_version": getattr(doc, "cortex_version", "1.0")}
    g = getattr(doc, "glossary", None)
    if g is not None:
        for sym in getattr(g, "symbols", []) or []:
            sigil = getattr(sym, "sigil", "") or ""
            shape = _norm_shape(getattr(sym, "shape", "attrs") or "attrs")
            # v1 ``contract`` is the shape's positional skeleton (e.g. a
            # generic ``value`` field), NOT the legacy ``$0`` declared-field
            # list — legacy ``SigilDef.fields`` stays None unless the file
            # uses the legacy declaration form.  Positional contracts are
            # only meaningful for ``attrs-pos`` sigils.
            contract_fields = [getattr(f, "name", "") for f in
                               (getattr(sym, "contract", []) or [])]
            sd = SigilDef(
                sigil=sigil,
                name=(sigil.lower() if sigil else ""),
                type=shape,
                fields=None,
                needs_review=bool(getattr(sym, "needs_review", False)),
            )
            out.glossary.add_sigil(sd)
            if shape == "attrs-pos" and contract_fields:
                out.glossary.add_contract(
                    AttrsPosContract(sigil=sigil, fields=contract_fields))
        for t in getattr(g, "types", []) or []:
            name = getattr(t, "name", "")
            if name:
                out.glossary.add_type(TypeDef(name=name,
                                              description=getattr(t, "description", "") or ""))
        for m in getattr(g, "micro", []) or getattr(g, "micros", []) or []:
            token = getattr(m, "token", "")
            if token:
                out.glossary.add_micro(MicroDef(token=token,
                                                value=getattr(m, "value", getattr(m, "expand", "")) or ""))
        for e in getattr(g, "enums", []) or []:
            name = getattr(e, "name", "")
            if name:
                out.glossary.add_type(TypeDef(name=name))
    seen_sections: dict[int, Section] = {}
    for sec in getattr(doc, "sections", []) or []:
        sid = getattr(sec, "id", 0)
        section = Section(id=f"${sid}",
                          title=getattr(sec, "title", "") or "")
        out.sections.append(section)
        seen_sections[sid] = section
        for idea in getattr(sec, "ideas", []) or []:
            iid = getattr(idea, "section", sid)
            target = seen_sections.get(iid, section)
            sigil = getattr(idea, "qualified_symbol", None) or getattr(idea, "symbol", "") or ""
            if "::" in sigil:
                sigil = sigil.split("::", 1)[1]
            value = _decode_payload(getattr(idea, "payload", None))
            shape = _norm_shape(getattr(idea, "shape", "attrs") or "attrs")
            if shape == "bloque" and not isinstance(value, str):
                value = str(value)
            raw = ""
            if isinstance(value, str) and shape in ("cuerpo", "bloque", "relación"):
                raw = value
            elif isinstance(value, dict):
                raw = "{" + ", ".join(f"{k}:{v}" for k, v in value.items()) + "}"
            entry = Entry(
                section=target.id, sigil=sigil,
                name=getattr(idea, "name", "") or "",
                type=shape, value=value, raw=raw,
                line_start=getattr(idea, "source_line", 0) or 0,
            )
            target.entries.append(entry)
    return out


def parse_native(text: str, *, path: str = "<string>") -> CortexDocument:
    """Parse ``text`` into the ArqUX model.

    Uses ``codec_cortex`` 1.0.x (a core dependency since arqux 1.0.0) and
    always returns this module's :class:`CortexDocument`. The legacy
    ``cortex`` 0.6.x fallback was removed with the 1.0 line: an absent
    codec is a broken install and fails closed, never a silent downgrade
    to a different dialect's semantics.
    """
    try:
        from codec_cortex.dispatcher import parse_cortex as _v1_parse
    except Exception as exc:
        raise RuntimeError("no CORTEX codec available") from exc
    return from_codec_v1(_v1_parse(text), path=path)
