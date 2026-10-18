"""Cortex learning engine and identity lesson recording handlers."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from ...constants import ARQUX_DIR
from ...cortex.reader import cortex_to_dict
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext, enforce_ctx
from ...state import crud_add, find_project_root

#: Titles that identify the behavioral-lessons section of an identity file.
_LESSONS_TITLE = re.compile(r"^(BEHAVIORAL\s+)?LESSONS$", re.IGNORECASE)


def _lessons_section_for(path: Path) -> str | None:
    """Return the id of the behavioral-lessons section, or ``None``.

    Identity files do not share a section layout. In this workspace alfred and
    jarvis keep lessons in ``$6`` while governor keeps them in ``$5``, and
    heimdall/seshat use ``$6`` for EXPERTISE — a hardcoded id would file
    lessons under DESCRIPTION or EXPERTISE.
    """
    doc = cortex_to_dict(path.read_text(encoding="utf-8"))
    for section in doc.get("sections", []):
        if _LESSONS_TITLE.match(str(section.get("title") or "").strip()):
            return str(section.get("id", ""))
    return None


def _ensure_lessons_section(path: Path) -> str:
    """Return the lessons section id, creating a *titled* one when absent.

    ``crud_add(create_section=True)`` writes a bare ``$8`` with no title, which
    this resolver would not recognise on the next call — so every lesson would
    allocate a fresh section. The header is therefore created here, with the
    title, and only then is the entry added into it.
    """
    found = _lessons_section_for(path)
    if found is not None:
        return found

    doc = cortex_to_dict(path.read_text(encoding="utf-8"))
    used = [
        int(m.group(1))
        for m in (
            re.match(r"^\$(\d+)$", str(s.get("id", ""))) for s in doc.get("sections", [])
        )
        if m
    ]
    new_id = f"${max(used or [0]) + 1}"

    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    text += f"\n{new_id}: BEHAVIORAL LESSONS\n\n"
    path.write_text(text, encoding="utf-8")
    return new_id


def _derive_lesson_name(
    lesson: str,
    taken: set[str],
    explicit: str | None = None,
) -> str:
    """Derive a unique, stable LNG entry name for *lesson*.

    BUG-1 follow-up: the name used to be the first word of the lesson prose.
    Spanish/English articles dominated, so ``alfred.cortex`` accumulated
    ``LNG:al`` x10, ``LNG:en`` x9, ``LNG:el`` x9 and 51 E008 duplicate
    entries in total. Entry identity must not come from prose.

    Resolution order:
      1. An explicit *name* supplied by the caller.
      2. The first word, when it is still free.
      3. The first word plus a digest of the lesson content. The digest makes
         the result deterministic, so re-recording the same lesson yields the
         same name instead of appending yet another numeric suffix.
    """
    if explicit:
        candidate = re.sub(r"[^a-z0-9_]", "_", explicit.casefold())[:30].strip("_")
        if candidate:
            return candidate
    first_word = lesson.lstrip(" -\"").lower().split()[0] if lesson.split() else "lesson"
    candidate = re.sub(r"[^a-z0-9]", "_", first_word)[:30] or "lesson"
    if candidate not in taken:
        return candidate
    digest = hashlib.sha256(lesson.encode("utf-8")).hexdigest()[:6]
    return f"{candidate}_{digest}"


def record_lesson_handler(
    lesson: str, kind: str | None = None, cause: str | None = None,
    prevention: str | None = None, name: str | None = None,
    agent_id: str | None = None,
    path: str | None = None, ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Record a behavioral lesson into agent identity with HMAC verification."""
    authenticated = enforce_ctx(
        ctx, "identity.record",
        require_hmac=os.environ.get("ARQUX_STRICT_SECURITY") == "1",
    )
    canonical_agent = authenticated.agent_id.casefold()
    if agent_id and agent_id.casefold() != canonical_agent:
        return CortexOUT.error(
            f"requested agent_id={agent_id!r} does not match authenticated agent={authenticated.agent_id!r}",
            code="IDENTITY_MISMATCH",
        )
    return record_lesson_handler_legacy(
        lesson=lesson,
        kind=kind or "behavioral",
        cause=cause or "",
        prevention=prevention or "",
        name=name,
        agent_id=authenticated.agent_id,
        path=path or "",
        ctx=ctx,
    )


