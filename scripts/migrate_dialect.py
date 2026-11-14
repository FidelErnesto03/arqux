#!/usr/bin/env python3
"""Migrate .cortex artifacts to the CORTEX 1.0 dialect — safely.

BLP-001 (CYCLE-16) instrument. The contract is read -> transform -> verify -> write:

  1. read the original (never modified in place during transformation)
  2. transform into a temp file
  3. parse the TEMP file with codec-cortex 1.0
  4. write the original ONLY if step 3 passed

This is deliberately the inverse of codec-cortex's own ``slotmigrate to-1.0``,
which writes first and parses afterwards (leaving the original corrupted when
the parse fails).

Usage:
    python scripts/migrate_dialect.py --root /home/vatrox/workspace --only brains --dry-run
    python scripts/migrate_dialect.py --root /home/vatrox/workspace --only brains --apply
    python scripts/migrate_dialect.py --root /home/vatrox/workspace --only identities --apply --report r.txt
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

FORMAT_LINE = "$0:format{cortex:1.0, encoding:UTF-8}"

# Category -> path predicates (relative to root). First match wins.
CATEGORIES: dict[str, tuple[str, ...]] = {
    "brains": ("ARQUX/.arqux/brain.cortex", "Proyecto_X/.arqux/brain.cortex", ".arqux/meta-brain.cortex"),
    "identities": ("identities/",),
    "templates": ("templates/",),
    "cycles": ("/cycles/CYCLE-",),
    "tasks": ("/tasks/T-",),
    "misc": ("issues/", "handoffs/", "audits/", "guides.cortex", "UPGRADE.cortex"),
    # Workspace-level registries directly under a .arqux/ root: the project
    # registry, the agent registry, the shared context and the learning policy.
    # They were absent from every category, so the migration reported success
    # while silently leaving four artifacts unconverted.
    "workspace": (
        "projects.cortex",
        "agents.cortex",
        "context.cortex",
        "learn-policies.cortex",
    ),
}


def classify(rel: str) -> str | None:
    """Return the artifact category for a relative path. Most specific wins."""
    if rel in CATEGORIES["brains"]:
        return "brains"
    # Tasks and cycles both live under /cycles/CYCLE-*/; the task segment is more
    # specific and must win, or a --only cycles run silently rewrites tasks.
    if "/tasks/" in rel:
        return "tasks"
    if "/blueprints/" in rel:
        return None
    for name in ("identities", "templates", "cycles", "misc", "workspace"):
        if any(p in rel for p in CATEGORIES[name]):
            return name
    return None


def _fix_format_line(text: str) -> str:
    """Repair `$0: format{` and normalise the dialect declaration to 1.0."""
    # Fix the space-after-colon typo that G010 rejects.
    text = re.sub(r"^([ \t]*)\$0:\s+format\{", r"\1$0:format{", text, flags=re.M)

    existing = re.search(r"^[ \t]*\$0:format\{[^}]*\}", text, flags=re.M)
    if existing:
        return text[: existing.start()] + FORMAT_LINE + text[existing.end():]

    # No declaration: insert right after the $0 line (the kernel header).
    m = re.search(r"^[ \t]*\$0[ \t]*$", text, flags=re.M)
    if m:
        insert_at = m.end()
        return text[:insert_at] + "\n" + FORMAT_LINE + text[insert_at:]
    return text


def _open_contracts(text: str, sigils: set[str]) -> str:
    """Rewrite sigil declarations in ``$0`` to be open and CORTEX 1.0 valid.

    Only lines inside the ``$0`` kernel are declarations. Entries elsewhere that
    happen to look like ``SIGIL:name{...}`` are DATA, and rewriting them corrupts
    the document (they became bogus declarations and left the real sigil use
    undeclared -> I001).
    """
    lines = text.split("\n")
    in_kernel = False
    out: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped == "$0":
            in_kernel = True
            out.append(line)
            continue
        if re.match(r"^\$0:format\{", stripped):
            # The format declaration lives INSIDE $0 — it does not close it.
            in_kernel = True
            out.append(line)
            continue
        if re.match(r"^\$\d+(\.\d+)?:", stripped):
            in_kernel = False
            out.append(line)
            continue

        if in_kernel:
            m = re.match(r"^([A-Z][A-Z0-9_]{1,5}):([a-z_][a-z0-9_]*)\{([^}]*)\}", stripped)
            if m and m.group(1) in sigils:
                sigil, name, body = m.groups()
                body = re.sub(r'fields\s*:\s*"[^"]*"', 'fields:"value:any?"', body)
                body = re.sub(r"focus\s*:\s*[^,}]+", 'focus:"value"', body)
                body = re.sub(r",?\s*open\s*:\s*(true|false)", "", body)
                body = body.rstrip().rstrip(",").rstrip()
                out.append(f"{sigil}:{name}{{{body}, open:true}}")
                continue

        out.append(line)

    return "\n".join(out)


def _translate_gsig(text: str) -> str:
    """Translate the legacy GSIG schema into CORTEX declarations.

    GSIG:{name,risk,layer,description} -> SIGIL:name{type,weight,focus,desc,open}
    `layer` has no CORTEX 1.0 equivalent; it is preserved as an extra field so it
    is not lost silently (BLP-001 §7.4).
    """
    def fix(m: re.Match[str]) -> str:
        body = m.group(1)
        name = re.search(r'name\s*:\s*"([^"]+)"', body)
        risk = re.search(r'risk\s*:\s*"([^"]+)"', body)
        layer = re.search(r'layer\s*:\s*"([^"]+)"', body)
        desc = re.search(r'description\s*:\s*"([^"]+)"', body)
        if not name:
            return m.group(0)
        sigil = name.group(1).upper()[:5]
        weight = risk.group(1) if risk else "B"
        parts = [
            'type:"attrs"',
            f'weight:"{weight}"',
            'focus:"value"',
            'fields:"value:any?"',
        ]
        if desc:
            parts.append(f'desc:"{desc.group(1)}"')
        if layer:
            parts.append(f'layer:"{layer.group(1)}"')
        parts.append("open:true")
        return f"{sigil}:{name.group(1)}{{{', '.join(parts)}}}"

    return re.sub(r"^GSIG:\{[^}]*\{?\}?\}", lambda m: fix(m), text, flags=re.M)


def _translate_gsig_text(text: str) -> str:
    """Translate ``GSIG:<SIGIL>{...}`` lines into CORTEX declarations.

    The sigil is the token that FOLLOWS ``GSIG:`` (``GSIG:IDN{...}`` declares
    ``IDN``). Deriving it from the ``name`` field instead invented bogus sigils
    (``IDENT``, ``AXIOM``, ``LEARN``) and left the real ones undeclared.

    A GSIG whose sigil is never used outside ``$0`` is DROPPED rather than
    declared: a packaged identity must not announce capabilities it does not
    carry (``test_published_identity_is_a_basic_contract`` rejects a bare
    ``LNG:`` declaration in an identity that ships no lessons).
    """
    lines = text.splitlines()

    # Sigils actually used as entries outside the kernel.
    in_kernel = False
    used: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if stripped == "$0" or re.match(r"^\$0:format\{", stripped):
            in_kernel = True
            continue
        if re.match(r"^\$\d+(\.\d+)?:", stripped):
            in_kernel = False
            continue
        if not in_kernel and not stripped.startswith("#"):
            m = re.match(r"^([A-Z][A-Z0-9_]{1,5}):[A-Za-z0-9_.\-]+\{", stripped)
            if m:
                used.add(m.group(1))

    out = []
    for line in lines:
        m = re.match(r"^(\s*)GSIG:([A-Z][A-Z0-9_]{1,5})\{(.*)\}\s*$", line)
        if m:
            sigil, body = m.group(2), m.group(3)
            if sigil not in used:
                continue  # declared but never exercised: do not advertise it
            risk = re.search(r'risk\s*:\s*"([^"]+)"', body)
            layer = re.search(r'layer\s*:\s*"([^"]+)"', body)
            desc = re.search(r'description\s*:\s*"([^"]+)"', body)

            weight = risk.group(1) if risk else "B"
            # The sigil is declared OPEN, so the field list must not constrain:
            # 1.0 still enforces every name in `fields` as REQUIRED (I008), and a
            # legacy list like ``name,action,...,alt_action`` fails on entries that
            # omit any of them. An open contract takes the least committing form.
            parts = ['type:"attrs"', f'weight:"{weight}"', 'focus:"value"',
                     'fields:"value:any?"']
            if desc:
                parts.append(f'desc:"{desc.group(1)}"')
            if layer:
                # No CORTEX 1.0 equivalent: preserved as an extra field so it is
                # never lost silently (BLP-001 §7.4).
                parts.append(f'layer:"{layer.group(1)}"')
            parts.append("open:true")

            out.append(f"{sigil}:{sigil.lower()}_contract{{{', '.join(parts)}}}")
            continue
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _synthesize_declarations(text: str) -> str:
    """Insert CORTEX 1.0 sigil declarations inside ``$0``.

    The legacy corpus keeps its glossary as ``# SIGIL | name | type | ...``
    comment lines, which NO parser reads in any version. Under 1.0 a sigil used
    outside ``$0`` must be declared as a real idea, or the document fails with
    I001_UNDECLARED_SYMBOL.

    Declarations are synthesised ``open:true`` so the parser accepts whatever
    fields the entries actually carry. Closing them requires deriving the real
    key set per sigil — that is phase 2, declared in BLP-001 §8.
    """
    lines = text.split("\n")

    # Split the document into kernel ($0) and body. The dialect declaration
    # ``$0:format{...}`` matches the section-header shape but lives INSIDE $0, so
    # treating it as a boundary truncated the kernel to two lines, hid every
    # declaration and made synthesis re-add them outside the glossary.
    kernel_start = None
    body_start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s == "$0" and kernel_start is None:
            kernel_start = i
        elif (
            re.match(r"^\$\d+(\.\d+)?:", s)
            and not re.match(r"^\$0:format\s*\{", s)
            and kernel_start is not None
        ):
            body_start = i
            break

    if kernel_start is None:
        return text

    kernel = lines[kernel_start:body_start if body_start is not None else len(lines)]
    body = lines[body_start:] if body_start is not None else []

    body_text = "\n".join(body)
    # Only real entries count: skip comments, where the legacy glossary lives as
    # ``# SIGIL | name | type | ...``. Reading those as usage invented duplicate
    # declarations and triggered G015_DUPLICATE_SYMBOL.
    real_text = "\n".join(
        ln for ln in body_text.split("\n") if not ln.lstrip().startswith("#"))
    # Entry names may contain hyphens and dots (e.g. LOOP:arqux-night-build).
    used = set(re.findall(r"^([A-Z][A-Z0-9_]{1,5}):[A-Za-z0-9_.\-]+\{", real_text, flags=re.M))
    if not used:
        return text

    # An existing declaration must be opened too: ``I005_UNKNOWN_FIELD`` fires on
    # a closed contract whose ``fields`` does not list every key the entries use
    # (``ARQX:artifact{level:...}`` against ``fields:"value:any?"``). Only the
    # copies inside the kernel are declarations; the same shape outside is data.
    for idx, line in enumerate(kernel):
        s = line.strip()
        if s.startswith("#"):
            continue
        m = re.match(r"^([A-Z][A-Z0-9_]{1,5}):([A-Za-z0-9_.\-]+)\{([^}]*)\}$", s)
        if not m:
            continue
        sigil, decl_name, decl_body = m.groups()
        if sigil not in used or "open:" in decl_body:
            continue
        if not re.search(r"(type|weight|focus|fields|desc)\s*:", decl_body):
            continue
        decl_body = re.sub(r'fields\s*:\s*"[^"]*"', 'fields:"value:any?"', decl_body)
        decl_body = re.sub(r"focus\s*:\s*[^,}]+", 'focus:"value"', decl_body)
        decl_body = decl_body.rstrip().rstrip(",").rstrip()
        kernel[idx] = f"{sigil}:{decl_name}{{{decl_body}, open:true}}"

    # A declaration lives INSIDE $0. Scanning the whole document found entries
    # (``AXM:workflow_fidelity{...}``) and prose that merely mentions a sigil
    # (an AUD entry quoting ``IDN:idn_contract``) — both were mistaken for
    # declarations, leaving the real sigil undeclared (I001).
    already: set[str] = set()
    for line in kernel:
        s = line.strip()
        if s.startswith("#"):
            continue
        m = re.match(r"^([A-Z][A-Z0-9_]{1,5}):[A-Za-z0-9_.\-]+\{([^}]*)\}$", s)
        if m and re.search(r"(type|weight|focus|fields|desc)\s*:", m.group(2)):
            already.add(m.group(1))
    # ``_translate_gsig_text`` already emits a contract declaration per GSIG
    # sigil. Without this, synthesis adds a second one for the same sigil and the
    # file dies with G015_DUPLICATE_SYMBOL.
    #
    # The lookup is scoped to the KERNEL: an entry elsewhere may quote the string
    # (an AUD note mentioning ``IDN:idn_contract``), and a whole-document search
    # read that as "already declared", leaving the sigil undeclared (I001).
    kernel_text = "\n".join(kernel)
    already |= {
        sigil for sigil in used
        if f"{sigil}:{sigil.lower()}_contract" in kernel_text
    }

    missing = sorted(used - already)

    if missing:
        new_decls = [
            f'{sigil}:{sigil.lower()}_contract{{type:"attrs", weight:"M", focus:"value", '
            f'fields:"value:any?", desc:"ArqUX {sigil} entry", open:true}}'
            for sigil in missing
        ]
        # The kernel must end with a blank line before the declaration block.
        if kernel and kernel[-1].strip() != "":
            kernel.append("")
        kernel.extend(new_decls)

    # Always rebuild: even with nothing missing, the loop above may have opened an
    # existing declaration, and returning the ORIGINAL text here discarded that
    # (I005 on ARQX:artifact against a closed contract).
    return "\n".join(kernel + body)


def flatten_multiline_strings(text: str) -> str:
    """Join physical lines that sit inside an unterminated quoted value.

    CORTEX 1.0 requires one physical line per idea (I004). Governance contracts
    carry values like ``purpose:"line one\\n<newline>   line two"``; joining them
    with a single space is the only lossless reading.
    """
    out: list[str] = []
    pending: str | None = None

    for line in text.split("\n"):
        if pending is not None:
            pending += " " + line.strip()
            if pending.count('"') % 2 == 0:
                out.append(pending)
                pending = None
            continue

        if line.lstrip().startswith("#") or line.count('"') % 2 == 0:
            out.append(line)
            continue

        pending = line.rstrip()

    if pending is not None:
        out.append(pending)

    return "\n".join(out)


def collapse_multiline_ideas(text: str) -> str:
    """Join an idea split across physical lines into ONE line (I004).

    An ``attrs`` entry that opens ``{`` and does not close ``}`` on the same line
    is a multi-line idea, which 1.0 rejects. Values are already flattened by this
    point, so joining is lossless.
    """
    out: list[str] = []
    buffer: str | None = None

    for line in text.split("\n"):
        stripped = line.strip()

        if buffer is not None:
            buffer += " " + stripped
            if "}" in stripped:
                out.append(buffer)
                buffer = None
            continue

        if (not stripped.startswith("#")
                and re.match(r"^[A-Z][A-Z0-9_]{1,5}:[A-Za-z0-9_.\-]+\{", stripped)
                and "}" not in stripped):
            buffer = stripped
            continue

        out.append(line)

    if buffer is not None:
        out.append(buffer)

    return "\n".join(out)


def absorb_metadata_into_identity(text: str) -> str:
    """Move the ``$0.1: ARQUX METADATA`` block into ``$1: IDENTITY``.

    ``$0`` may hold only sigil declarations (G004), so the metadata sub-section
    cannot stay there. The metadata is identity-level; ``formats.py`` reads it
    from either location (BLP-001 T-1.17).

    Only the ``$0.1`` line and the metadata entries directly under it are moved.
    Pulling the whole span up to the next ``$N:`` section also swallowed the
    translated sigil declarations that sit between them, which then ended up
    outside the kernel (G015 / I001).
    """
    m = re.search(
        r"^\$0\.1:[^\n]*\n((?:[ \t]*(?:ARQX:[^\n]*|#[^\n]*|\s*)\n)*)",
        text,
        re.M,
    )
    if not m:
        return text

    block = m.group(1)
    # Keep only the metadata entries; comments stay where they are.
    entries = [ln for ln in block.split("\n")
               if ln.strip() and not ln.lstrip().startswith("#")]
    text = text[: m.start()] + text[m.end():]

    idn = re.search(r"^\$1:\s*IDENTITY\s*$", text, re.M)
    if not idn:
        return text

    insert_at = idn.end()
    body = "\n".join(entries) if entries else ""
    return text[:insert_at] + "\n\n" + body + text[insert_at:]


def normalize_body_payloads(text: str) -> str:
    """Rewrite ``SIGIL:name{ free text }`` as a CORTEX ``cuerpo`` entry.

    Some identities carry axioms as a raw payload between braces:
    ``AXM:workflow_fidelity{ Respeto irrestricto... }``. CORTEX 1.0 parses the
    brace payload as attrs and fails with S006 (``Expected : after key``). The
    canonical form for free text is the ``cuerpo`` shape, so the sigil is
    declared as ``type:"cuerpo"`` and the payload moved to a ``body`` field.
    """
    out: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        m = re.match(r"^([A-Z][A-Z0-9_]{1,5}):([A-Za-z0-9_.\-]+)\{(.*)\}$", stripped)
        if m and not stripped.startswith("#"):
            sigil, name, payload = m.groups()
            # Heuristic: a real attrs payload has ``key:value`` pairs and no bare
            # prose. Body payloads start with natural language.
            looks_like_attrs = bool(re.match(r"\s*[A-Za-z_][A-Za-z0-9_]*\s*:", payload))
            if not looks_like_attrs and payload.strip():
                body = " ".join(payload.split())
                # Inner quotes must be escaped or they close the value early
                # (S006: "Expected , or } got 'e'").
                body = body.replace('\\"', '"').replace('"', '\\"')
                out.append(f'{sigil}:{name}{{type:"cuerpo", body:"{body}"}}')
                continue
        out.append(line)

    return "\n".join(out)


def absorb_metadata_into_first_section(text: str) -> str:
    """Fold a ``$0.1: ARQUX METADATA`` block into the first content section.

    Under CORTEX 1.0 ``$0`` may hold only sigil declarations (G004), so the
    metadata sub-section cannot stay in the glossary of tasks, cycles or other
    non-identity artifacts. Those artifacts have no IDENTITY section, so the
    block moves to whatever ``$N:`` comes first after ``$0``.
    """
    m = re.search(
        r"^\$0\.1:[^\n]*\n((?:[ \t]*(?:ARQX:[^\n]*|#[^\n]*|\s*)\n)*)",
        text,
        re.M,
    )
    if not m:
        return text

    entries = [ln for ln in m.group(1).split("\n")
               if ln.strip() and not ln.lstrip().startswith("#")]
    text = text[: m.start()] + text[m.end():]

    if not entries:
        return text

    target = re.search(r"^\$(?!0)\d+:[^\n]*$", text, re.M)
    if not target:
        return text

    insert_at = target.end()
    return text[:insert_at] + "\n\n" + "\n".join(entries) + text[insert_at:]


def ensure_content_section(text: str) -> str:
    """Give a document a content section when it has entries but no ``$N:``.

    Some legacy artifacts declare ``$0`` then list entries directly, with no
    section header. CORTEX 1.0 requires entries to live inside a section
    (S005_CONTENT_OUTSIDE_SECTION), and without one every entry is parsed as part
    of the glossary — turning data into duplicate declarations (G015).
    """
    lines = text.split("\n")
    kernel_start = None
    for i, line in enumerate(lines):
        if line.strip() == "$0":
            kernel_start = i
            break
    if kernel_start is None:
        return text

    # First section header after the kernel?
    for line in lines[kernel_start + 1:]:
        if re.match(r"^\$(?!0)\d+(\.\d+)?:", line.strip()):
            return text

    # No section. Find the first entry after the kernel and insert a header.
    for i in range(kernel_start + 1, len(lines)):
        if re.match(r"^[A-Z][A-Z0-9_]{1,5}:[A-Za-z0-9_.\-]+\{", lines[i].strip()):
            lines.insert(i, "")
            lines.insert(i + 1, "$1: CONTENT")
            lines.insert(i + 2, "")
            return "\n".join(lines)
    return text


def _kernel_declarations(text: str) -> set[str]:
    """Sigils declared inside the ``$0`` kernel."""
    lines = text.split("\n")
    kernel_start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s == "$0" and kernel_start is None:
            kernel_start = i
            continue
        if kernel_start is None:
            continue
        if re.match(r"^\$\d+(\.\d+)?:", s) and not re.match(r"^\$0:format\s*\{", s):
            break
    else:
        return set()
    kernel = lines[kernel_start:i]
    declared = set()
    for line in kernel:
        s = line.strip()
        if s.startswith("#"):
            continue
        m = re.match(r"^([A-Z][A-Z0-9_]{1,5}):[A-Za-z0-9_.\-]+\{([^}]*)\}$", s)
        if m and re.search(r"(type|weight|focus|fields|desc)\s*:", m.group(2)):
            declared.add(m.group(1))
    return declared


def transform(text: str, category: str) -> str:
    # Idempotence: a file already on 1.0 with its contracts in place must pass
    # through unchanged. Re-running the migrator is a normal operation (a failed
    # batch is retried), and a non-idempotent migrator duplicates declarations.
    #
    # A declaration that is MISSING means the file is not really migrated — a
    # governance write from an older process can strip them while leaving the
    # format line, and returning here would ship a broken artifact.
    if (
        re.search(r"^\$0:format\{cortex:1\.0[,}]", text, re.M)
        and "GSIG:" not in text
        and "$0.1:" not in text
    ):
        body_text = "\n".join(
            ln for ln in text.split("\n") if not ln.lstrip().startswith("#"))
        used = set(re.findall(
            r"^([A-Z][A-Z0-9_]{1,5}):[A-Za-z0-9_.\-]+\{", body_text, flags=re.M))
        if not (used - _kernel_declarations(text)):
            return text

    # Two legacy shapes are not CORTEX artifacts and are out of scope for a
    # dialect migration (BLP-001 §6): markdown tasks (frontmatter + ``# OBJ``) and
    # artifacts whose YAML frontmatter precedes ``$0``. There are 2 in the corpus;
    # converting them is a format change, not a dialect change.
    if text.lstrip().startswith("---"):
        return text
    if not re.search(r"^[ \t]*\$0[ \t]*$", text, re.M):
        return text

    if category in ("identities", "templates"):
        # Order matters: translate and normalise the kernel declarations while
        # they are still where the source put them, THEN move the metadata block
        # up into $1. Absorbing first moved the $0.1 span across the translated
        # declarations and left a second, duplicate set outside the kernel
        # (G015_DUPLICATE_SYMBOL).
        text = _translate_gsig_text(text)
        text = normalize_body_payloads(text)
        text = flatten_multiline_strings(text)
        text = collapse_multiline_ideas(text)
        text = absorb_metadata_into_identity(text)
        text = _fix_format_line(text)
        text = _synthesize_declarations(text)
    else:
        # Non-identity artifacts can also carry a ``$0.1`` metadata block, which
        # $0 may not contain under 1.0 (G004). Fold it into the first content
        # section instead of leaving it inside the glossary. Some of them also
        # carry legacy ``GSIG:`` declarations, which are not sigils and fail as
        # duplicate symbols if left alone.
        text = _translate_gsig_text(text)
        text = flatten_multiline_strings(text)
        text = collapse_multiline_ideas(text)
        text = absorb_metadata_into_first_section(text)
        text = ensure_content_section(text)
        text = _fix_format_line(text)
        text = _synthesize_declarations(text)
    return text


def verify_with_codec_1(path: Path) -> tuple[bool, str]:
    try:
        from codec_cortex.dispatcher import parse_cortex
    except ImportError:
        return False, "NO_CODEC_1"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return False, str(type(exc).__name__)

    # Same scope boundary as dialect_conformance.py: a file that is not a CORTEX
    # artifact is not a failure of the migration.
    if text.lstrip().startswith("---"):
        return True, "SKIP_LEGACY_FRONTMATTER"
    if not re.search(r"^[ \t]*\$0[ \t]*$", text, re.M):
        return True, "SKIP_NOT_CORTEX"

    try:
        parse_cortex(text)
        return True, "OK"
    except Exception as exc:  # noqa: BLE001
        return False, str(getattr(exc, "code", "") or type(exc).__name__)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="/home/vatrox/workspace")
    ap.add_argument("--only", nargs="+", choices=list(CATEGORIES), required=True)
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="explicit no-op (default)")
    ap.add_argument("--report")
    ap.add_argument("--files", nargs="*", help="restrict to these relative paths")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    apply_changes = args.apply and not args.dry_run

    targets = []
    if args.files:
        targets = [root / f for f in args.files]
    else:
        from dialect_conformance import iter_cortex_files  # same directory
        for path in iter_cortex_files(root, "migrable"):
            rel = str(path.relative_to(root))
            cat = classify(rel)
            if cat in args.only:
                targets.append(path)

    rows, written, failed = [], 0, 0

    for path in targets:
        rel = str(path.relative_to(root))
        original = path.read_text(encoding="utf-8")
        candidate = transform(original, classify(rel) or "misc")

        with tempfile.NamedTemporaryFile("w", suffix=".cortex", delete=False,
                                         encoding="utf-8") as tmp:
            tmp.write(candidate)
            tmp_path = Path(tmp.name)
        try:
            ok, code = verify_with_codec_1(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        if not ok:
            failed += 1
            rows.append(("FAIL", code, rel, "original intacto"))
            continue

        if not apply_changes:
            rows.append(("OK-DRY", "OK", rel, "verificado, sin escribir"))
            continue

        backup = path.with_suffix(path.suffix + ".pre-migracion")
        shutil.copy2(path, backup)
        path.write_text(candidate, encoding="utf-8")

        ok2, code2 = verify_with_codec_1(path)
        if not ok2:
            shutil.move(str(backup), str(path))
            failed += 1
            rows.append(("FAIL", code2, rel, "revertido desde .pre-migracion"))
            continue

        written += 1
        rows.append(("MIGRATED", "OK", rel, ""))

    for status, code, rel, note in rows:
        print(f"{status}\t{code}\t{rel}\t{note}")
    print()
    print(f"targets={len(targets)} written={written} failed={failed} mode={'apply' if apply_changes else 'dry-run'}")

    if args.report:
        out = Path(args.report).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for status, code, rel, note in rows:
                fh.write(f"{status}\t{code}\t{rel}\t{note}\n")
        print(f"report -> {out}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    raise SystemExit(main())
