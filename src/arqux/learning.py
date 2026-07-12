"""Learning engine — compatibility shim.

This module now re-exports from ``core.learning`` package.
See ``core/learning/`` for the canonical implementation.
"""
from .core.learning import *
from .core.learning import (
    _preview_hash,
    _resolve_policy_path,
    _resolve_project_root,
    _validate_elevation_payload,
)
