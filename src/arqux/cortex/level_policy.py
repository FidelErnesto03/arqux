# SPDX-License-Identifier: MPL-2.0
"""ArqUX level policy — native CORTEX semantic validation (BLP-005).

Reimplementation of the codec-cortex validation semantics *as ArqUX
policy* over :mod:`arqux.cortex.model`.  CODEC-CORTEX remains the format
dependency (parse/canonicalize); every rule below is ArqUX-owned.

Coverage (mirrors the legacy ``validate`` contract):

- unknown sigils → ``I001`` info (auto-register, ``needs_review``) or
  ``E003`` under ``strict``
- undeclared sigil types → ``I002`` info (auto-register)
- ``attrs-pos`` sigil without positional contract → ``E007`` error
- required/optional field checks → ``W001`` / ``I003``
- ``status`` / ``severity`` / ``priority`` vocabularies → ``W002``–``W004``
- duplicate ``sigil:name`` within a section → ``E008`` error
- level policy: ``E023``/``E024``/``E025``/``E027``/``E029``/``E031``/
  ``E032``/``E033``/``E034`` (document-kind inference, live-state rules,
  ``survive`` domain, attrs-pos arity, critical-sigil completeness,
  secret scanning)
- ``strict=True`` promotes every warning to an error

BLP-020 exemption (Architect policy 2026-11-02): ``LNG`` entries typed
``behavioral`` inside ``(BEHAVIORAL )?LESSONS`` sections of an artifact
declaring ``usage:"identity"`` are curated contract content, not live
state — ``E023`` is scoped out for exactly those entries.
"""

from __future__ import annotations

import os
import re
from typing import Any

from .model import CortexDocument, Entry, Glossary, SigilDef

# ---------------------------------------------------------------------------
# Diagnostic codes (stable contract shared with codec-cortex diagnostics)
# ---------------------------------------------------------------------------

E003_UNKNOWN_SIGIL = "E003_UNKNOWN_SIGIL"
E007_ATTRS_POS_CONTRACT_MISSING = "E007_ATTRS_POS_CONTRACT_MISSING"
E008_DUPLICATE_ENTRY = "E008_DUPLICATE_ENTRY"
E023_LEVEL1_LIVE_STATE = "E023_LEVEL1_LIVE_STATE"
E024_LEVEL2_MISSING_FOCUS = "E024_LEVEL2_MISSING_FOCUS"
E025_INVALID_SURVIVE = "E025_INVALID_SURVIVE"
E027_ATTRS_POS_ARITY = "E027_ATTRS_POS_ARITY"
E029_LEVEL3_LIVE_STATE = "E029_LEVEL3_LIVE_STATE"
E031_SECRET_NOT_BYPASSABLE = "E031_SECRET_NOT_BYPASSABLE"
E032_CRITICAL_SIGIL_INCOMPLETE = "E032_CRITICAL_SIGIL_INCOMPLETE"
E033_ZERO_SECTION_MEMORY_ENTRY = "E033_ZERO_SECTION_MEMORY_ENTRY"
E034_CRITICAL_REQUIRED_FIELD_EMPTY = "E034_CRITICAL_REQUIRED_FIELD_EMPTY"

# Canonical vocabularies (CODEC-CORTEX §4/§6 contract)
CANONICAL_TYPES: frozenset[str] = frozenset(
    {"attrs", "attrs-pos", "cuerpo", "bloque", "relación"})
ALLOWED_STATUS: frozenset[str] = frozenset({
    "current", "specification", "planned", "future",
    "experimental", "deprecated", "blocked", "done",
})
ALLOWED_SEVERITY: frozenset[str] = frozenset({"blocking", "warning", "info"})
ALLOWED_PRIORITY: frozenset[str] = frozenset({"high", "medium", "low"})
ALLOWED_SURVIVE: frozenset[str] = frozenset({"min", "recovery", "work", "full"})

