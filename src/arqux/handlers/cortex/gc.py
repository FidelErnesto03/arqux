"""cortex.gc handler — garbage collection / repair for duplicate entries.

Scans a .cortex file for entries with the same sigil:name in the same
section and either removes the extra occurrences (``mode="dedupe"``,
conserving the first/last ``first_kept`` occurrences) or renames them
to unique sequential names (``mode="rename"``, preserving every
occurrence).

Optional ``section``/``sigil``/``name`` filters restrict which duplicate
groups are affected; unfiltered invocations behave as before.

BLP-002 G-5: Created to address the accumulation of duplicate entries
without any mechanism for automated cleanup.
T-018: scoped repair — filters + keep-last + rename mode (pulse trail
repair: distinct AUD events sharing an E_NNNN id get unique names).
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from ...cortex.atomic import atomic_write_json
from ...cortex.reader import cortex_to_dict
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import find_project_root

_VALID_KEEP = ("first", "last")
_VALID_MODE = ("dedupe", "rename")

# Entry names ending in digits have a "numeric suffix" used by rename
# mode: ``E_0157`` -> prefix ``E_``, suffix ``0157`` (width 4).
_NUM_SUFFIX_RE = re.compile(r"^(?P<prefix>.*?)(?P<digits>\d+)$")

# Attr keys that may embed the entry's own identifier.  Pulse AUD entries
# store ``event:"E-0157"`` (hyphen form) while the entry name is
# ``E_0157`` (underscore form); rename mode keeps them consistent.
_ID_ATTR_KEYS = ("event", "id")


def _matches_filters(
    sec_id: str,
    sigil: str,
    name: str,
    f_section: str | None,
    f_sigil: str | None,
    f_name: str | None,
) -> bool:
    """True when the (section, sigil, name) group passes all filters."""
    if f_section is not None and sec_id != f_section:
        return False
    if f_sigil is not None and sigil != f_sigil:
        return False
    return f_name is None or name == f_name


def _namespace_state(
    cache: dict[tuple[int, str], dict[str, Any]],
    sec_i: int,
    sigil: str,
    entries: list[dict],
) -> dict[str, Any]:
    """Lazily compute rename state for a (section, sigil) namespace.

    ``next`` is the global maximum numeric suffix over ALL *same-sigil*
    entry names in the section + 1 — computed once, then incremented per
    rename so renamed extras never collide with existing (or newer) ids.
    ``used`` holds every name currently taken in the namespace (names are
    only unique within a (section, sigil) pair, so other sigils' names
    are ignored).
    """
    key = (sec_i, sigil)
    st = cache.get(key)
    if st is None:
        max_num = 0
        used: set[str] = set()
        for entry in entries:
            if entry.get("sigil") != sigil:
                continue
            n = entry.get("name", "")
            used.add(n)
            m = _NUM_SUFFIX_RE.match(n)
            if m is not None:
                num = int(m.group("digits"))
                if num > max_num:
                    max_num = num
        st = {"next": max_num + 1, "used": used}
        cache[key] = st
    return st


def _next_unique_name(ns: dict[str, Any], old_name: str) -> str:
    """Return the next free rename for *old_name* in namespace *ns*.

    Names with a trailing numeric suffix keep their prefix and draw the
    number from the shared namespace counter (global max + 1, incrementing
    per rename, zero-padded to the original suffix width).  Names with no
    numeric suffix get ``_001``, ``_002``, ... appended (documented
    behavior).  Candidates already in ``ns['used']`` are skipped.
    """
    m = _NUM_SUFFIX_RE.match(old_name)
    if m is not None:
        prefix, digits = m.group("prefix"), m.group("digits")
        width = len(digits)
        while True:
            cand = f"{prefix}{ns['next']:0{width}d}"
            ns["next"] += 1
            if cand not in ns["used"]:
                break
    else:
        n = 1
        while True:
            cand = f"{old_name}_{n:03d}"
            n += 1
            if cand not in ns["used"]:
                break
    ns["used"].add(cand)
    return cand


def _id_attr_updates(entry: dict, old_name: str, new_name: str) -> dict[str, str]:
    """Compute attr updates so embedded ids stay consistent after rename.

    Handles both storage forms: an attr equal to the old entry name
    verbatim is set to the new name verbatim; an attr equal to the old
    name's hyphen form (``E-0157`` for ``E_0157``) is set to the new
    name's hyphen form.  Non-matching values are left untouched.
    """
    updates: dict[str, str] = {}
    attrs = entry.get("attrs")
    if not isinstance(attrs, dict):
        return updates
    old_hyphen = old_name.replace("_", "-")
    for key in _ID_ATTR_KEYS:
        value = attrs.get(key)
        if not isinstance(value, str):
            continue
        if value == old_name:
            updates[key] = new_name
        elif value == old_hyphen:
            updates[key] = new_name.replace("_", "-")
    return updates


def gc_handler(
    path: str,
    *,
    dry_run: bool = True,
    force: bool = False,
    first_kept: int = 1,
    section: str | None = None,
    sigil: str | None = None,
    name: str | None = None,
    keep: str = "first",
    mode: str = "dedupe",
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Garbage-collect or repair duplicate entries in a .cortex file.

    Duplicates are entries that share the same (section, sigil, name).
    With ``dry_run=True`` (default), returns the list of affected
    occurrences without modifying the file.  With ``dry_run=False`` and
    ``force=True``, applies the mutation in a single atomic rewrite.

    Args:
        path: Path to the .cortex file (e.g., ``brain.cortex``).
        dry_run: If True (default), preview without mutating.
        force: Required to perform the actual mutation.
        first_kept: Number of occurrences to keep per duplicate group.
        section: Optional filter — only affect groups in this section
            (``"$6"``; the ``$`` prefix may be omitted).
        sigil: Optional filter — only affect groups with this sigil.
        name: Optional filter — only affect groups with this entry name.
        keep: ``"first"`` (default) conserves the first ``first_kept``
            occurrences in file order; ``"last"`` conserves the last
            ones (metrics: keeps the most recent values).
        mode: ``"dedupe"`` (default) removes extra occurrences;
            ``"rename"`` preserves every occurrence and assigns extras a
            new unique name — next sequential numeric id in the
            (section, sigil) namespace for numeric-suffixed names
            (``E_0157`` -> ``E_0343``...), or ``_001``, ``_002``, ...
            appended for names without a numeric suffix.  Embedded
            ``event``/``id`` attrs are updated consistently.
        ctx: Permission context.

    Returns:
        ``OUT-WORK`` with ``duplicates`` list (one item per affected
        occurrence, carrying ``action`` and — in rename mode —
        ``new_name``), ``matched_groups``/``skipped_groups`` counts,
        ``removed``/``renamed`` counts.  ``bytes_written``/``file_bytes``
        report the whole file size after the rewrite (unlike
        ``entry.add``, where ``bytes_written`` is the serialized entry
        size).
    """
    src_path = Path(path)
    if not src_path.exists():
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")

    try:
        doc = cortex_to_dict(src_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return CortexOUT.error(str(exc), code="PARSE_ERROR")

    try:
        first_kept = max(1, int(first_kept))
    except (TypeError, ValueError):
        return CortexOUT.error(
            f"invalid first_kept={first_kept!r} (must be an integer >= 1)",
            code="INVALID_ARGS",
        )

    if keep not in _VALID_KEEP:
        return CortexOUT.error(
            f"invalid keep={keep!r} (must be 'first' or 'last')",
            code="INVALID_ARGS",
        )
    if mode not in _VALID_MODE:
        return CortexOUT.error(
            f"invalid mode={mode!r} (must be 'dedupe' or 'rename')",
            code="INVALID_ARGS",
        )

    # Normalise the section filter: accept both "$6" and "6".
    f_section: str | None = None
    if section is not None:
        f_section = section if section.startswith("$") else f"${section}"

    filters: dict[str, str] = {}
    if f_section is not None:
        filters["section"] = f_section
    if sigil is not None:
        filters["sigil"] = sigil
    if name is not None:
        filters["name"] = name

    duplicates: list[dict] = []
    matched_groups = 0
    skipped_groups = 0
    # Mutation plans — computed during the scan, applied only after the
    # dry_run/force gate so previews never mutate the document.
    drop_by_section: dict[int, set[int]] = {}
    rename_by_section: dict[int, dict[int, tuple[str, dict[str, str]]]] = {}
    ns_cache: dict[tuple[int, str], dict[str, Any]] = {}

    for sec_i, sec in enumerate(doc.get("sections", [])):
        sec_id = sec.get("id", "")
        entries = sec.get("entries", [])
        groups: dict[tuple[str, str], list[int]] = defaultdict(list)
        for idx, entry in enumerate(entries):
            e_sigil = entry.get("sigil", "")
            e_name = entry.get("name", "")
            if not e_sigil or not e_name:
                continue
            groups[(e_sigil, e_name)].append(idx)

        for (g_sigil, g_name), idxs in groups.items():
            if len(idxs) <= first_kept:
                continue
            if not _matches_filters(
                sec_id, g_sigil, g_name, f_section, sigil, name
            ):
                skipped_groups += 1
                continue
            matched_groups += 1
            if keep == "first":
                kept_idxs = idxs[:first_kept]
                extra_idxs = idxs[first_kept:]
            else:
                kept_idxs = idxs[len(idxs) - first_kept:]
                extra_idxs = idxs[: len(idxs) - first_kept]
            kept_names = [entries[i].get("name", g_name) for i in kept_idxs]
            # Renames are assigned in file order (chronological
            # preservation) regardless of which occurrences are kept.
            for idx in extra_idxs:
                item: dict[str, Any] = {
                    "section": sec_id,
                    "sigil": g_sigil,
                    "name": g_name,
                    "count": len(idxs),
                    "first_kept": first_kept,
                    "keep": keep,
                    "kept_names": kept_names,
                    "index": idx,
                }
                if mode == "dedupe":
                    drop_by_section.setdefault(sec_i, set()).add(idx)
                    item["action"] = "removed"
                else:
                    ns = _namespace_state(ns_cache, sec_i, g_sigil, entries)
                    new_name = _next_unique_name(ns, g_name)
                    attr_updates = _id_attr_updates(
                        entries[idx], g_name, new_name
                    )
                    rename_by_section.setdefault(sec_i, {})[idx] = (
                        new_name,
                        attr_updates,
                    )
                    item["action"] = "renamed"
                    item["new_name"] = new_name
                    if attr_updates:
                        item["event_updated"] = True
                duplicates.append(item)

    common: dict[str, Any] = {
        "path": path,
        "mode": mode,
        "keep": keep,
        "matched_groups": matched_groups,
        "skipped_groups": skipped_groups,
    }
    if filters:
        common["filters"] = filters

    if not duplicates:
        skipped = (
            f" — {skipped_groups} duplicate group(s) skipped by filters"
            if skipped_groups
            else ""
        )
        return CortexOUT.work(
            f"cortex.gc ok — 0 duplicates matched in {path}{skipped}",
            dry_run=dry_run, force=force,
            duplicates=[], removed=0, renamed=0,
            **common,
        )

    if dry_run:
        if mode == "rename":
            msg = (
                f"cortex.gc dry_run — {len(duplicates)} occurrence(s) "
                f"would be renamed"
            )
        else:
            msg = (
                f"cortex.gc dry_run — {len(duplicates)} duplicate(s) "
                f"detected"
            )
        return CortexOUT.work(
            msg,
            dry_run=True, force=False,
            duplicates=duplicates, removed=0, renamed=0,
            would_remove=len(duplicates) if mode == "dedupe" else 0,
            would_rename=len(duplicates) if mode == "rename" else 0,
            **common,
        )

    if not force:
        verb = "rename" if mode == "rename" else "remove"
        return CortexOUT.error(
            f"{len(duplicates)} duplicates found — pass force=True to {verb}",
            code="CONFIRM_REQUIRED",
        )

    try:
        for sec_i, idxs in drop_by_section.items():
            sec = doc["sections"][sec_i]
            entries = sec["entries"]
            sec["entries"] = [
                e for i, e in enumerate(entries) if i not in idxs
            ]
        for sec_i, renames in rename_by_section.items():
            entries = doc["sections"][sec_i]["entries"]
            for idx, (new_name, attr_updates) in renames.items():
                entries[idx]["name"] = new_name
                attrs = entries[idx].get("attrs")
                if attr_updates and isinstance(attrs, dict):
                    attrs.update(attr_updates)
        result = atomic_write_json(doc, str(src_path))
        removed = len(duplicates) if mode == "dedupe" else 0
        renamed = len(duplicates) if mode == "rename" else 0
        failed = 0
    except Exception:
        return CortexOUT.error(
            f"cortex.gc failed — 0 of {len(duplicates)} duplicate(s) repaired",
            code="GC_ERROR",
        )

    # PULSE.
    try:
        root = find_project_root(start=path)
        if root is not None:
            agent = (ctx or PermissionContext.from_env()).agent_id
            event_id = next_pulse_event_id(root)
            append_pulse_to_brain(
                root,
                event_id=event_id,
                task_id="-",
                kind="handler_call",
                agent=agent,
                payload=(
                    f"[cortex.gc] mode={mode} removed={removed} "
                    f"renamed={renamed} failed={failed}"
                ),
            )
    except Exception:
        pass

    if mode == "rename":
        msg = (
            f"cortex.gc ok — {renamed} occurrence(s) renamed "
            f"(failed={failed})"
        )
    else:
        msg = (
            f"cortex.gc ok — {removed} duplicate(s) removed "
            f"(failed={failed})"
        )
    return CortexOUT.work(
        msg,
        dry_run=False, force=True,
        duplicates=duplicates, removed=removed, renamed=renamed,
        failed=failed,
        bytes_written=result.bytes_written,
        file_bytes=result.bytes_written,
        backup=result.backup,
        **common,
    )
