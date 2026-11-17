#!/usr/bin/env python3
"""Generate HANDLERS.md from the ArqUX handler registry.

Rich reference: for every handler — name, description, parameters
(type/required/default from the JSON input schema), return shape,
error codes extracted from the handler source, and minimum permission
derived from permissions.py (GOVERNOR_ONLY / MUTATING_HANDLERS /
CONDITIONAL_MUTATING).

Usage:
    python scripts/generate_handlers_md.py [--output HANDLERS.md]

Regeneration is deterministic: same registry + same permissions → same doc.
"""

from __future__ import annotations

import argparse
import inspect
import re
from datetime import date
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from arqux.handlers import REGISTRY  # noqa: E402
from arqux.permissions import (  # noqa: E402
    CONDITIONAL_MUTATING,
    GOVERNOR_ONLY,
    MUTATING_HANDLERS,
)

_ERROR_RE = re.compile(r'"(ERR_[A-Z_]+|PERMISSION_DENIED|EXPORT_BLOCKED|INVALID_ARGS|INTERNAL_ERROR|NOT_FOUND|UNBOUND_SESSION|POLICY_BLOCK|MISSING_DEPENDENCY|ENGINE_UNAVAILABLE)"')

_DOMAIN_TITLES = {
    "blueprint": "Blueprints",
    "cortex": "Cortex / memoria",
    "cycle": "Ciclos",
    "evidence": "Evidencia",
    "handler": "Registro MCP",
    "identity": "Identidades",
    "journal": "Journal de políticas",
    "learning": "Aprendizaje",
    "loop": "Loop VAMOS",
    "policy": "Política",
    "project": "Proyectos",
    "review": "Revisión",
    "session": "Sesiones",
    "session_bridge": "Session bridge",
    "setup": "Setup / PlantUML",
    "skill": "Skills",
    "sync": "Sincronía",
    "task": "Tareas",
    "voice": "Voz (extra)",
    "workspace": "Workspace",
    "audit": "Auditoría",
    "comms": "Comms (extra)",
    "drift": "Drift",
    "render": "Render",
    "context": "Contexto",
}


def _permission(name: str) -> str:
    if name in GOVERNOR_ONLY:
        return "governor únicamente"
    if name in MUTATING_HANDLERS:
        return "mutante — governor/executor; auditor denegado"
    if name in CONDITIONAL_MUTATING:
        flags = CONDITIONAL_MUTATING[name]
        if flags:
            fl = ", ".join(f"`--{f}`" for f in flags)
            return f"mutante solo con {fl}; lectura permite auditor"
        return "mutante (gate interno); auditor solo lectura"
    return "lectura — cualquier rol, incluido auditor"


def _errors(spec) -> list[str]:
    try:
        src = inspect.getsource(spec.fn)
    except (OSError, TypeError):
        return []
    return sorted(set(_ERROR_RE.findall(src)))


def _params(spec) -> list[str]:
    schema = spec.input_schema or {}
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    if not props:
        return ["_sin parámetros_"]
    rows = []
    for pname in sorted(props):
        p = props[pname]
        ptype = p.get("type", "?")
        req = "**sí**" if pname in required else "no"
        default = p.get("default", "—")
        desc = (p.get("description") or "").strip()
        rows.append(
            f"| `{pname}` | `{ptype}` | {req} | {default} | {desc} |"
        )
    header = "| Parámetro | Tipo | Requerido | Default | Descripción |\n|---|---|---|---|---|"
    return [header] + rows


def _return_shape(spec) -> str:
    ret = inspect.signature(spec.fn).return_annotation
    if ret is inspect.Signature.empty:
        return "`OUT-WORK` / `OUT-ERROR`"
    return f"`{getattr(ret, '__name__', ret)}` → `OUT-WORK` / `OUT-ERROR`"


def _domain(name: str) -> str:
    first = name.split(".")[0]
    return _DOMAIN_TITLES.get(first, first.replace("_", " ").title())


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate HANDLERS.md from registry")
    parser.add_argument("--output", default="HANDLERS.md", help="Output file path")
    args = parser.parse_args()

    domains: dict[str, list[str]] = {}
    for name, spec in sorted(REGISTRY.items()):
        domains.setdefault(_domain(name), []).append(name)

    lines: list[str] = []
    lines.append("---")
    lines.append("doc_type: reference")
    lines.append("status: informative")
    lines.append("version: 1.0.0")
    lines.append(f"verified: {date.today().isoformat()}")
    lines.append("---")
    lines.append("")
    # Brand header/footer per docs/es/formato-documental.md — generated, not
    # hand-edited; identical markers to scripts/format_docs.py output.
    lines.append("<!-- DOC-BRAND -->")
    lines.append('<p align="center">')
    lines.append("  <picture>")
    lines.append('    <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/brand/arqux-logo-primary-dark.svg">')
    lines.append('    <img alt="ArqUX" src="./docs/assets/brand/arqux-logo-primary-light.svg" width="240">')
    lines.append("  </picture>")
    lines.append("</p>")
    lines.append('<p align="center"><sub>Referencia · Informativo · ArqUX 1.0.0</sub></p>')
    lines.append("<!-- /DOC-BRAND -->")
    lines.append("")
    lines.append("# Referencia de handlers MCP")
    lines.append("")
    lines.append(f"Total: **{len(REGISTRY)}** handlers en {len(domains)} dominios.")
    lines.append("")
    lines.append(
        "Generado del registro real. No editar a mano: regenerar con "
        "`python scripts/generate_handlers_md.py`."
    )
    lines.append("")
    lines.append("## Índice por dominio")
    lines.append("")
    for d in sorted(domains):
        anchor = d.lower().replace(" ", "-").replace("/", "").replace("(", "").replace(")", "")
        lines.append(f"- [{d}](#{anchor}) — {len(domains[d])} handlers")
    lines.append("")

    for domain in sorted(domains):
        lines.append(f"## {domain}")
        lines.append("")
        for name in domains[domain]:
            spec = REGISTRY[name]
            lines.append(f"### `{name}`")
            lines.append("")
            lines.append(spec.description.strip() or "_sin descripción_")
            lines.append("")
            lines.extend(_params(spec))
            lines.append("")
            lines.append(f"**Retorna**: {_return_shape(spec)}")
            lines.append("")
            errs = _errors(spec)
            if errs:
                lines.append("**Errores posibles**: " + ", ".join(f"`{e}`" for e in errs))
                lines.append("")
            lines.append(f"**Permiso mínimo**: {_permission(name)}")
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append("## Regeneración")
    lines.append("")
    lines.append(
        "Este documento deriva 100% del registro: "
        "`scripts/generate_handlers_md.py` lee `arqux.handlers.REGISTRY` "
        "(firma JSON-schema + docstring + errores del source) y "
        "`arqux.permissions` (clasificación mutante/condicional/governor). "
        "Cualquier handler nuevo aparece al regenerar — sin edición manual."
    )
    lines.append("")
    lines.append("<!-- DOC-FOOT -->")
    lines.append("<hr>")
    lines.append(
        f'<p align="center"><sub>ArqUX 1.0.0 · verificado {date.today().isoformat()} · '
        '<a href="./docs/es/README.md">índice de documentación</a></sub></p>'
    )
    lines.append("<!-- /DOC-FOOT -->")
    lines.append("")

    output = Path(args.output)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated {output} with {len(REGISTRY)} handlers in {len(domains)} domains")


if __name__ == "__main__":
    main()