#: Required fields per critical sigil (legacy §6 contract).
REQUIRED_FIELDS: dict[str, list[str]] = {
    "FCS":   ["what", "priority", "status", "survive"],
    "OBJ":   ["goal", "status", "success", "survive"],
    "WRK":   ["phase", "current", "blocked", "survive"],
    "STP":   ["action", "reason", "owner", "status", "survive"],
    "CNST":  ["rule", "severity", "survive"],
    "CLAIM": ["statement", "evidence", "status"],
    "LIM":   ["limit", "scope", "status"],
    "RSK":   ["risk", "impact", "mitigation", "status", "survive"],
    "AUD":   ["event", "evidence", "result", "date"],
    "SES":   ["input", "output", "outcome", "date"],
    "LNG":   ["type", "cause", "lesson", "prevention"],
    "KNW":   ["topic", "content", "status"],
}

#: Sigils constituting live working state.
LIVE_WORKING_SIGILS = frozenset({"FCS", "OBJ", "WRK", "STP", "NXT"})
LIVE_SESSION_SIGILS = frozenset({"SES", "LNG"})
LIVE_STATE_SIGILS = LIVE_WORKING_SIGILS | LIVE_SESSION_SIGILS
GLOSSARY_ENTRY_SIGILS = frozenset({"GSIG", "GTYP", "GMIC", "GCON"})

NULL_LIKE = frozenset({
    "null", "none", "nil", "undefined", "n/a", "n.a.", "na",
    "tbd", "todo", "tbc", "???", "?", "-", "--",
})

_SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)\b(api[_-]?key)\b\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}"), "api_key"),
    (re.compile(r"(?i)\b(password|passwd|pwd)\b\s*[:=]\s*[\"']?[^\s\"']{4,}"), "password"),
    (re.compile(r"(?i)\b(token|secret|bearer)\b\s*[:=]\s*[\"']?[A-Za-z0-9_\-\.]{16,}"), "token"),
    (re.compile(r"(?i)\b(aws[_-]?secret[_-]?access[_-]?key)\b\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}"), "aws_secret"),
    (re.compile(r"(?i)\b(private[_-]?key)\b\s*[:=]\s*[\"']?-----BEGIN"), "private_key"),
    (re.compile(r"https?://[^/\s]+:[^@/\s]+@"), "url_with_credentials"),
]

