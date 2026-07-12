# ruff: noqa: F401
"""State persistence and discovery helpers.

The framework persists state via CODEC-CORTEX (`.cortex` + `.md`).
This module provides:
    - Workspace/project root discovery.
    - A thin abstraction over CODEC-CORTEX for read/write/verify.
    - Project brain operations: the single shared mind of a project.
    - Handoff and pulse operations: stored INSIDE the brain, not in separate files.

CODEC-CORTEX is a REQUIRED dependency. If not installed, the framework will
not start. The old YAML-frontmatter fallback is preserved for backward
compatibility with existing `.arqux/` files produced by v1.0.0, but all NEW
files are written in proper CODEC-CORTEX sigil format when available.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ... import formats
from ...constants import (
    ARQUX_DIR,
    BRAIN_CORTEX,
    BRAIN_SECTION_ACTIVE_CONTEXT,
    BRAIN_SECTION_CONCURRENCY,
    BRAIN_SECTION_FOCUS,
    BRAIN_SECTION_HANDOFFS,
    BRAIN_SECTION_LESSONS,
    BRAIN_SECTION_OBJECTIVES,
    BRAIN_SECTION_PULSE,
    BRAIN_SECTION_RISKS,
    BRAIN_SECTION_SESSIONS,
    CYCLES_DIR,
    MANIFEST_CORTEX,
    META_BRAIN_CORTEX,
    PRODUCT_NAME,
    PRODUCT_NAME_UPPER,
    PROJECTS_CORTEX,
    TASKS_DIR,
)

#: Name of the session context file inside ``.arqux/``.
CONTEXT_CORTEX: str = "context.cortex"

# --- CODEC-CORTEX integration (REQUIRED) -----------------------------------

_HAS_CODEC_CORTEX: bool = False
_codec_cortex = None  # type: ignore[assignment]

try:
    import cortex.core.ast as _cc_ast
    import cortex.core.lexer as _cc_lexer
    import cortex.core.parser as _cc_parser
    import cortex.core.validator as _cc_validator
    import cortex.core.writer as _cc_writer
    import cortex.crud.mutations as _cc_mutations
    import cortex.crud.selectors as _cc_selectors
    import cortex.crud.transactions as _cc_transactions
    import cortex.hcortex.read_renderer as _cc_renderer

    _HAS_CODEC_CORTEX = True
    _codec_cortex = True  # sentinel
except ImportError:
    _HAS_CODEC_CORTEX = False
    pass

# --- Import and re-export submodules ---------------------------------------

from ._brain import (
    _bump_concurrency,
    _initial_brain_body,
    _now_iso,
    _resolve_brain_path,
    append_to_brain_section,
    brain_version,
    cycle_dir,
    ensure_brain_section,
    next_cycle_id,
    next_task_id,
    read_brain,
    task_path,
    write_brain,
    write_brain_sections,
    write_manifest,
    write_meta_brain,
    write_projects_index,
)
from ._crud import (
    _parse_and_mutate,
    cortex_read,
    cortex_render,
    cortex_verify,
    cortex_write,
    crud_add,
    crud_delete,
    crud_list,
    crud_move,
    crud_read,
    crud_update,
    requires_codec_cortex,
)
from ._migrate import (
    migrate_cortex_file,
)
from ._parse import (
    parse_brain_sections,
    rebuild_brain_body,
)
from ._project import (
    WorkspaceRoot,
    find_project_root,
    find_workspace_root,
    parse_cortex_file,
)
from ._render import (
    _render_cortex,
    _render_governance_cortex,
    _render_hcortex,
    _write_md_twin,
    _yaml_value,
    write_cortex_pair,
)
