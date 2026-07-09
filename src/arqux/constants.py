"""Module-level constants for Arqux.

All placeholder-derived identifiers live here so the rename script has a single
canonical surface to swap. After running `scripts/rename-product.py <name>`:

    arqux            -> <name>           (lowercase, package/cli/paths)
    ARQUX      -> <NAME>           (uppercase, constants/markers)
    Arqux      -> <Name>           (title case, display names)
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Identity --------------------------------------------------------------

#: Lowercase product name. Used as the package name, CLI command, and the
#: governance directory name (e.g. `.<product>/`).
PRODUCT_NAME: str = "arqux"

#: Uppercase product name. Used for environment variables and constants.
PRODUCT_NAME_UPPER: str = "ARQUX"

#: Title-case product name. Used in human-readable documentation.
PRODUCT_NAME_TITLE: str = "Arqux"

#: Version string — single source of truth.
ARQUX_VERSION: str = "0.4.2"

# --- Filesystem layout -----------------------------------------------------

#: Name of the governance directory created inside a workspace or project.
ARQUX_DIR: str = f".{PRODUCT_NAME}"

#: Environment variable prefix for runtime configuration.
ARQUX_ENV_PREFIX: str = f"{PRODUCT_NAME_UPPER}_"

#: Default workspace manifest file (machine-readable).
MANIFEST_CORTEX: str = "manifest.cortex"

#: Default workspace manifest file (human-readable).
MANIFEST_HCORTEX: str = "manifest.md"

#: Workspace-level projects index (machine-readable).
PROJECTS_CORTEX: str = "projects.cortex"

#: Workspace-level projects index (human-readable).
PROJECTS_HCORTEX: str = "projects.md"

#: Project-level brain (machine-readable).
BRAIN_CORTEX: str = "brain.cortex"

#: Project-level brain (human-readable).
BRAIN_HCORTEX: str = "brain.md"

#: Workspace-level meta-brain (machine-readable).
META_BRAIN_CORTEX: str = "meta-brain.cortex"

#: Workspace-level meta-brain (human-readable).
META_BRAIN_HCORTEX: str = "meta-brain.md"

#: Per-cycle tasks directory.
TASKS_DIR: str = "tasks"

#: Per-project cycles directory.
CYCLES_DIR: str = "cycles"
BLUEPRINTS_DIR: str = "blueprints"

# --- Brain sections (the project brain is the single shared mind) -----------
#
# The brain.cortex is the shared project mind. All handoffs, pulses,
# sessions, lessons, focus, and active context live HERE — not in separate
# files. This guarantees that every agent bound to the project shares the
# same mental state.

BRAIN_SECTION_FOCUS: str = "FOCUS"
BRAIN_SECTION_OBJECTIVES: str = "OBJECTIVES"
BRAIN_SECTION_SESSIONS: str = "SESSIONS"
BRAIN_SECTION_HANDOFFS: str = "HANDOFFS"
BRAIN_SECTION_PULSE: str = "PULSE"
BRAIN_SECTION_LESSONS: str = "LESSONS"
BRAIN_SECTION_ACTIVE_CONTEXT: str = "ACTIVE_CONTEXT"
BRAIN_SECTION_RISKS: str = "RISKS"
BRAIN_SECTION_CONCURRENCY: str = "CONCURRENCY"

#: All canonical brain sections (used for validation).
ALL_BRAIN_SECTIONS: tuple[str, ...] = (
    BRAIN_SECTION_FOCUS,
    BRAIN_SECTION_OBJECTIVES,
    BRAIN_SECTION_SESSIONS,
    BRAIN_SECTION_HANDOFFS,
    BRAIN_SECTION_PULSE,
    BRAIN_SECTION_LESSONS,
    BRAIN_SECTION_ACTIVE_CONTEXT,
    BRAIN_SECTION_RISKS,
    BRAIN_SECTION_CONCURRENCY,
)

# --- Roles and permissions -------------------------------------------------

ROLE_GOVERNOR: str = "governor"
ROLE_EXECUTOR: str = "executor"
ROLE_AUDITOR: str = "auditor"

ALL_ROLES: tuple[str, ...] = (ROLE_GOVERNOR, ROLE_EXECUTOR, ROLE_AUDITOR)

# --- Task state machine ----------------------------------------------------

TASK_DRAFT: str = "draft"
TASK_OPEN: str = "open"
TASK_IN_PROGRESS: str = "in_progress"
TASK_REVIEW: str = "review"
TASK_DONE: str = "done"
TASK_BLOCKED: str = "blocked"
TASK_CANCELLED: str = "cancelled"

TASK_ACTIVE_STATES: tuple[str, ...] = (
    TASK_DRAFT,
    TASK_OPEN,
    TASK_IN_PROGRESS,
    TASK_REVIEW,
    TASK_BLOCKED,
)

TASK_TERMINAL_STATES: tuple[str, ...] = (TASK_DONE, TASK_CANCELLED)

TASK_TRANSITIONS: dict[str, tuple[str, ...]] = {
    TASK_DRAFT: (TASK_OPEN, TASK_CANCELLED),
    TASK_OPEN: (TASK_IN_PROGRESS, TASK_CANCELLED),
    TASK_IN_PROGRESS: (TASK_REVIEW, TASK_BLOCKED, TASK_DONE, TASK_CANCELLED),
    TASK_REVIEW: (TASK_DONE, TASK_IN_PROGRESS, TASK_BLOCKED, TASK_CANCELLED),
    TASK_BLOCKED: (TASK_IN_PROGRESS, TASK_CANCELLED),
    TASK_DONE: (),
    TASK_CANCELLED: (),
}

# --- Cycle state machine ---------------------------------------------------

CYCLE_OPEN: str = "open"
CYCLE_CLOSED: str = "closed"

CYCLE_TRANSITIONS: dict[str, tuple[str, ...]] = {
    CYCLE_OPEN: (CYCLE_CLOSED,),
    CYCLE_CLOSED: (),
}

# --- CORTEX-OUT profiles ---------------------------------------------------

OUT_MIN: str = "OUT-MIN"
OUT_WORK: str = "OUT-WORK"
OUT_AUDIT: str = "OUT-AUDIT"
OUT_FULL: str = "OUT-FULL"
OUT_ERROR: str = "OUT-ERROR"

ALL_OUT_PROFILES: tuple[str, ...] = (
    OUT_MIN,
    OUT_WORK,
    OUT_AUDIT,
    OUT_FULL,
    OUT_ERROR,
)

DEFAULT_OUT_PROFILE: str = OUT_WORK

# --- Error codes -----------------------------------------------------------

PERMISSION_DENIED: str = "PERMISSION_DENIED"
NOT_FOUND: str = "NOT_FOUND"
INVALID_STATE: str = "INVALID_STATE"
INVALID_ARGUMENT: str = "INVALID_ARGUMENT"
ALREADY_EXISTS: str = "ALREADY_EXISTS"
INTERNAL_ERROR: str = "INTERNAL_ERROR"

# --- Paths -----------------------------------------------------------------

PACKAGE_ROOT: Path = Path(__file__).resolve().parent
TEMPLATES_DIR: Path = PACKAGE_ROOT / "templates"
IDENTITIES_DIR: Path = PACKAGE_ROOT / "identities"

# --- Environment overrides -------------------------------------------------

def env(var: str, default: str | None = None) -> str | None:
    """Read an environment variable prefixed with the product name."""
    return os.environ.get(f"{ARQUX_ENV_PREFIX}{var}", default)