# BLP-020: identity contracts may curate behavioral lessons as contract
# content, not live state.
_IDENTITY_LESSONS_TITLE = re.compile(r"^(BEHAVIORAL\s+)?LESSONS$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Schema resolution ($0 wins, canonical fallback)
# ---------------------------------------------------------------------------

class SchemaResolver:
    #: Parity with the ArqUX runtime shim on codec-cortex <=0.6.2
    #: (``state/__init__.py`` sets ``SchemaResolver.ALWAYS_REQUIRED =
    #: frozenset()``): in CODEC-CORTEX the entry name lives in the key
    #: ``SIGIL:name``, never as a ``name`` attribute, so ``name`` is NOT
    #: an always-required field.  ``errors.REQUIRED_FIELDS`` does not
    #: exist in the codec (it lives in ``validator.py``), so the
    #: canonical-optional fallback never engages either: a sigil with
    #: declared ``$0`` fields yields ``(declared, ∅)``; anything else
    #: yields ``(∅, ∅)`` and rule 2 skips it.
    ALWAYS_REQUIRED: frozenset[str] = frozenset()

    def __init__(self, glossary: Glossary | None = None) -> None:
        self.glossary = glossary

    def required_fields(self, sigil: str) -> tuple[set[str], set[str]]:
        if self.glossary and sigil in self.glossary.sigils:
            sd = self.glossary.sigils[sigil]
            if sd.fields:
                return (set(sd.fields), set())
        return (set(self.ALWAYS_REQUIRED), set())

    def valid_statuses(self) -> frozenset[str]:
        if self.glossary and self.glossary.status_custom:
            return frozenset(self.glossary.status_custom)
        return ALLOWED_STATUS

    def valid_types(self) -> frozenset[str]:
        base = CANONICAL_TYPES
        if self.glossary:
            declared = frozenset(self.glossary.types)
            custom = frozenset(self.glossary.types_custom or [])
            return base | declared | custom
        return base

    def has_fields(self, sigil: str) -> bool:
        if self.glossary and sigil in self.glossary.sigils:
            sd = self.glossary.sigils[sigil]
            return sd.fields is not None and len(sd.fields) > 0
        return False

    def needs_review(self, sigil: str) -> bool:
        if self.glossary and sigil in self.glossary.sigils:
            return self.glossary.sigils[sigil].needs_review
        return False


def ensure_in_glossary(
    doc: CortexDocument,
    *,
    sigil: str | None = None,
    status: str | None = None,
    type_: str | None = None,
    definition: dict[str, Any] | None = None,
) -> None:
    """Auto-register undeclared glossary elements (``needs_review``)."""
    if sigil is not None and sigil not in doc.glossary.sigils:
        needs_review = definition is None
        name = (definition or {}).get("name", sigil.lower())
        type_val = (definition or {}).get("type", "attrs")
        fields_raw = (definition or {}).get("fields")
        fields_list = None
        if isinstance(fields_raw, str):
            fields_list = [f.strip() for f in
                           fields_raw.replace("[", "").replace("]", "").split(",")]
        elif isinstance(fields_raw, (list, tuple)):
            fields_list = [str(f) for f in fields_raw]
        doc.glossary.add_sigil(SigilDef(
            sigil=sigil, name=name, type=type_val,
            risk=(definition or {}).get("risk", "M"),
            layer=(definition or {}).get("layer", "Semantic"),
            description=(definition or {}).get("description", "TODO: needs_review"),
            fields=fields_list, needs_review=needs_review))
    if status is not None and status not in ALLOWED_STATUS:
        if doc.glossary.status_custom is None:
            doc.glossary.status_custom = []
        if status not in doc.glossary.status_custom:
            doc.glossary.status_custom.append(status)
    if type_ is not None and type_ not in CANONICAL_TYPES:
        if doc.glossary.types_custom is None:
            doc.glossary.types_custom = []
        if type_ not in doc.glossary.types_custom:
            doc.glossary.types_custom.append(type_)


# ---------------------------------------------------------------------------
# Level policy (document-kind inference + cognitive governance)
# ---------------------------------------------------------------------------

def _is_field_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip().lower()
        return stripped == "" or stripped in NULL_LIKE
    return False


def _is_live_entry(entry: Entry) -> bool:
    if entry.sigil not in LIVE_STATE_SIGILS:
        return False
    if not isinstance(entry.value, dict):
        return True
    nature = entry.value.get("nature", "")
    if isinstance(nature, str) and nature in (
        "example", "template", "non_operational", "contract", "specification",
    ):
        return False
    status = entry.value.get("status", "")
    return status not in ("specification", "planned", "future", "deprecated")


class DocumentKind:
    def __init__(self, kind: str, source: str) -> None:
        self.kind = kind
        self.source = source

    def __str__(self) -> str:
        return f"{self.kind} (inferred via {self.source})"


def infer_document_kind(doc: CortexDocument, path: str | None = None) -> DocumentKind:
    for _sec, entry in doc.iter_entries():
        if entry.sigil != "IDN" or not isinstance(entry.value, dict):
            continue
        kind_val = entry.value.get("kind")
        if isinstance(kind_val, str) and kind_val in ("skill", "brain", "package"):
            return DocumentKind(kind=kind_val, source="idn_attr")
        if entry.name == "skill":
            return DocumentKind(kind="skill", source="idn_attr")
        if entry.name == "package":
            return DocumentKind(kind="package", source="idn_attr")
        if entry.name == "agent":
            return DocumentKind(kind="brain", source="idn_attr")
    if path:
        basename = os.path.basename(path).lower()
        if basename == "brain.cortex" or basename.startswith("brain."):
            return DocumentKind(kind="brain", source="filename")
        if basename == "skill.cortex" or basename.startswith("skill."):
            return DocumentKind(kind="skill", source="filename")
        if basename == "package.cortex" or basename.startswith("package."):
            return DocumentKind(kind="package", source="filename")
    sigils_present = {e.sigil for _, e in doc.iter_entries()}
    if "WRK" in sigils_present and "FCS" in sigils_present:
        return DocumentKind(kind="brain", source="sigils")
    if "AXM" in sigils_present and "WRK" not in sigils_present:
        return DocumentKind(kind="skill", source="sigils")
    if "CLAIM" in sigils_present and "LIM" in sigils_present and "WRK" not in sigils_present:
        return DocumentKind(kind="package", source="sigils")
    return DocumentKind(kind="generic", source="default")


def _extract_body(raw: str) -> str:
    start = raw.find("{")
    if start == -1:
        return ""
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start + 1:i]
    return raw[start + 1:]


