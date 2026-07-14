#!/usr/bin/env python3
# =============================================================================
# arqux_response_hook.py — Hook pre-respuesta invisible
# BLP-017: Governance Enforcement
#
# Si falta ⬡ HEADER + HCORTEX, CORRIGE en vez de rechazar.
# Identidad tomada de ARQUX_AGENT_ID (seteada por el gate).
# =============================================================================
"""Hook pre-respuesta — enforce ⬡ HEADER + HCORTEX."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HEADER_PATTERN = re.compile(r"^⬡\s*\w+\s*\|\s*[A-Za-z0-9]+\s*\|[\s\w\-|]+", re.MULTILINE)
HCORTEX_INDICATORS = ["═══", "───", "✅", "❌", "⚠️", "🟢", "🔴", "🟡", "§", "##"]


def _get_active_identity() -> str:
    return os.environ.get("ARQUX_AGENT_ID", "alfred")


def _get_project_scope() -> tuple[str, str]:
    d = Path.cwd()
    while d != d.parent:
        arqux = d / ".arqux"
        if arqux.exists():
            try:
                ctx = arqux / "context.cortex"
                if ctx.exists():
                    text = ctx.read_text()
                    pm = re.search(r"project[:\s]+(\w+)", text)
                    sm = re.search(r"scope[:\s]+([\w-]+)", text)
                    return (
                        pm.group(1) if pm else "ARQUX",
                        sm.group(1) if sm else "CYCLE-04",
                    )
            except Exception:
                pass
            break
        d = d.parent
    return ("ARQUX", "CYCLE-04")


def has_header(text: str) -> bool:
    return bool(HEADER_PATTERN.match(text.strip()))


def main() -> int:
    text = sys.stdin.read()
    agent = _get_active_identity()
    project, scope = _get_project_scope()

    if not text.strip():
        print(f"⬡ {agent} | {project} | {scope}")
        return 0

    if not has_header(text):
        text = f"⬡ {agent} | {project} | {scope}\n\n{text.strip()}"

    sys.stdout.write(text.rstrip() + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
