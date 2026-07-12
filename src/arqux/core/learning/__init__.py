"""Learning engine — package split.

Submodules:

* ``_common``  — shared helpers, CLE imports, policy loading
* ``_scan``    — scanning, candidate listing, profile building
* ``_elevate`` — contextual candidate elevation
* ``_lesson``  — LessonStore, Lesson, behavioral exceptions
* ``_unified`` — unified ``elevate()``, ``BlueprintDraft``
"""
from __future__ import annotations

# Shared helpers ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
from ._common import (
    POLICY_FILENAME,
    _HAS_CLE,
    _build_brain_doc,
    _hash_text,
    _load_policies,
    _resolve_policy_path,
    _resolve_project_root,
    logger,
)

# Scanning ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
from ._scan import (
    build_profile,
    list_candidates,
    scan_brain,
)

# Contextual elevation ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
from ._elevate import (
    _planned_entry,
    _preview_hash,
    _validate_elevation_payload,
    elevate_candidate,
)

# Behavioral learning — models & exceptions ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
from ._models import (
    Lesson,
    LessonNotFoundError,
    InsufficientConfidenceError,
    InvalidLessonStatusError,
    ContainerIdentityError,
    AgentIdentityError,
)

from ._lesson import (
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_OCCURRENCES,
    DEFAULT_TTL_CYCLES,
    LessonStore,
)

# Unified three-line API ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
from ._unified import (
    BlueprintDraft,
    _draft_to_dict,
    _resolve_behavioral_paths,
    elevate,
)
