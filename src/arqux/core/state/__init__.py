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

#: Which API shape was detected: "v1" | None.
_CODEC_CORTEX_API: str | None = None

#: Capabilities this ArqUX needs that the installed codec does NOT provide.
_CODEC_CORTEX_MISSING: tuple[str, ...] = ()

_cc_ast = _cc_lexer = _cc_parser = _cc_validator = None
_cc_selectors = _cc_renderer = None
_cc_canonicalize = None


def _bind_v1_api() -> bool:
    """Bind CODEC-CORTEX 1.0.x (flat ``codec_cortex`` namespace).

    The codec supplies *format* only: ``parse_cortex``/``canonicalize``
    are adapted into the ArqUX-owned model
    (:mod:`arqux.cortex.model`).  ``validate``, ``render_hcortex_read``
    and the selectors are ArqUX-native
    (:mod:`arqux.cortex.level_policy`, :mod:`arqux.cortex.read_renderer`,
    :mod:`arqux.cortex.selectors`) — learning, governance semantics and
    CRUD never come from the codec.

    Requires the full 1.0.x surface (``dispatcher`` or ``hcortex``
    present). The legacy ``cortex`` 0.6.x package and the 1.0.0rc1
    candidate are not bound at all: the pin (codec-cortex>=1.0,<1.1)
    excludes both, and either present manually would fail closed here
    rather than bind a codec missing validate/render capabilities.
    """
    global _cc_parser, _cc_validator, _cc_selectors, _cc_renderer  # noqa: PLW0603
    global _HAS_CODEC_CORTEX, _codec_cortex  # noqa: PLW0603
    global _CODEC_CORTEX_API, _CODEC_CORTEX_MISSING  # noqa: PLW0603
    global _cc_canonicalize  # noqa: PLW0603

    try:
        import codec_cortex.dispatcher as dispatcher_mod
        _v1_parse_cortex = dispatcher_mod.parse_cortex
        _v1_canonicalize = getattr(dispatcher_mod, "canonicalize", None)
    except (ImportError, AttributeError):
        try:
            import codec_cortex.hcortex  # noqa: F401 — full 1.0.x surface
            import codec_cortex.parser as parser_mod
            _v1_parse_cortex = parser_mod.parse_cortex
            _v1_canonicalize = None
        except (ImportError, AttributeError):
            return False

    import types as _types

    from arqux.cortex import level_policy, model, read_renderer, selectors

    def _parse(text, path="<string>"):
        return model.from_codec_v1(_v1_parse_cortex(text), path=path)

    _cc_parser = _types.SimpleNamespace(parse_cortex=_parse)
    _cc_canonicalize = _v1_canonicalize
    _cc_validator = level_policy
    _cc_selectors = selectors
    _cc_renderer = read_renderer
    _HAS_CODEC_CORTEX = True
    _codec_cortex = True  # sentinel
    _CODEC_CORTEX_API = "v1"
    _CODEC_CORTEX_MISSING = ()
    return True


if not _bind_v1_api():
    # codec-cortex is a core dependency since 1.0.0 — reaching this branch
    # means a broken install. Handles stay None so module-level imports in
    # the submodules do not crash, and requires_codec_cortex() fails
    # closed at every gated call site with a precise diagnosis.
    _HAS_CODEC_CORTEX = False
    _codec_cortex = None
    _CODEC_CORTEX_API = None
    _CODEC_CORTEX_MISSING = ("parse_cortex", "validate", "render_hcortex_read")
    _cc_ast = _cc_lexer = _cc_parser = _cc_validator = None
    _cc_selectors = _cc_renderer = None
    _cc_canonicalize = None


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
    find_project_root_with_source,
    find_workspace_root,
    find_write_project_root,
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
