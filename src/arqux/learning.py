"""Learning adapter — bridges Arqux governance state with CODEC-CORTEX Learning Engine (CLE).

The adapter translates between Arqux's ``.arqux/brain.cortex`` sections dict
and the CODEC-CORTEX ``CortexDocument`` / ``Entry`` objects that the learning
engine operates on.  The policy file ``learn-policies.cortex`` (stored in
``.arqux/``) controls scoring thresholds, elevation rules, and protected sigils.

Pipeline::

    read_brain() ─→ sections dict
        │
        ▼  _build_brain_doc()
    CortexDocument ─→ Entry objects
        │
        ▼  rebuild_index()
    LearnIndex ─→ ScoreRecord per entry
        │
        ▼  detect_candidates()
    Candidates ─→ SES→LNG, LNG→KNW proposals
        │
        ▼  plan_patch() → apply_patch()
    Elevated brain.cortex
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import ARQUX_DIR, BRAIN_CORTEX, BRAIN_SECTION_LESSONS, BRAIN_SECTION_PULSE

_HAS_CLE: bool = False
try:
    from cortex.core.ast import CortexDocument, Entry
    from cortex.core.parser import parse_cortex
    from cortex.core.writer import write_cortex
    from cortex.learning.index import rebuild_index
    from cortex.learning.policy import parse_policy_document
    from cortex.learning.candidates import detect_candidates
    from cortex.learning.elevation import plan_patch, apply_patch, render_diff
    from cortex.learning.errors import LearningError

    _HAS_CLE = True
except ImportError:
    CortexDocument = None  # type: ignore
    Entry = None  # type: ignore


POLICY_FILENAME = "learn-policies.cortex"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_project_root(path: str | None) -> Path | None:
    """Find the project root (parent of .arqux/) from ``path`` or cwd."""
    from .state import find_project_root
    result = find_project_root(start=path)
    if result is None:
        return None
    # find_project_root returns .arqux/ path. Return its parent.
    return result.parent


def _load_policies(project_root: Path) -> Any | None:
    """Load learn-policies.cortex from ``.arqux/``.

    Returns a ``LearningPolicySet`` or ``None`` (policy invalid). If the
    project-local policy is missing, fall back to the packaged default so
    migrated projects can still run cortex.learn before policy seeding.
    """
    if not _HAS_CLE:
        return None
    policy_path = _resolve_policy_path(project_root)
    if not policy_path.exists():
        return None
    from cortex.core.parser import parse_cortex
    doc = parse_cortex(policy_path.read_text(encoding="utf-8"))
    if not doc:
        return None
    return parse_policy_document(doc)


def _resolve_policy_path(project_root: Path) -> Path:
    """Return project policy path or packaged default fallback."""
    project_policy = project_root / ARQUX_DIR / POLICY_FILENAME
    if project_policy.exists():
        return project_policy
    return Path(__file__).resolve().parent / "templates" / POLICY_FILENAME


def _build_brain_doc(project_root: Path) -> CortexDocument | None:
    """Build a CortexDocument from the project's brain.cortex sections.

    Uses the existing ``formats._build_brain_doc()`` to convert sections
    dict → CortexDocument so the learning engine can process it.
    """
    from .state import read_brain
    from .formats import _build_brain_doc as _build_doc
    from cortex.core.ast import CortexDocument as CDoc

    fm, sections, _ = read_brain(project_root)
    doc = CDoc()
    _build_doc(doc, fm, sections)
    return doc


def _hash_text(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _preview_hash(diff: str) -> str:
    """Stable approval token for an exact learning elevation preview."""
    return _hash_text(diff)


def _planned_entry(target: Any) -> tuple[str, str, dict[str, Any]]:
    """Return the entry that would be written for a learning candidate."""
    new_sigil = target.target
    new_name = getattr(target, "candidate_id", "elevated")
    new_value = {
        "topic": "elevated_knowledge",
        "content": str(getattr(target, "source_entries", [])),
        "status": "active",
    }
    return new_sigil, new_name, new_value


def _validate_elevation_payload(
    new_sigil: str,
    new_value: dict[str, Any],
    diff: str,
) -> list[str]:
    """Return blocking problems in a proposed learning elevation."""
    problems: list[str] = []
    serialized_values = [str(v).strip() for v in new_value.values()]
    if any(v in {"", "[]", "{}", "None"} for v in serialized_values):
        problems.append("proposed elevation contains empty fields")
    generic_markers = [
        "elevated_outcome",
        'input:""',
        'output:""',
        'date:""',
        'input=""',
        'output=""',
        'date=""',
    ]
    if any(marker in diff for marker in generic_markers):
        problems.append("proposed elevation contains generic or placeholder content")
    if new_sigil not in {"SES", "LNG", "KNW"}:
        problems.append(f"unexpected elevation target: {new_sigil}")
    return problems


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_brain(
    project_root: Path,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Scan the project brain through the learning engine.

    Returns a dict with:
        - entries: list of scored entries (id, sigil, hotness, promotion, risk, priority, action)
        - candidates: list of detected elevation candidates
        - count: total entries scanned
        - engine: available or unavailable
    """
    result: dict[str, Any] = {
        "engine": "unavailable",
        "count": 0,
        "entries": [],
        "candidates": [],
    }

    if not _HAS_CLE:
        return result
    result["engine"] = "available"

    try:
        # 1. Load brain and policies
        brain_doc = _build_brain_doc(project_root)
        if not brain_doc:
            return {**result, "error": "could_not_build_document"}

        policy_set = _load_policies(project_root)
        if not policy_set:
            return {**result, "error": "policies_not_found"}

        # 2. Brain hash (simple fingerprint)
        brain_path = project_root / ARQUX_DIR / BRAIN_CORTEX
        brain_hash = _hash_text(brain_path.read_text(encoding="utf-8"))
        policy_path = _resolve_policy_path(project_root)
        policy_hash = _hash_text(policy_path.read_text(encoding="utf-8"))

        # 3. Rebuild index — this runs all scoring
        index = rebuild_index(
            brain_doc,
            policy_set,
            brain_hash,
            policy_hash,
        )

        # 4. Build entry list
        entries = []
        for eid, record in sorted(index.entries.items(), key=lambda x: x[1].read_priority):
            entries.append({
                "id": eid,
                "fingerprint": record.fingerprint,
                "hotness": record.hotness_score,
                "promotion": record.promotion_score,
                "risk": record.risk_weight,
                "priority": record.read_priority,
                "action": record.suggested_action,
                "signals": record.signals,
            })
        result["count"] = len(entries)
        result["entries"] = entries

        # 5. Detect candidates
        if verbose:
            candidates = detect_candidates(brain_doc, index, policy_set)
            result["candidates"] = [
                {
                    "id": c.candidate_id,
                    "source": c.source_entries,
                    "target": c.target,
                    "promotion_score": c.promotion_score,
                    "hotness_score": c.hotness_score,
                }
                for c in candidates
            ]

    except Exception as exc:
        return {**result, "error": str(exc)}

    return result


