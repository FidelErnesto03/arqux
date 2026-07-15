"""Module-level constants for Arqux.

All placeholder-derived identifiers live here so the rename script has a single
canonical surface to swap. After running `scripts/rename-product.py <name>`:

    arqux            -> <name>           (lowercase, package/cli/paths)
    ARQUX      -> <NAME>           (uppercase, constants/markers)
    Arqux      -> <Name>           (title case, display names)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# --- Identity --------------------------------------------------------------

#: Lowercase product name. Used as the package name, CLI command, and the
#: governance directory name (e.g. `.<product>/`).
PRODUCT_NAME: str = "arqux"

#: Uppercase product name. Used for environment variables and constants.
PRODUCT_NAME_UPPER: str = "ARQUX"

#: Title-case product name. Used in human-readable documentation.
PRODUCT_NAME_TITLE: str = "Arqux"

#: Version string — single source of truth.
ARQUX_VERSION: str = "0.6.0"

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


# === BLP-041: ARQX:artifact sigil in $0.1 ====================================
#
# ARQX:artifact is an attrs entry in section $0.1 of every .cortex file,
# declaring:
#   level  → architectural level (0=PACKAGE, 1=BEHAVIORAL, 2=SKILL, 3=BRAIN)
#   name   → canonical artifact name (e.g. "brain", "jarvis", "owasp-top10")
#   usage  → semantic role (state|skill|identity|lesson|config)
#   kind   → provenance (native|inherited|adapted)
#
# It is declared (not inferred): every .cortex file MUST carry an ARQX:artifact
# entry. Files without it degrade to NIVEL 0 + Warning W001.
# The ARQX sigil is registered in the $0 pipe-table so CODEC-CORTEX recognizes
# it as a valid attrs sigil. Section $0.1 (not $0) avoids E033.


class CortexLevel(Enum):
    """Architectural level of a .cortex artifact (BLP-035)."""
    PACKAGE = 0       # Level 0: lessons, configs, raw packages
    BEHAVIORAL = 1    # Level 1: identity contracts (agents)
    SKILL = 2         # Level 2: skill files (.skill.md)
    BRAIN = 3         # Level 3: project brain (brain.cortex)

    @classmethod
    def from_int(cls, value: int) -> CortexLevel:
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"Invalid level: {value}. Must be 0-3.") from exc


class ArtifactKind(Enum):
    """Provenance of an artifact (BLP-035 / BLP-040)."""
    NATIVE = "native"          # created inside this workspace
    INHERITED = "inherited"    # imported from a third-party upstream
    ADAPTED = "adapted"        # local fork of an inherited artifact

    @classmethod
    def from_str(cls, value: str) -> ArtifactKind:
        for k in cls:
            if k.value == value:
                return k
        raise ValueError(f"Invalid kind: {value!r}. Must be native|inherited|adapted.")


class ArtifactUsage(Enum):
    """Semantic role of an artifact (BLP-035)."""
    STATE = "state"        # project brain / live state
    SKILL = "skill"        # procedural skill file
    IDENTITY = "identity"  # agent identity contract
    LESSON = "lesson"      # raw lesson store (Nivel 0)
    CONFIG = "config"      # configuration / glossary

    @classmethod
    def from_str(cls, value: str) -> ArtifactUsage:
        for u in cls:
            if u.value == value:
                return u
        raise ValueError(
            f"Invalid usage: {value!r}. Must be state|skill|identity|lesson|config."
        )


@dataclass(frozen=True)
class ArtifactMetadata:
    """Technical identity of a .cortex artifact (BLP-041).

    The ARQX:artifact entry in $0.1 declares level, name, usage, kind.
    Optional fields (agent, source, upstream_version) are kept for
    BLP-038/BLP-040 extensions.
    """
    level: CortexLevel
    name: str
    usage: ArtifactUsage
    kind: ArtifactKind
    # Optional provenance fields (BLP-038 conductual / BLP-040 procedural):
    agent: str | None = None
    source: str | None = None
    upstream_version: str | None = None

    @staticmethod
    def default(level: int = 0) -> ArtifactMetadata:
        """Return a default metadata for the given level.

        Used when a .cortex file lacks ARQX:artifact — the file degrades to
        NIVEL 0 (PACKAGE) with a default identity and emits W001_NO_METADATA.
        """
        return ArtifactMetadata(
            level=CortexLevel.from_int(level),
            name="<unknown>",
            usage=ArtifactUsage.CONFIG,
            kind=ArtifactKind.NATIVE,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "level": self.level.value,
            "name": self.name,
            "usage": self.usage.value,
            "kind": self.kind.value,
        }
        if self.agent is not None:
            d["agent"] = self.agent
        if self.source is not None:
            d["source"] = self.source
        if self.upstream_version is not None:
            d["upstream_version"] = self.upstream_version
        return d


# === BLP-036: BrainSection enum (13 canonical sections $0..$12) ============

class BrainSection(Enum):
    """Canonical 13 sections of a Level-3 Brain artifact (BLP-036).

    Maps to niveles-cortex-arqux.md v3.0: $0 through $12 ISSUES.
    ArqUX metadata lives in $0.1 (BLP-041), not $0.
    The enum value is the section identifier used in the .cortex file
    (with the leading ``$``).
    """
    METADATA = "$0"
    IDENTITY = "$1"
    KNOWLEDGE = "$2"
    FOCUS = "$3"
    OBJECTIVES = "$4"
    STATE = "$5"
    LESSONS = "$6"
    DECISIONS = "$7"
    AXIOMS = "$8"
    LIMITS = "$9"
    HANDOFF = "$10"
    CONCURRENCY = "$11"
    ISSUES = "$12"

    @property
    def number(self) -> int:
        """Numeric section index (0..12)."""
        return int(self.value[1:])

    @classmethod
    def all_ids(cls) -> list[str]:
        """Return the 13 canonical section ids in order."""
        return [s.value for s in cls]


#: Mapping from BrainSection → human-readable title (for structural validation).
BRAIN_SECTION_TITLES: dict[str, str] = {
    "$0": "GLOSSARY",
    "$1": "IDENTITY",
    "$2": "KNOWLEDGE",
    "$3": "FOCUS",
    "$4": "OBJECTIVES",
    "$5": "STATE",
    "$6": "LESSONS",
    "$7": "DECISIONS",
    "$8": "AXIOMS",
    "$9": "LIMITS",
    "$10": "HANDOFF",
    "$11": "CONCURRENCY",
    "$12": "ISSUES",
}


# === BLP-037: Active-state status whitelist/blacklist =======================

#: Statuses that count as "vigente" (alive) for FCS/OBJ semantic validation.
#: A project brain with at least one FCS in these states is NOT zombie.
VALID_STATUSES: frozenset[str] = frozenset({
    "current",
    "active",
    "pending",
    "blocked",
    "paused",
})

#: Statuses that count as "inerte" (dead) for FCS/OBJ semantic validation.
#: A project brain where ALL FCS/OBJ are in these states is zombie.
INVALID_STATUSES: frozenset[str] = frozenset({
    "done",
    "archived",
    "dropped",
    "cancelled",
})


# === BLP-035 warning codes ==================================================

#: Warning code emitted when a .cortex file lacks ARQX:artifact.
W001_NO_METADATA: str = "W001_NO_METADATA"

#: Warning code emitted when a Brain artifact has fewer than 8 active sections.
W002_INCOMPLETE_BRAIN: str = "W002_INCOMPLETE_BRAIN"

#: Warning code emitted when a behavioral lesson has expired (BLP-038).
W003_LEARNING_DEBT_BEHAVIORAL: str = "W003_LEARNING_DEBT_BEHAVIORAL"

#: Warning code emitted when an inherited skill is stale vs upstream (BLP-040).
W004_STALE_INHERITED_SKILL: str = "W004_STALE_INHERITED_SKILL"

#: Warning code emitted when an AdaptedStore entry lacks original_ref (BLP-040).
W005_MISSING_ORIGINAL_REF: str = "W005_MISSING_ORIGINAL_REF"


# === BLP-037 / BLP-036 error codes ==========================================

#: BRAIN without any active FCS (CRITICAL).
E024_LEVEL3_MISSING_FOCUS: str = "E024_LEVEL3_MISSING_FOCUS"

#: BRAIN section is malformed (e.g. misnamed sigil).
E026_MISSING_SECTION: str = "E026_MISSING_SECTION"

#: BRAIN section has a sigil with wrong naming.
E027_MALFORMED_SECTION: str = "E027_MALFORMED_SECTION"

#: BRAIN with no active objectives (HIGH).
E028_NO_ACTIVE_OBJECTIVES: str = "E028_NO_ACTIVE_OBJECTIVES"
