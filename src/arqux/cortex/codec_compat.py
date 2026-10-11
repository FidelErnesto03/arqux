"""Compatibility boundary for CODEC-CORTEX generations.

ArqUX owns its document model and writer. This module only adapts the
external parser surface so callers can validate legacy 0.6.x files and the
current ``codec-cortex 1.0.0rc1`` distribution without importing one layout
unconditionally.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import metadata
from typing import Any


@dataclass(frozen=True)
class CodecInfo:
    """Detected external CODEC-CORTEX backend."""

    package: str | None
    version: str | None
    parser: str | None

    @property
    def available(self) -> bool:
        return self.parser is not None


def _package_version() -> str | None:
    try:
        return metadata.version("codec-cortex")
    except metadata.PackageNotFoundError:
        return None


def _backend() -> tuple[CodecInfo, Callable[..., Any] | None]:
    """Return the newest installed parser and its normalized entry point."""
    try:
        from codec_cortex.dispatcher import parse_cortex

        return CodecInfo("codec_cortex", _package_version(), "dispatcher"), parse_cortex
    except ImportError:
        pass

    try:
        from cortex.core.parser import parse_cortex

        return CodecInfo("cortex", _package_version(), "legacy"), parse_cortex
    except ImportError:
        return CodecInfo(None, _package_version(), None), None


def codec_info() -> CodecInfo:
    """Describe the parser available in the current environment."""
    return _backend()[0]


def parse_with_codec(text: str, *, path: str | None = None) -> Any:
    """Parse *text* through the newest available CODEC-CORTEX API."""
    info, parser = _backend()
    if parser is None:
        raise RuntimeError(
            "CODEC-CORTEX is unavailable; install codec-cortex>=0.6.2,<0.7 "
            "(the 1.0.0rc1 candidate provides only parse_cortex)"
        )
    if info.parser == "legacy" and path is not None:
        return parser(text, path=path)
    return parser(text)


def verify_text(text: str, *, path: str | None = None) -> dict[str, Any]:
    """Return a compact, version-independent verification result."""
    info = codec_info()
    doc = parse_with_codec(text, path=path)
    sections = getattr(doc, "sections", [])
    entries = sum(
        len(getattr(section, "ideas", getattr(section, "entries", [])))
        for section in sections
    )
    return {
        "valid": True,
        "package": info.package,
        "version": info.version,
        "parser": info.parser,
        "sections": len(sections),
        "entries": entries,
    }


__all__ = ["CodecInfo", "codec_info", "parse_with_codec", "verify_text"]