def _scan_for_secrets(doc: CortexDocument) -> list[dict]:
    findings: list[dict] = []
    for sec, entry in doc.iter_entries():
        texts: list[str] = []
        if isinstance(entry.value, dict):
            for k, v in entry.value.items():
                if isinstance(v, str):
                    texts.append(f"{k}={v}")
        elif isinstance(entry.value, str):
            texts.append(entry.value)
        texts.append(entry.raw or "")
        for text in texts:
            for pattern, label in _SECRET_PATTERNS:
                if pattern.search(text):
                    findings.append({
                        "code": E031_SECRET_NOT_BYPASSABLE,
                        "message": (
                            f"possible {label} in clear text in "
                            f"{entry.sigil}:{entry.name}; use "
                            "REF:secret{provider:..., key:...} instead — "
                            "this error is NOT bypassable with --force"),
                        "line": entry.line_start,
                        "section": sec.id,
                        "sigil": entry.sigil,
                        "entry": entry.name,
                        "severity": "error",
                        "bypassable": False,
                    })
                    break
            else:
                continue
            break
    return findings


def validate_level_policy(
    doc: CortexDocument,
    kind: DocumentKind | None = None,
) -> list[dict]:
    """Run the E0xx cognitive-governance rules; return diagnostic dicts."""
    if kind is None:
        kind = infer_document_kind(doc, doc.meta.get("path"))
    findings: list[dict] = []

    # $0 section integrity — structural metadata, never working memory.
    for sec in doc.sections:
        if sec.id != "$0":
            continue
        for entry in sec.entries:
            if entry.sigil in GLOSSARY_ENTRY_SIGILS:
                continue
            findings.append({
                "code": E033_ZERO_SECTION_MEMORY_ENTRY,
                "message": (
                    f"$0 MUST NOT contain operational entries; found "
                    f"{entry.sigil}:{entry.name} in $0.  $0 is structural "
                    "metadata only (SKILL.md §4.1).  Move operational "
                    "entries to $1 or later sections."),
                "section": "$0",
                "sigil": entry.sigil,
                "entry": entry.name,
                "severity": "error",
                "bypassable": False,
            })

    # Nivel 1 (skill): no live state.
    if kind.kind == "skill":
        for sec, entry in doc.iter_entries():
            if sec.id == "$0" or not _is_live_entry(entry):
                continue
            if entry.sigil in LIVE_STATE_SIGILS:
                findings.append({
                    "code": E023_LEVEL1_LIVE_STATE,
                    "message": (
                        f"Nivel 1 (skill) MUST NOT contain live state "
                        f"sigil {entry.sigil}:{entry.name}; only "
                        "contracts/examples allowed"),
                    "line": entry.line_start, "section": sec.id,
                    "sigil": entry.sigil, "entry": entry.name,
                    "severity": "error", "bypassable": False,
                })

    # Nivel 2 (brain): ≥1 active FCS and ≥1 active OBJ outside $0.
    if kind.kind == "brain":
        active_status = {"current", "blocked"}
        has_fcs = has_obj = False
        for sec, entry in doc.iter_entries():
            if sec.id == "$0" or not isinstance(entry.value, dict):
                continue
            if (entry.sigil == "FCS"
                    and entry.value.get("status") in active_status
                    and not _is_field_empty(entry.value.get("what"))):
                has_fcs = True
            elif (entry.sigil == "OBJ"
                    and entry.value.get("status") in active_status
                    and not _is_field_empty(entry.value.get("goal"))):
                has_obj = True
        if not has_fcs:
            findings.append({
                "code": E024_LEVEL2_MISSING_FOCUS,
                "message": ("Nivel 2 (brain) MUST have at least one active "
                            "FCS entry (status=current|blocked; 'done' is a "
                            "closed state, not active)"),
                "section": "$3", "sigil": "FCS",
                "severity": "error", "bypassable": False,
            })
        if not has_obj:
            findings.append({
                "code": E024_LEVEL2_MISSING_FOCUS,
                "message": ("Nivel 2 (brain) MUST have at least one active "
                            "OBJ entry (status=current|blocked; 'done' is a "
                            "closed state, not active)"),
                "section": "$4", "sigil": "OBJ",
                "severity": "error", "bypassable": False,
            })

    # Nivel 3 (package): no live state.
    if kind.kind == "package":
        for sec, entry in doc.iter_entries():
            if sec.id == "$0" or not _is_live_entry(entry):
                continue
            if entry.sigil in LIVE_STATE_SIGILS:
                findings.append({
                    "code": E029_LEVEL3_LIVE_STATE,
                    "message": (f"Nivel 3 (package) MUST NOT contain live "
                                f"state sigil {entry.sigil}:{entry.name}"),
                    "line": entry.line_start, "section": sec.id,
                    "sigil": entry.sigil, "entry": entry.name,
                    "severity": "error", "bypassable": False,
                })

    # survive attribute domain.
    for sec, entry in doc.iter_entries():
        if not isinstance(entry.value, dict):
            continue
        survive = entry.value.get("survive")
        if survive is None:
            continue
        if not isinstance(survive, str) or survive not in ALLOWED_SURVIVE:
            findings.append({
                "code": E025_INVALID_SURVIVE,
                "message": (f"{entry.sigil}:{entry.name} survive={survive!r} "
                            f"not in {sorted(ALLOWED_SURVIVE)}"),
                "line": entry.line_start, "section": sec.id,
                "sigil": entry.sigil, "entry": entry.name,
                "severity": "error",
            })

    # attrs-pos arity (needs raw body).
    for sec, entry in doc.iter_entries():
        if entry.type != "attrs-pos":
            continue
        contract = doc.glossary.contract_for(entry.sigil)
        if contract is None:
            continue
        parts = _extract_body(entry.raw or "").split("|")
        expected = len(contract.fields)
        if len(parts) > expected:
            findings.append({
                "code": E027_ATTRS_POS_ARITY,
                "message": (
                    f"{entry.sigil}:{entry.name} attrs-pos has {len(parts)} "
                    f"positional values but contract declares {expected} "
                    f"fields ({', '.join(contract.fields)}); excess values "
                    "silently dropped"),
                "line": entry.line_start, "section": sec.id,
                "sigil": entry.sigil, "entry": entry.name,
                "severity": "error",
            })

    # Critical-sigil completeness + semantic emptiness.
    resolver = SchemaResolver(doc.glossary)
    critical = frozenset(REQUIRED_FIELDS.keys())
    for sec, entry in doc.iter_entries():
        if entry.sigil not in critical or not isinstance(entry.value, dict):
            continue
        required = (resolver.required_fields(entry.sigil)[0]
                    if resolver.has_fields(entry.sigil)
                    else REQUIRED_FIELDS[entry.sigil])
        missing = [f for f in required if f not in entry.value]
        if missing:
            findings.append({
                "code": E032_CRITICAL_SIGIL_INCOMPLETE,
                "message": (f"{entry.sigil}:{entry.name} missing required "
                            f"fields {missing}; critical sigils MUST be "
                            "complete to persist (SKILL.md §6)"),
                "line": entry.line_start, "section": sec.id,
                "sigil": entry.sigil, "entry": entry.name,
                "severity": "error", "bypassable": False,
            })
        empty = [f for f in required
                 if f in entry.value and _is_field_empty(entry.value[f])]
        if empty:
            findings.append({
                "code": E034_CRITICAL_REQUIRED_FIELD_EMPTY,
                "message": (f"{entry.sigil}:{entry.name} has empty required "
                            f"fields {empty}; critical fields MUST have "
                            "non-empty values (SKILL.md §6)."),
                "line": entry.line_start, "section": sec.id,
                "sigil": entry.sigil, "entry": entry.name,
                "severity": "error", "bypassable": False,
            })

    findings.extend(_scan_for_secrets(doc))
    return findings


