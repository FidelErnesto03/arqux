"""Compatibility shim: elevation implementation lives in `arqux.core.learning.elevation` (BLP-004)."""
from __future__ import annotations

from ..elevation import Patch, normalize_section_id, plan_patch, render_diff

__all__ = ["Patch", "normalize_section_id", "plan_patch", "render_diff"]
