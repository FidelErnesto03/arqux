# ruff: noqa: I001, F405
"""Learning engine — compatibility shim.

This module now re-exports from ``core.learning`` package.
See ``core/learning/`` for the canonical implementation.
"""
from .core.learning import *
from .core.learning import (  # noqa: F401 — re-export private names not picked up by *
    _build_brain_doc,
    _draft_to_dict,
    _hash_text,
    _load_policies,
    _planned_entry,
    _preview_hash,
    _resolve_behavioral_paths,
    _resolve_policy_path,
    _resolve_project_root,
    _validate_elevation_payload,
)
