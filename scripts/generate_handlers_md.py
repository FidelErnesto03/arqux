#!/usr/bin/env python3
"""Generate HANDLERS.md from the ArqUX handler registry.

Usage:
    python scripts/generate_handlers_md.py [--output HANDLERS.md]
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate HANDLERS.md from registry")
    parser.add_argument("--output", default="HANDLERS.md", help="Output file path")
    args = parser.parse_args()

    # Import registry from the installed package
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

    from arqux.handlers import REGISTRY

    lines: list[str] = []
    lines.append("# ArqUX Handlers")
    lines.append("")
    lines.append(f"Total: **{len(REGISTRY)}** handlers")
    lines.append("")

    # Group by module
    modules: dict[str, list[tuple[str, str]]] = {}
    for name, spec in sorted(REGISTRY.items()):
        module = name.split(".")[0]
        if module not in modules:
            modules[module] = []
        modules[module].append((name, spec.description))

    for module in sorted(modules.keys()):
        lines.append(f"## {module}")
        lines.append("")
        lines.append("| Handler | Description |")
        lines.append("|---------|-------------|")
        for name, desc in modules[module]:
            lines.append(f"| `{name}` | {desc} |")
        lines.append("")

    output = Path(args.output)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated {output} with {len(REGISTRY)} handlers")


if __name__ == "__main__":
    main()
