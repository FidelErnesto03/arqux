# ruff: noqa: F401
"""State persistence and discovery helpers.

The framework persists state via CORTEX (`.cortex` + `.md`).
This module provides:
    - Workspace/project root discovery.
    - A thin abstraction over CORTEX for read/write/verify.
    - Project brain operations: the single shared mind of a project.
    - Handoff and pulse operations: stored INSIDE the brain, not in separate files.

Since v0.7.0 (CYCLE-11), ArqUX uses its own CORTEX writer, CRUD, and atomic
write modules (arqux.cortex.writer, arqux.cortex.crud, arqux.cortex.atomic).
CODEC-CORTEX is an OPTIONAL dependency used for parsing/reading and
HCORTEX rendering. If not installed, the framework degrades gracefully
using a built-in fallback parser.
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

# --- CODEC-CORTEX integration (capability-based resolution) ----------------
#
# CODEC-CORTEX changed its public import name AND its surface between the
# two versions ArqUX can be installed against:
#
#   0.6.2 (legacy)   cortex.core.{ast,lexer,parser,validator}
#                    cortex.crud.selectors
#                    cortex.hcortex.read_renderer   -> render_hcortex_read
#
#   1.0.0rc1 (rc1)   codec_cortex.parser           -> parse_cortex
#                    codec_cortex.hcortex           -> compile_hcortex
#                    NO validate, NO render_hcortex_read
#
# The previous code imported only the legacy names and swallowed ImportError,
# so installing the PINNED version (codec-cortex==1.0.0rc1, the `codec` extra)
# silently disabled the entire CORTEX layer: parse AND verify AND render.
# See issue 2026-10-11-la-dependencia-pineada-codec-cortex-1-0-0rc1-es-.
#
# Resolution is now capability-based: bind whatever the installed codec
# actually provides, and report the absent capabilities by name instead of
# collapsing to a single boolean that hides the real cause.

_HAS_CODEC_CORTEX: bool = False
_codec_cortex = None  # type: ignore[assignment]

#: Which API shape was detected: "legacy" | "rc1" | None.
_CODEC_CORTEX_API: str | None = None

#: Capabilities this ArqUX needs that the installed codec does NOT provide.
_CODEC_CORTEX_MISSING: tuple[str, ...] = ()

_cc_ast = _cc_lexer = _cc_parser = _cc_validator = None
_cc_selectors = _cc_renderer = None


def _bind_legacy_api() -> bool:
    """Bind the 0.6.2 layout (``cortex.*``). Returns True on full success."""
    global _cc_ast, _cc_lexer, _cc_parser, _cc_validator  # noqa: PLW0603
    global _cc_selectors, _cc_renderer, _HAS_CODEC_CORTEX  # noqa: PLW0603
    global _codec_cortex, _CODEC_CORTEX_API, _CODEC_CORTEX_MISSING  # noqa: PLW0603

    try:
        import cortex.core.ast as ast_mod
        import cortex.core.lexer as lexer_mod
        import cortex.core.parser as parser_mod
        import cortex.core.validator as validator_mod
        import cortex.crud.selectors as selectors_mod
        import cortex.hcortex.read_renderer as renderer_mod
    except ImportError:
        return False

    _cc_ast = ast_mod
    _cc_lexer = lexer_mod
    _cc_parser = parser_mod
    _cc_validator = validator_mod
    _cc_selectors = selectors_mod
    _cc_renderer = renderer_mod
    _HAS_CODEC_CORTEX = True
    _codec_cortex = True  # sentinel
    _CODEC_CORTEX_API = "legacy"
    _CODEC_CORTEX_MISSING = ()
    return True


def _bind_rc1_api() -> bool:
    """Bind the 1.0.0rc1 layout (``codec_cortex.*``, flat namespace).

    Only ``parse_cortex`` exists there. ``validate`` and
    ``render_hcortex_read`` are absent from the candidate, so their handles
    stay None and are reported in ``_CODEC_CORTEX_MISSING``.
    """
    global _cc_parser, _HAS_CODEC_CORTEX, _codec_cortex  # noqa: PLW0603
    global _CODEC_CORTEX_API, _CODEC_CORTEX_MISSING  # noqa: PLW0603

    try:
        import codec_cortex.parser as parser_mod
    except ImportError:
        return False

    if not hasattr(parser_mod, "parse_cortex"):
        return False

    _cc_parser = parser_mod
    _HAS_CODEC_CORTEX = True
    _codec_cortex = True  # sentinel
    _CODEC_CORTEX_API = "rc1"
    # The rc1 candidate exposes compile_hcortex, not render_hcortex_read, and
    # ships no validator at all. Both handles stay None on purpose: binding a
    # module that lacks the entry point would turn a precise diagnosis into an
    # AttributeError at the call site.
    _CODEC_CORTEX_MISSING = ("validate", "render_hcortex_read")
    return True


if not _bind_legacy_api() and not _bind_rc1_api():
    # BLP-fix (T-005/G-9): CODEC-CORTEX is optional. Define the
    # codec handles as None so that 'from . import _cc_*' at module
    # level in the submodules does not raise ImportError, and the
    # runtime checks via requires_codec_cortex() still gate usage.
    _HAS_CODEC_CORTEX = False
    _codec_cortex = None
    _CODEC_CORTEX_API = None
    _CODEC_CORTEX_MISSING = ("parse_cortex", "validate", "render_hcortex_read")
    _cc_ast = _cc_lexer = _cc_parser = _cc_validator = None
    _cc_selectors = _cc_renderer = None


def codec_cortex_diagnostics() -> dict:
    """Report what the installed CODEC-CORTEX actually provides.

    Returns a dict with the detected API shape, whether CORTEX support is
    active at all, and the capabilities this ArqUX requires that the
    installed codec does not supply. Diagnostic only — never raises.
    """
    return {
        "available": _HAS_CODEC_CORTEX,
        "api": _CODEC_CORTEX_API,
        "missing_capabilities": list(_CODEC_CORTEX_MISSING),
        "can_parse": _cc_parser is not None,
        "can_validate": _cc_validator is not None,
        "can_render_hcortex": _cc_renderer is not None,
    }

# Runtime shim (issue 2026-10-02, schema mismatch verifier<->format):
# codec-cortex <=0.6.2 requires a `name` ATTRIBUTE on every entry, but in
# CODEC-CORTEX the name lives in the KEY (SIGIL:name). Published versions
# still carry the bug, so arqux neutralizes it at load time — the fix
# travels with arqux, NOT with codec-cortex (which stays untouched).
if _HAS_CODEC_CORTEX:
    try:
        from cortex.core.schema import SchemaResolver as _SchemaResolver

        _SchemaResolver.ALWAYS_REQUIRED = frozenset()
    except Exception:  # noqa: BLE001  # best-effort shim, never blocks startup
        pass

# BLP-005: These CODEC modules have been removed from ArqUX.
# They are kept as None for backward-compatibility with any code
# that still references them (e.g. state.py re-exports).
_cc_writer = None
_cc_mutations = None
_cc_transactions = None

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