def list_candidates(
    project_root: Path,
) -> list[dict[str, Any]]:
    """List elevation candidates for the project."""
    if not _HAS_CLE:
        return []

    try:
        brain_doc = _build_brain_doc(project_root)
        if not brain_doc:
            return []

        policy_set = _load_policies(project_root)
        if not policy_set:
            return []

        brain_path = project_root / ARQUX_DIR / BRAIN_CORTEX
        brain_hash = _hash_text(brain_path.read_text(encoding="utf-8"))
        policy_path = _resolve_policy_path(project_root)
        policy_hash = _hash_text(policy_path.read_text(encoding="utf-8"))

        index = rebuild_index(brain_doc, policy_set, brain_hash, policy_hash)
        candidates = detect_candidates(brain_doc, index, policy_set)

        return [
            {
                "id": c.candidate_id,
                "source": c.source_entries,
                "target": c.target,
                "promotion_score": c.promotion_score,
                "hotness_score": c.hotness_score,
            }
            for c in candidates
        ]
    except Exception:
        return []


def elevate_candidate(
    project_root: Path,
    candidate_id: str,
    *,
    dry_run: bool = True,
    confirm_hash: str | None = None,
) -> dict[str, Any]:
    """Elevate a candidate (SES→LNG or LNG→KNW).

    When ``dry_run=True`` (default), returns the diff without applying.
    When ``dry_run=False``, applies the elevation to brain.cortex.
    """
    if not _HAS_CLE:
        return {"error": "learning engine unavailable"}

    try:
        brain_doc = _build_brain_doc(project_root)
        if not brain_doc:
            return {"error": "could_not_build_document"}

        policy_set = _load_policies(project_root)
        if not policy_set:
            return {"error": "policies_not_found"}

        # Rebuild index and find the candidate
        brain_path = project_root / ARQUX_DIR / BRAIN_CORTEX
        brain_hash = _hash_text(brain_path.read_text(encoding="utf-8"))
        policy_path = _resolve_policy_path(project_root)
        policy_hash = _hash_text(policy_path.read_text(encoding="utf-8"))

        index = rebuild_index(brain_doc, policy_set, brain_hash, policy_hash)
        candidates = detect_candidates(brain_doc, index, policy_set)

        target = None
        for c in candidates:
            if c.candidate_id == candidate_id:
                target = c
                break
        if target is None:
            return {"error": f"candidate {candidate_id!r} not found"}

        # Plan the patch
        patch = plan_patch(brain_doc, policy_set, target)
        if patch.mode == "block":
            return {"error": f"elevation blocked by policy: {patch.block_reason}"}

        diff = render_diff(brain_doc, patch)
        preview_hash = _preview_hash(diff)

        new_sigil = patch.new_entry_sigil or target.target
        new_name = patch.new_entry_name
        new_value = patch.new_entry_value
        if not new_name or not new_value:
            fallback_sigil, fallback_name, fallback_value = _planned_entry(target)
            new_sigil = new_sigil or fallback_sigil
            new_name = new_name or fallback_name
            new_value = new_value or fallback_value

        validation_errors = _validate_elevation_payload(new_sigil, new_value, diff)

        if dry_run:
            return {
                "mode": "dry_run",
                "diff": diff,
                "candidate": candidate_id,
                "preview_hash": preview_hash,
                "validation_errors": validation_errors,
            }

        if confirm_hash != preview_hash:
            return {
                "error": (
                    "preview approval required before applying elevation. "
                    "Run dry-run, review the exact diff, then pass confirm_hash."
                ),
                "preview_hash": preview_hash,
                "diff": diff,
            }

        if validation_errors:
            return {
                "error": "unsafe elevation blocked: " + "; ".join(validation_errors),
                "preview_hash": preview_hash,
                "diff": diff,
            }

        # Apply manually: add the elevated entry to KNOWLEDGE section.
        from .state import read_brain, write_brain_sections
        from .formats import _build_brain_doc as _build_doc

        # Read current brain, add to KNOWLEDGE section
        fm, sections, _ = read_brain(project_root)
        knw_line = f"{new_sigil}:{new_name} " + " ".join(f'{k}="{v}"' for k, v in new_value.items())
        existing = sections.get("KNOWLEDGE", "").strip()
        if existing:
            sections["KNOWLEDGE"] = existing + "\n" + knw_line
        else:
            sections["KNOWLEDGE"] = knw_line
        write_brain_sections(project_root, fm, sections)

        return {"mode": "applied", "diff": diff, "candidate": candidate_id, "preview_hash": preview_hash}

    except Exception as exc:
        return {"error": str(exc)}


def build_profile(
    project_root: Path,
) -> dict[str, Any]:
    """Produce a load priority profile (P0-P5) for the project brain."""
    scan = scan_brain(project_root)
    if "entries" not in scan:
        return {"error": "scan_failed", "engine": scan.get("engine", "unavailable")}

    profile: dict[str, int] = {}
    for entry in scan["entries"]:
        p = entry.get("priority", "P3")
        profile[p] = profile.get(p, 0) + 1

    return {
        "engine": scan.get("engine", "unavailable"),
        "total": scan.get("count", 0),
        "profile": dict(sorted(profile.items())),
    }