def record_lesson_handler_legacy(
    lesson: str,
    kind: str = "behavioral",
    cause: str = "",
    prevention: str = "",
    name: str | None = None,
    agent_id: str = "",
    path: str = "",
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Record a behavioral lesson into the agent's identity file.

    Appends an LNG entry to ``$5: BEHAVIORAL LESSONS`` in the agent's
    identity at ``<workspace or project>/.arqux/identities/<agent_id>.cortex``.

    This is how identities evolve — each significant behavioral lesson
    becomes a permanent part of the agent's identity.

    BLP-042: prevention is REQUIRED. No fallback bypass.
    """
    agent = (agent_id or (ctx.agent_id if ctx else "alfred")).casefold()
    target_path = Path(path or ".").resolve()

    identity_file = None
    cursor = target_path
    while True:
        candidate = cursor / ARQUX_DIR / "identities" / f"{agent}.cortex"
        if candidate.exists():
            identity_file = candidate
            break
        if cursor.parent == cursor:
            break
        cursor = cursor.parent

    if identity_file is None:
        pkg = Path(__file__).resolve().parent.parent.parent / "identities" / f"{agent}.cortex"
        if pkg.exists():
            identity_file = pkg
        else:
            return CortexOUT.error(
                f"identity file not found for agent={agent}", code="NOT_FOUND"
            )

    try:
        content_text = identity_file.read_text(encoding="utf-8")
        taken = {m.group(1) for m in re.finditer(r"^LNG:([A-Za-z0-9_]+)", content_text, re.M)}
        entry_name = _derive_lesson_name(lesson, taken, name)
        if entry_name in ("_", "*"):  # T-022: '_'/'*' are reserved selector names
            entry_name = "lesson"
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="IDENTITY_UPDATE_ERROR")

    value = {"type": kind, "cause": cause, "lesson": lesson, "prevention": prevention}

    # BLP-022 invariante B (E-1808): a Level-1 identity contract admits no
    # live-state sigil. When the identity declares level 1 the lesson is filed
    # in an apt destination (the project brain) instead of corrupting the
    # contract; if no apt destination exists the write is rejected.
    from ...timelog_capture import require_writable_destination

    destination_rejection = require_writable_destination(
        identity_file, "LNG", action="identity.record",
    )
    filed_in_identity = destination_rejection is None
    if filed_in_identity:
        try:
            result = crud_add(
                identity_file,
                # Resolved by section title: identities disagree on the number
                # ($5 for governor, $6 for alfred/jarvis) and some reuse $6 for
                # EXPERTISE, so a fixed id files lessons under the wrong section.
                _ensure_lessons_section(identity_file),
                "LNG", entry_name, value,
                create_section=True,
                force=True,
            )
            if "error" in result:
                return CortexOUT.error(result["error"], code="CRUD_ERROR")
        except Exception as exc:  # noqa: BLE001
            return CortexOUT.error(str(exc), code="IDENTITY_UPDATE_ERROR")

    scan_candidates = 0
    filed_in_brain = False
    try:
        from ...learning import scan_brain  # lazy: allow monkeypatch

        root = find_project_root(start=path or ".")
        if root is not None:
            project_dir = root.parent
            brain_path = project_dir / ".arqux" / "brain.cortex"
            if brain_path.exists():
                brain_result = crud_add(
                    brain_path,
                    "$7", "LNG", entry_name,
                    {"type": kind, "cause": cause, "lesson": lesson,
                     "prevention": prevention},
                    create_section=True,
                )
                # F4: only a clean write counts as filed — a crud_add that
                # returned an error must NOT be reported as persisted.
                filed_in_brain = "error" not in brain_result

            scan = scan_brain(project_dir, verbose=True)
            scan_candidates = len(scan.get("candidates", []))
    except Exception:  # noqa: BLE001
        pass

    if not filed_in_identity and not filed_in_brain:
        return CortexOUT.error(
            destination_rejection["message"],
            code=destination_rejection["code"],
            remediation=destination_rejection["remediation"],
        )

    result = CortexOUT.work(
        f"identity.record ok agent={agent} lesson={entry_name} kind={kind}",
        agent=agent,
        kind=kind,
        lesson=entry_name,
        file=str(identity_file),
        destination="identity" if filed_in_identity else "brain",
    )
    if scan_candidates:
        result.fields["hint"] = f"{scan_candidates} learning candidate(s) detected — run cortex.learn.elevate to review"
        result.fields["learning_candidates"] = scan_candidates
    return result


def learn_scan_handler(
    scope: str = "project",
    path: str | None = None,
    content: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Scan a project brain through the CODEC-CORTEX Learning Engine.

    Returns scored entries and elevation candidates. Accepts ``content`` as
    CORTEX with keys ``scope``/``path`` (BLP-014 alignment).
    """
    if content:
        from ...cortex.parse_content import parse_content_entry

        parsed = parse_content_entry(content)
        if parsed:
            scope = parsed.get("scope", scope)
            path = parsed.get("path", path)

    from ...learning import (  # lazy: allow monkeypatch
        _resolve_project_root,
        list_candidates,
        scan_brain,
    )

    root = _resolve_project_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    scan = scan_brain(root, verbose=(scope == "workspace"))
    if scan.get("engine") == "unavailable":
        return CortexOUT.error(
            "CODEC-CORTEX Learning Engine not available. "
            "Requires codec-cortex >=0.4.0 with learning module.",
            code="ENGINE_UNAVAILABLE",
        )
    if "error" in scan:
        return CortexOUT.error(scan["error"], code="LEARN_ERROR")

    candidates = scan.get("candidates", []) or list_candidates(root)

    return CortexOUT.work(
        f"learn.scan ok count={scan.get('count', 0)} entries scanned",
        engine=scan.get("engine", "unknown"),
        total=scan.get("count", 0),
        profile=scan.get("profile", {}),
        candidates=candidates,
    )


def learn_elevate_handler(
    candidate_id: str,
    path: str | None = None,
    *,
    apply: bool = False,
    confirm_hash: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Elevate a learning candidate (dry-run or apply).

    Default mode is dry-run (returns diff without changing brain).
    Pass apply=true to actually apply the elevation.
    """
    from ...learning import _resolve_project_root, elevate_candidate  # lazy: allow monkeypatch

    root = _resolve_project_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    result = elevate_candidate(root, candidate_id, dry_run=not apply, confirm_hash=confirm_hash)
    if "error" in result:
        return CortexOUT.error(
            result["error"],
            code="ELEVATE_ERROR",
            preview_hash=result.get("preview_hash"),
            diff=result.get("diff"),
        )

    if result.get("mode") == "dry_run":
        return CortexOUT.work(
            f"learn.elevate dry-run candidate={candidate_id}",
            candidate=candidate_id,
            mode="dry_run",
            diff=result.get("diff", ""),
            preview_hash=result.get("preview_hash", ""),
            validation_errors=result.get("validation_errors", []),
        )

    return CortexOUT.work(
        f"learn.elevate applied candidate={candidate_id}",
        candidate=candidate_id,
        mode="applied",
        diff=result.get("diff", ""),
        preview_hash=result.get("preview_hash", ""),
    )
