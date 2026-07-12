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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ...constants import (
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
    ARQUX_DIR,
)
from ... import formats

#: Name of the session context file inside ``.arqux/``.
CONTEXT_CORTEX: str = "context.cortex"

# --- CODEC-CORTEX integration (REQUIRED) -----------------------------------

_HAS_CODEC_CORTEX: bool = False
_codec_cortex = None  # type: ignore[assignment]

try:
    import cortex.core.ast as _cc_ast
    import cortex.core.parser as _cc_parser
    import cortex.core.writer as _cc_writer
    import cortex.core.validator as _cc_validator
    import cortex.crud.mutations as _cc_mutations
    import cortex.crud.selectors as _cc_selectors
    import cortex.crud.transactions as _cc_transactions
    import cortex.hcortex.read_renderer as _cc_renderer
    import cortex.core.lexer as _cc_lexer

    _HAS_CODEC_CORTEX = True
    _codec_cortex = True  # sentinel
except ImportError:
    _HAS_CODEC_CORTEX = False
    pass

# --- Import and re-export submodules ---------------------------------------

from ._crud import (
    requires_codec_cortex,
    cortex_read,
    cortex_write,
    cortex_verify,
    cortex_render,
    _parse_and_mutate,
    crud_read,
    crud_add,
    crud_update,
    crud_delete,
    crud_move,
    crud_list,
)

from ._render import (
    write_cortex_pair,
    _render_governance_cortex,
    _write_md_twin,
    _render_cortex,
    _render_hcortex,
    _yaml_value,
)

from ._migrate import (
    migrate_cortex_file,
)

from ._parse import (
    parse_brain_sections,
    rebuild_brain_body,
)

from ._brain import (
    _resolve_brain_path,
    read_brain,
    write_brain_sections,
    ensure_brain_section,
    append_to_brain_section,
    _bump_concurrency,
    brain_version,
    write_manifest,
    write_meta_brain,
    write_projects_index,
    write_brain,
    _initial_brain_body,
    cycle_dir,
    task_path,
    next_task_id,
    next_cycle_id,
    _now_iso,
)

from ._project import (
    parse_cortex_file,
    WorkspaceRoot,
    find_workspace_root,
    find_project_root,
)