# ---------------------------------------------------------------------------
# BLP-020 exemption — curated behavioral lessons in identity contracts
# ---------------------------------------------------------------------------

def _declares_identity_usage(doc: CortexDocument) -> bool:
    for _sec, entry in doc.iter_entries():
        if entry.sigil != "ARQX" or not isinstance(entry.value, dict):
            continue
        if str(entry.value.get("usage", "")).casefold() == "identity":
            return True
    return False


def drop_identity_lesson_e023(doc: CortexDocument,
                              diagnostics: list[dict]) -> list[dict]:
    """Drop ``E023`` raised against curated behavioral lessons (BLP-020)."""
    if not diagnostics or not _declares_identity_usage(doc):
        return diagnostics
    lesson_sections = {
        sec.id for sec in doc.sections
        if _IDENTITY_LESSONS_TITLE.match(str(sec.title or "").strip())
    }
    if not lesson_sections:
        return diagnostics
    behavioral = {
        entry.name for sec in doc.sections if sec.id in lesson_sections
        for entry in sec.entries
        if entry.sigil == "LNG" and isinstance(entry.value, dict)
        and str(entry.value.get("type", "")).casefold() == "behavioral"
    }
    if not behavioral:
        return diagnostics
    return [
        d for d in diagnostics
        if not (d.get("code") == E023_LEVEL1_LIVE_STATE
                and d.get("sigil") == "LNG"
                and d.get("section") in lesson_sections
                and d.get("entry") in behavioral)
    ]


