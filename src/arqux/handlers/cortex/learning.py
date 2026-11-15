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
      1. An explicit *name* supplied by the caller — honoured in full once
         slugified (explicit intent wins; the 30-char cap below used to
         truncate it silently — ergonomics issue). Slugification stays:
         entry names cannot carry spaces or braces in CORTEX.
      2. The first word, when it is still free.
      3. The first word plus a digest of the lesson content. The digest makes
         the result deterministic, so re-recording the same lesson yields the
         same name instead of appending yet another numeric suffix.

    The 30-char cap applies ONLY to auto-derived names (branches 2–3).
    """
    if explicit:
        candidate = re.sub(r"[^a-z0-9_]", "_", explicit.casefold()).strip("_")
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
    """Record a lesson into the project brain ``$8`` with HMAC verification.

    Architect rule 2026-11-15: ``brain.cortex`` is the ONLY lesson surface.
    All kinds (behavioral, technical, process, infrastructure) are filed as
    ``LNG`` entries in ``$8`` with the originating ``agent`` preserved as a
    field. Elevation to ``$11`` KNW or to an identity ``AXM``/``LIM`` is a
    separate governed step (``cortex.learn.elevate`` / ``identity.elevate``).
    """
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
    """Record a lesson into the project brain ``$8`` LESSONS section.

    Architect rule 2026-11-15: lessons live ONLY in ``brain.cortex``.
    Every kind — including ``behavioral`` — is filed as an ``LNG`` entry in
    ``$8``; the originating agent is preserved in the entry's ``agent``
    field. Identity files no longer receive lesson captures: behavioral
    knowledge reaches ``<agent>.cortex`` only through governed elevation
    (``identity.elevate`` → ``AXM``/``LIM``).

    BLP-042: prevention is REQUIRED. No fallback bypass. Brain E034 also
    rejects empty ``cause`` — both are enforced here so callers get a
    clear INVALID_ARGS instead of a downstream CRUD_ERROR.
    """
    agent = (agent_id or (ctx.agent_id if ctx else "alfred")).casefold()
    target_path = Path(path or ".").resolve()

    missing = [f for f, v in (("cause", cause), ("prevention", prevention)) if not str(v).strip()]
    if missing:
        return CortexOUT.error(
            f"required lesson field(s) empty: {', '.join(missing)} "
            f"(BLP-042/E034 — brain $8 LNG entries must carry non-empty "
            f"cause, lesson and prevention)",
            code="INVALID_ARGS",
        )

    root = find_project_root(start=str(target_path))
    brain_path = root / "brain.cortex" if root is not None else None
    if brain_path is None or not brain_path.exists():
        direct = target_path / ARQUX_DIR / "brain.cortex"
        brain_path = direct if direct.exists() else None
    if brain_path is None:
        return CortexOUT.error(
            "no project brain.cortex found — lessons are filed only in brain $8",
            code="NOT_FOUND",
        )

    try:
        content_text = brain_path.read_text(encoding="utf-8")
        taken = {m.group(1) for m in re.finditer(r"^LNG:([A-Za-z0-9_]+)", content_text, re.M)}
        entry_name = _derive_lesson_name(lesson, taken, name)
        if entry_name in ("_", "*"):  # T-022: '_'/'*' are reserved selector names
            entry_name = "lesson"
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="BRAIN_UPDATE_ERROR")

    value = {
        "type": kind,
        "cause": cause,
        "lesson": lesson,
        "prevention": prevention,
        "agent": agent,
    }

    try:
        from ...core.state._crud import crud_section_id_for_title
        lessons_sec = crud_section_id_for_title(brain_path, "LESSONS", fallback="$8")
        brain_result = crud_add(
            brain_path,
            lessons_sec, "LNG", entry_name, value,
            create_section=True, section_title="LESSONS",
        )
        # F4: only a clean write counts as filed — a crud_add that
        # returned an error must NOT be reported as persisted.
        if "error" in brain_result:
            return CortexOUT.error(brain_result["error"], code="CRUD_ERROR")
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="BRAIN_UPDATE_ERROR")

    scan_candidates = 0
    try:
        from ...learning import scan_brain  # lazy: allow monkeypatch

        project_dir = brain_path.parent.parent
        scan = scan_brain(project_dir, verbose=True)
        scan_candidates = len(scan.get("candidates", []))
    except Exception:  # noqa: BLE001
        pass

    result = CortexOUT.work(
        f"identity.record ok agent={agent} lesson={entry_name} kind={kind}",
        agent=agent,
        kind=kind,
        lesson=entry_name,
        file=str(brain_path),
        destination="brain",
    )
    if scan_candidates:
        result.fields["hint"] = f"{scan_candidates} learning candidate(s) detected — run cortex.learn.elevate to review"
        result.fields["learning_candidates"] = scan_candidates
    else:
        # The recorded lesson itself is a valid learning signal — expose it
        # as a local candidate so auto-trigger consumers (and the native
        # engine contract) get a hint.
        lesson_candidate = {
            "candidate_id": f"cand_lng_{entry_name}",
            "source_entries": [f"LNG:{entry_name}"],
            "target": "KNW",
            "source": "identity.record",
        }
        result.fields["hint"] = "1 learning candidate(s) detected — run cortex.learn.elevate to review"
        result.fields["learning_candidates"] = 1
        result.fields["candidates"] = [lesson_candidate]
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

    _lc = list_candidates(root)
    candidates = scan.get("candidates", []) or ([] if isinstance(_lc, dict) else _lc)

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
