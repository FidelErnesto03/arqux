"""Corpus-level cortex handlers (BLP-006 / gap 2.6)."""
from __future__ import annotations

from pathlib import Path

from ..cortex_out import CortexOUT


def corpus_list_handler(
    path: str | None = None,
    *,
    ctx=None,
) -> CortexOUT:
    """List .cortex files across a corpus/root (minimal cross-corpus query)."""
    root = Path(path or ".").resolve()
    if not root.exists():
        return CortexOUT.error(f"Path not found: {root}", code="NOT_FOUND")
    files = sorted(str(p) for p in root.rglob("*.cortex") if ".venv" not in p.parts)
    return CortexOUT.work(
        "cortex.corpus.list ok",
        root=str(root),
        count=len(files),
        files=files[:500],
    )


def corpus_query_handler(
    pattern: str,
    path: str | None = None,
    *,
    ctx=None,
) -> CortexOUT:
    """Query corpus files by simple path substring (minimal transversal query)."""
    root = Path(path or ".").resolve()
    matches = []
    if root.exists():
        needle = str(pattern)
        for p in root.rglob("*.cortex"):
            if ".venv" in p.parts:
                continue
            sp = str(p)
            if needle in sp:
                matches.append(sp)
    return CortexOUT.work(
        "cortex.corpus.query ok",
        root=str(root),
        pattern=pattern,
        count=len(matches),
        matches=sorted(matches)[:500],
    )

handler_schemas = [
    {
        "name": "cortex.corpus.list",
        "fn": corpus_list_handler,
        "description": "List .cortex files in a corpus/root directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Root path to scan (default cwd)."}},
            "required": [],
        },
    },
    {
        "name": "cortex.corpus.query",
        "fn": corpus_query_handler,
        "description": "Query corpus .cortex files by path substring/pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Substring to match in file paths."},
                "path": {"type": "string", "description": "Root path to scan (default cwd)."},
            },
            "required": ["pattern"],
        },
    },
]
