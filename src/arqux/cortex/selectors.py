# SPDX-License-Identifier: MPL-2.0
"""ArqUX CORTEX selectors (BLP-005).

Native ``$SECTION/SIGIL:NAME`` selector resolution over
:mod:`arqux.cortex.model`.  Grammar (codec §12.1):

    $SECTION/SIGIL:NAME     exact match
    SIGIL:NAME              match any section
    SIGIL:*                 all entries with that sigil
    $SECTION/*              all entries in a section

``*`` wildcards on name and section.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import CortexDocument, Entry, normalize_section_id


class NotFoundError(LookupError):
    def __init__(self, selector: str) -> None:
        super().__init__(f"selector {selector!r} matched no entries")
        self.selector = selector


class AmbiguousSelectorError(LookupError):
    def __init__(self, selector: str, count: int) -> None:
        super().__init__(f"selector {selector!r} matched {count} entries")
        self.selector = selector
        self.count = count


@dataclass
class Selector:
    section: str | None
    sigil: str
    name: str

    def __str__(self) -> str:
        s = f"{self.section}/" if self.section else ""
        return f"{s}{self.sigil}:{self.name}"


def parse_selector(s: str) -> Selector:
    s = s.strip()
    if not s:
        raise ValueError("empty selector")
    if "/" in s:
        section_part, rest = s.split("/", 1)
    else:
        section_part, rest = None, s
    if section_part == "*":
        section = "*"
    elif section_part:
        section = normalize_section_id(section_part)
    else:
        section = None
    if ":" in rest:
        sigil, name = rest.split(":", 1)
    else:
        sigil, name = rest, "*"
    return Selector(section=section,
                    sigil=sigil or "*",
                    name=name or "*")


def select(doc: CortexDocument, selector_str: str) -> list[Entry]:
    sel = parse_selector(selector_str)
    out: list[Entry] = []
    for sec, entry in doc.iter_entries():
        if sel.section and sel.section != "*" \
                and sec.id != normalize_section_id(sel.section):
            continue
        if sel.sigil != "*" and entry.sigil != sel.sigil:
            continue
        if sel.name != "*" and entry.name != sel.name:
            continue
        out.append(entry)
    return out


def select_one(doc: CortexDocument, selector_str: str) -> Entry:
    matches = select(doc, selector_str)
    if not matches:
        raise NotFoundError(selector_str)
    if len(matches) > 1:
        raise AmbiguousSelectorError(selector_str, len(matches))
    return matches[0]