# ---------------------------------------------------------------------------
# Public validate() — codec-compatible signature
# ---------------------------------------------------------------------------

def is_protected_entry(entry: Entry) -> bool:
    if entry.sigil in ("FCS", "OBJ", "CNST") and isinstance(entry.value, dict):
        if entry.value.get("severity") == "blocking":
            return True
        if entry.value.get("survive") == "min":
            return True
    return False


def validate(
    doc: CortexDocument,
    strict: bool = False,
    kind: DocumentKind | None = None,
) -> list[dict]:
    """Run all validators; return diagnostic dicts (codec-compatible)."""
    findings: list[dict] = list(doc.diagnostics)
    resolver = SchemaResolver(doc.glossary)
    resolver_statuses = resolver.valid_statuses()
    resolver_types = resolver.valid_types()

    # 1. Sigil/type declaration checks.
    for sec, entry in doc.iter_entries():
        if entry.sigil in GLOSSARY_ENTRY_SIGILS:
            continue
        sigil_missing = entry.sigil not in doc.glossary.sigils
        auto_added = (
            not sigil_missing
            and doc.glossary.sigils[entry.sigil].needs_review)
        if sigil_missing or (strict and auto_added):
            if strict:
                findings.append({
                    "code": E003_UNKNOWN_SIGIL,
                    "message": (f"sigil {entry.sigil!r} (entry {entry.name!r}) "
                                "not declared in $0 — strict mode rejects "
                                "undeclared sigils"),
                    "line": entry.line_start, "section": sec.id,
                    "sigil": entry.sigil, "entry": entry.name,
                    "severity": "error",
                })
            else:
                ensure_in_glossary(doc, sigil=entry.sigil)
                findings.append({
                    "code": "I001_UNDECLARED_SIGIL",
                    "message": (f"sigil {entry.sigil!r} (entry {entry.name!r}) "
                                "not declared in $0 — auto-registered with "
                                "needs_review"),
                    "line": entry.line_start, "section": sec.id,
                    "sigil": entry.sigil, "entry": entry.name,
                    "severity": "info",
                })
            continue
        sd = doc.glossary.sigils[entry.sigil]
        if sd.type not in resolver_types:
            ensure_in_glossary(doc, type_=sd.type)
            findings.append({
                "code": "I002_UNDECLARED_TYPE",
                "message": (f"type {sd.type!r} (sigil {entry.sigil!r}) "
                            "auto-registered in $0"),
                "line": entry.line_start, "section": sec.id,
                "sigil": entry.sigil, "entry": entry.name,
                "severity": "info",
            })
        if (sd.type == "attrs-pos"
                and doc.glossary.contract_for(entry.sigil) is None
                and not isinstance(entry.value, dict)):
            findings.append({
                "code": E007_ATTRS_POS_CONTRACT_MISSING,
                "message": (f"attrs-pos sigil {entry.sigil!r} has no "
                            "positional contract"),
                "line": entry.line_start, "section": sec.id,
                "sigil": entry.sigil, "entry": entry.name,
                "severity": "error",
            })

    # 2. Required/optional fields for critical sigils.
    for sec, entry in doc.iter_entries():
        required, optional = resolver.required_fields(entry.sigil)
        if not required and not optional:
            continue
        if not isinstance(entry.value, dict):
            findings.append({
                "code": "W001_MISSING_FIELDS",
                "message": (f"{entry.sigil}:{entry.name} value is not a dict; "
                            "cannot check fields"),
                "line": entry.line_start, "section": sec.id,
                "sigil": entry.sigil, "entry": entry.name,
                "severity": "warning",
            })
            continue
        missing = [f for f in required if f not in entry.value]
        if missing:
            findings.append({
                "code": "W001_MISSING_FIELDS",
                "message": (f"{entry.sigil}:{entry.name} missing required "
                            f"fields: {missing}"),
                "line": entry.line_start, "section": sec.id,
                "sigil": entry.sigil, "entry": entry.name,
                "severity": "warning",
            })
        optional_missing = [f for f in optional if f not in entry.value]
        if optional_missing:
            findings.append({
                "code": "I003_OPTIONAL_FIELDS",
                "message": (f"{entry.sigil}:{entry.name} optional fields "
                            "missing (canonical but not in $0): "
                            f"{optional_missing}"),
                "line": entry.line_start, "section": sec.id,
                "sigil": entry.sigil, "entry": entry.name,
                "severity": "info",
            })

    # 3. status / severity / priority vocabularies.
    for sec, entry in doc.iter_entries():
        if not isinstance(entry.value, dict):
            continue
        status = entry.value.get("status")
        if isinstance(status, str) and status not in resolver_statuses:
            findings.append({
                "code": "W002_INVALID_STATUS",
                "message": (f"{entry.sigil}:{entry.name} status={status!r} "
                            f"not in {sorted(resolver_statuses)}"),
                "line": entry.line_start, "section": sec.id,
                "sigil": entry.sigil, "entry": entry.name,
                "severity": "warning",
            })
        severity = entry.value.get("severity")
        if isinstance(severity, str) and severity not in ALLOWED_SEVERITY:
            findings.append({
                "code": "W003_INVALID_SEVERITY",
                "message": (f"{entry.sigil}:{entry.name} severity={severity!r} "
                            f"not in {sorted(ALLOWED_SEVERITY)}"),
                "line": entry.line_start, "section": sec.id,
                "sigil": entry.sigil, "entry": entry.name,
                "severity": "warning",
            })
        priority = entry.value.get("priority")
        if isinstance(priority, str) and priority not in ALLOWED_PRIORITY:
            findings.append({
                "code": "W004_INVALID_PRIORITY",
                "message": (f"{entry.sigil}:{entry.name} priority={priority!r} "
                            f"not in {sorted(ALLOWED_PRIORITY)}"),
                "line": entry.line_start, "section": sec.id,
                "sigil": entry.sigil, "entry": entry.name,
                "severity": "warning",
            })

    # 4. Duplicate entries within a section.
    seen: dict[str, list[str]] = {}
    for sec, entry in doc.iter_entries():
        if entry.sigil in GLOSSARY_ENTRY_SIGILS:
            continue
        key = f"{sec.id}::{entry.sigil}::{entry.name}"
        if key in seen:
            findings.append({
                "code": E008_DUPLICATE_ENTRY,
                "message": (f"duplicate entry {entry.sigil}:{entry.name} "
                            f"in {sec.id}"),
                "line": entry.line_start, "section": sec.id,
                "sigil": entry.sigil, "entry": entry.name,
                "severity": "error",
            })
        seen.setdefault(key, []).append(entry.name)

    # 5. Level policy + secret scanning.
    findings.extend(validate_level_policy(doc, kind=kind))

    # 6. BLP-020: curated behavioral lessons in identity contracts.
    findings = drop_identity_lesson_e023(doc, findings)

    # 7. Strict mode promotes warnings.
    if strict:
        for f in findings:
            if f.get("severity") == "warning":
                f["severity"] = "error"
                f["message"] = f"[strict] {f.get('message', '')}"

    # Deduplicate by (code, line, sigil, entry, message).
    seen_keys = set()
    deduped: list[dict] = []
    for f in findings:
        k = (f.get("code"), f.get("line"), f.get("sigil"),
             f.get("entry"), f.get("message"))
        if k in seen_keys:
            continue
        seen_keys.add(k)
        deduped.append(f)
    return deduped


def is_valid(doc: CortexDocument, strict: bool = False,
             kind: DocumentKind | None = None) -> bool:
    return not any(f.get("severity") == "error"
                   for f in validate(doc, strict=strict, kind=kind))
